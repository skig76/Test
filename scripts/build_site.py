from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sys
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


SITE_URL = "https://elenagofman.beeryakov.workers.dev"
PUBLISHABLE_STATUS = "published"
KNOWN_STATUSES = {"draft", PUBLISHABLE_STATUS}
REQUIRED_FIELDS = {"title", "description", "date", "language", "status"}
FRONTMATTER_RE = re.compile(
    r"\A---\r?\n(?P<frontmatter>.*?)\r?\n---\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)
TEMPLATE_TOKEN_RE = re.compile(r"{{\s*([a-z_][a-z0-9_]*)\s*}}")


class BuildError(RuntimeError):
    """Raised when an article or site source cannot be built safely."""


@dataclass(frozen=True)
class Article:
    source: Path
    title: str
    description: str
    date: dt.date
    language: str
    status: str
    slug: str
    body: str

    @property
    def url_path(self) -> str:
        encoded_slug = urllib.parse.quote(self.slug, safe="-")
        return f"/blog/{encoded_slug}/"

    @property
    def canonical_url(self) -> str:
        return f"{SITE_URL}{self.url_path}"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _parse_frontmatter_value(raw_value: str, source: Path, key: str) -> str:
    value = raw_value.strip()
    if not value:
        raise BuildError(f"{source}: frontmatter field '{key}' is empty")
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise BuildError(
                f"{source}: frontmatter field '{key}' has invalid quoting"
            ) from exc
        if not isinstance(parsed, str):
            raise BuildError(f"{source}: frontmatter field '{key}' must be text")
        return parsed.strip()
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1].replace("''", "'").strip()
    return value


def slugify_filename(path: Path) -> str:
    value = path.stem
    value = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", value)
    value = unicodedata.normalize("NFKC", value).strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = "".join(char for char in value if char.isalnum() or char == "-")
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if not value:
        raise BuildError(f"{path}: filename does not contain a usable article slug")
    return value


