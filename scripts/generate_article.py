import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


MODEL_NAME = "gemini-3.6-flash"
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL_NAME}:generateContent"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a draft Russian SEO article with Gemini."
    )
    parser.add_argument("topic", help="Topic for the article")
    return parser.parse_args()


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_prompt() -> str:
    prompt_path = project_root() / "prompts" / "seo_ru.txt"
    return prompt_path.read_text(encoding="utf-8").strip()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = "".join(char for char in value if char.isalnum() or char == "-")
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if not value:
        value = "article"
    return value[:80]


def build_prompt(template: str, topic: str) -> str:
    return f"{template}\n\nТема статьи: {topic}\n"


def call_gemini(api_key: str, prompt: str) -> str:
    url = f"{API_URL}?key={urllib.parse.quote(api_key)}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
        },
    }
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API request failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc

    parts = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)

    if not parts:
        raise RuntimeError("Gemini API returned no text content.")

    return "\n".join(parts).strip()


def parse_response(text: str) -> tuple[str, str, str]:
    title_match = re.search(r"^SEO_TITLE:\s*(.+)$", text, re.MULTILINE)
    description_match = re.search(r"^META_DESCRIPTION:\s*(.+)$", text, re.MULTILINE)
    article_match = re.search(r"^ARTICLE_MARKDOWN:\s*$\n?(.*)$", text, re.MULTILINE | re.DOTALL)

    if not title_match or not description_match or not article_match:
        raise RuntimeError(
            "Gemini response did not match the expected format "
            "(SEO_TITLE, META_DESCRIPTION, ARTICLE_MARKDOWN)."
        )

    title = title_match.group(1).strip()
    description = description_match.group(1).strip()
    article = article_match.group(1).strip()

    if not title or not description or not article:
        raise RuntimeError("Gemini response contained empty title, description, or article.")

    return title, description, article


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def compose_markdown(title: str, description: str, article: str) -> str:
    today = dt.date.today().isoformat()
    frontmatter = "\n".join(
        [
            "---",
            f"title: {yaml_quote(title)}",
            f"description: {yaml_quote(description)}",
            f"date: {yaml_quote(today)}",
            "language: ru",
            "status: published",
            "---",
            "",
        ]
    )
    return frontmatter + article.rstrip() + "\n"


def output_path(topic: str) -> Path:
    today = dt.date.today().isoformat()
    filename = f"{today}-{slugify(topic)}.md"
    return project_root() / "content" / "blog" / filename


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is required.")

    prompt_template = load_prompt()
    response_text = call_gemini(api_key=api_key, prompt=build_prompt(prompt_template, args.topic))
    title, description, article = parse_response(response_text)
    markdown = compose_markdown(title=title, description=description, article=article)

    path = output_path(args.topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    print(path.relative_to(project_root()).as_posix())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