def parse_article(path: Path) -> Article:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise BuildError(f"{path}: expected YAML frontmatter between --- lines")

    metadata: dict[str, str] = {}
    for line_number, line in enumerate(match.group("frontmatter").splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise BuildError(f"{path}:{line_number}: invalid frontmatter line")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[a-z_][a-z0-9_-]*", key):
            raise BuildError(f"{path}:{line_number}: invalid frontmatter key '{key}'")
        if key in metadata:
            raise BuildError(f"{path}:{line_number}: duplicate frontmatter key '{key}'")
        metadata[key] = _parse_frontmatter_value(raw_value, path, key)

    missing = sorted(REQUIRED_FIELDS - metadata.keys())
    if missing:
        raise BuildError(f"{path}: missing frontmatter fields: {', '.join(missing)}")

    try:
        article_date = dt.date.fromisoformat(metadata["date"])
    except ValueError as exc:
        raise BuildError(f"{path}: date must use YYYY-MM-DD format") from exc

    language = metadata["language"].lower()
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", language):
        raise BuildError(f"{path}: language must be a two-letter language code")

    status = metadata["status"].lower()
    if status not in KNOWN_STATUSES:
        allowed = ", ".join(sorted(KNOWN_STATUSES))
        raise BuildError(f"{path}: status must be one of: {allowed}")

    body = match.group("body").strip()
    if not body:
        raise BuildError(f"{path}: article body is empty")
    if status == PUBLISHABLE_STATUS and len(re.findall(r"(?m)^#\s+\S", body)) != 1:
        raise BuildError(f"{path}: a published article must contain exactly one H1")

    return Article(
        source=path,
        title=metadata["title"],
        description=metadata["description"],
        date=article_date,
        language=language,
        status=status,
        slug=slugify_filename(path),
        body=body,
    )


def _safe_link(match: re.Match[str]) -> str:
    label = match.group(1)
    raw_href = html.unescape(match.group(2)).strip()
    allowed = raw_href.startswith(("https://", "http://", "/", "#", "mailto:", "tel:"))
    if not allowed:
        return label
    href = html.escape(raw_href, quote=True)
    external = ' target="_blank" rel="noopener"' if raw_href.startswith(("https://", "http://")) else ""
    return f'<a href="{href}"{external}>{label}</a>'


def render_inline(value: str) -> str:
    rendered = html.escape(value, quote=True)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _safe_link, rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", rendered)
    return rendered


def markdown_to_html(markdown: str) -> str:
    output: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    code_lines: list[str] | None = None
    code_language = ""

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{render_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            output.append(f"</{list_type}>")
            list_type = None

    for line in markdown.splitlines():
        if code_lines is not None:
            if line.startswith("```"):
                language_class = (
                    f' class="language-{html.escape(code_language, quote=True)}"'
                    if code_language
                    else ""
                )
                output.append(
                    f"<pre><code{language_class}>{html.escape(chr(10).join(code_lines))}</code></pre>"
                )
                code_lines = None
                code_language = ""
            else:
                code_lines.append(line)
            continue

        fence = re.match(r"^```([A-Za-z0-9_+-]*)\s*$", line)
        if fence:
            flush_paragraph()
            close_list()
            code_lines = []
            code_language = fence.group(1)
            continue

        if not line.strip():
            flush_paragraph()
            close_list()
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            output.append(f"<h{level}>{render_inline(heading.group(2))}</h{level}>")
            continue

        unordered = re.match(r"^\s*[-+*]\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if unordered or ordered:
            flush_paragraph()
            requested_type = "ul" if unordered else "ol"
            if list_type != requested_type:
                close_list()
                list_type = requested_type
                output.append(f"<{list_type}>")
            item = (unordered or ordered).group(1)
            output.append(f"<li>{render_inline(item)}</li>")
            continue

        if re.fullmatch(r"\s*([-*_])(?:\s*\1){2,}\s*", line):
            flush_paragraph()
            close_list()
            output.append("<hr>")
            continue

        quote = re.match(r"^>\s?(.*)$", line)
        if quote:
            flush_paragraph()
            close_list()
            output.append(f"<blockquote><p>{render_inline(quote.group(1))}</p></blockquote>")
            continue

        paragraph.append(line.strip())

    if code_lines is not None:
        raise BuildError("article contains an unclosed fenced code block")
    flush_paragraph()
    close_list()
    return "\n".join(output)


def render_template(path: Path, context: dict[str, str]) -> str:
    template = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise BuildError(f"{path}: missing template value '{key}'")
        return context[key]

    return TEMPLATE_TOKEN_RE.sub(replace, template)


def load_published_articles(content_dir: Path) -> list[Article]:
    articles = [parse_article(path) for path in sorted(content_dir.glob("*.md"))]
    published = [article for article in articles if article.status == PUBLISHABLE_STATUS]
    seen_slugs: dict[str, Path] = {}
    for article in published:
        previous = seen_slugs.get(article.slug)
        if previous:
            raise BuildError(
                f"duplicate article slug '{article.slug}' in {previous} and {article.source}"
            )
        seen_slugs[article.slug] = article.source
    return sorted(published, key=lambda item: (item.date, item.title), reverse=True)


def _json_for_html(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def render_article(article: Article, template_path: Path) -> str:
    structured_data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": article.title,
        "description": article.description,
        "datePublished": article.date.isoformat(),
        "inLanguage": article.language,
        "mainEntityOfPage": article.canonical_url,
        "author": {"@type": "Person", "name": "Elena Gofman"},
        "publisher": {"@type": "Organization", "name": "Elena Gofman Cosmetology"},
    }
    return render_template(
        template_path,
        {
            "language": html.escape(article.language, quote=True),
            "direction": "rtl" if article.language.startswith("he") else "ltr",
            "title": html.escape(article.title),
            "description": html.escape(article.description, quote=True),
            "canonical_url": html.escape(article.canonical_url, quote=True),
            "published_date": article.date.isoformat(),
            "article_html": markdown_to_html(article.body),
            "structured_data": _json_for_html(structured_data),
        },
    )


def render_blog_index(articles: list[Article], template_path: Path) -> str:
    cards = []
    for article in articles:
        cards.append(
            "\n".join(
                [
                    '<article class="article-card">',
                    f'  <time datetime="{article.date.isoformat()}">{article.date.strftime("%d.%m.%Y")}</time>',
                    f'  <h2><a href="{html.escape(article.url_path, quote=True)}">{html.escape(article.title)}</a></h2>',
                    f"  <p>{html.escape(article.description)}</p>",
                    f'  <a class="read-more" href="{html.escape(article.url_path, quote=True)}">Читать статью →</a>',
                    "</article>",
                ]
            )
        )
    if not cards:
        cards.append('<p class="empty-state">Новые статьи появятся здесь после проверки.</p>')

    structured_data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Статьи о косметологии — Elena Gofman Cosmetology",
        "url": f"{SITE_URL}/blog/",
        "inLanguage": "ru",
    }
    return render_template(
        template_path,
        {
            "article_cards": "\n".join(cards),
            "structured_data": _json_for_html(structured_data),
        },
    )


def update_sitemap(sitemap_path: Path, articles: list[Article]) -> None:
    if not sitemap_path.exists():
        raise BuildError(f"missing source sitemap: {sitemap_path}")
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", namespace)
    try:
        tree = ET.parse(sitemap_path)
    except ET.ParseError as exc:
        raise BuildError(f"invalid sitemap XML: {sitemap_path}") from exc
    root = tree.getroot()
    if root.tag != f"{{{namespace}}}urlset":
        raise BuildError(f"{sitemap_path}: expected a sitemap urlset")

    existing = {
        node.text.strip()
        for node in root.findall(f"{{{namespace}}}url/{{{namespace}}}loc")
        if node.text and node.text.strip()
    }
    last_modified = max((article.date for article in articles), default=dt.date.today())
    entries = [(f"{SITE_URL}/blog/", last_modified)]
    entries.extend((article.canonical_url, article.date) for article in articles)
    for location, modified in entries:
        if location in existing:
            continue
        url = ET.SubElement(root, f"{{{namespace}}}url")
        ET.SubElement(url, f"{{{namespace}}}loc").text = location
        ET.SubElement(url, f"{{{namespace}}}lastmod").text = modified.isoformat()
        existing.add(location)

    ET.indent(tree, space="  ")
    tree.write(sitemap_path, encoding="utf-8", xml_declaration=True)


def build_site(root: Path | None = None) -> list[Article]:
    root = (root or project_root()).resolve()
    public_dir = root / "public"
    content_dir = root / "content" / "blog"
    templates_dir = root / "templates"
    dist_dir = root / "dist"

    for required in (public_dir, content_dir, templates_dir):
        if not required.exists():
            raise BuildError(f"missing required source directory: {required}")

    articles = load_published_articles(content_dir)

    if dist_dir.exists():
        if dist_dir.parent != root or dist_dir.name != "dist":
            raise BuildError(f"refusing to clean unexpected build path: {dist_dir}")
        shutil.rmtree(dist_dir)
    shutil.copytree(public_dir, dist_dir)

    blog_dir = dist_dir / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)
    article_template = templates_dir / "blog_article.html"
    index_template = templates_dir / "blog_index.html"
    for article in articles:
        target_dir = blog_dir / article.slug
        target_dir.mkdir(parents=True, exist_ok=False)
        (target_dir / "index.html").write_text(
            render_article(article, article_template).rstrip() + "\n",
            encoding="utf-8",
        )

    (blog_dir / "index.html").write_text(
        render_blog_index(articles, index_template).rstrip() + "\n",
        encoding="utf-8",
    )
    update_sitemap(dist_dir / "sitemap.xml", articles)
    return articles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the static Elena Gofman site.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root (used by tests and local diagnostics).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    articles = build_site(args.root)
    output = str((args.root / "dist").resolve()) if args.root else "dist"
    print(f"Built site with {len(articles)} article(s) in {output}/")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BuildError, OSError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
