import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_site import BuildError, build_site, markdown_to_html, parse_article  # noqa: E402


class BuildSiteTests(unittest.TestCase):
    def write_article(
        self,
        path: Path,
        *,
        title: str = "Тестовая статья",
        status: str = "published",
        body: str = "# Тестовая статья\n\nПолезный текст.",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                [
                    "---",
                    f'title: "{title}"',
                    'description: "Краткое описание статьи"',
                    'date: "2026-08-25"',
                    "language: ru",
                    f"status: {status}",
                    "---",
                    body,
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def create_project(self, root: Path) -> None:
        (root / "public" / "assets").mkdir(parents=True)
        (root / "public" / "index.html").write_text("ORIGINAL HOME", encoding="utf-8")
        (root / "public" / "assets" / "keep.txt").write_text("KEEP", encoding="utf-8")
        (root / "public" / "sitemap.xml").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://elenagofman.beeryakov.workers.dev/</loc></url>
</urlset>
""",
            encoding="utf-8",
        )
        (root / "content" / "blog").mkdir(parents=True)
        (root / "templates").mkdir()
        for template_name in ("blog_index.html", "blog_article.html"):
            (root / "templates" / template_name).write_text(
                (ROOT / "templates" / template_name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    def test_parse_article_reads_required_metadata_and_slug(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "2026-08-25-Моя статья.md"
            self.write_article(source, title="Уход: важные шаги")
            article = parse_article(source)

        self.assertEqual(article.title, "Уход: важные шаги")
        self.assertEqual(article.slug, "моя-статья")
        self.assertEqual(article.status, "published")
        self.assertEqual(article.date.isoformat(), "2026-08-25")

    def test_markdown_renderer_handles_article_markup_and_escapes_html(self) -> None:
        rendered = markdown_to_html(
            "# Заголовок\n\nАбзац с **важным** словом и <script>.\n\n* Первый\n* Второй"
        )

        self.assertIn("<h1>Заголовок</h1>", rendered)
        self.assertIn("<strong>важным</strong>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("<ul>", rendered)
        self.assertNotIn("<script>", rendered)

    def test_build_copies_public_and_renders_only_published_articles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_project(root)
            self.write_article(root / "content" / "blog" / "2026-08-25-ready.md")
            self.write_article(
                root / "content" / "blog" / "2026-08-26-draft.md",
                status="draft",
            )

            articles = build_site(root)

            self.assertEqual(len(articles), 1)
            self.assertEqual((root / "dist" / "index.html").read_text(), "ORIGINAL HOME")
            self.assertEqual((root / "dist" / "assets" / "keep.txt").read_text(), "KEEP")
            self.assertTrue((root / "dist" / "blog" / "ready" / "index.html").exists())
            self.assertFalse((root / "dist" / "blog" / "draft").exists())
            index = (root / "dist" / "blog" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Тестовая статья", index)
            self.assertIn("/blog/ready/", index)

    def test_build_updates_sitemap_and_rejects_published_article_without_h1(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_project(root)
            self.write_article(root / "content" / "blog" / "2026-08-25-ready.md")
            build_site(root)
            sitemap = (root / "dist" / "sitemap.xml").read_text(encoding="utf-8")
            self.assertIn("https://elenagofman.beeryakov.workers.dev/blog/", sitemap)
            self.assertIn("https://elenagofman.beeryakov.workers.dev/blog/ready/", sitemap)

            self.write_article(
                root / "content" / "blog" / "2026-08-26-invalid.md",
                body="Текст без заголовка.",
            )
            with self.assertRaisesRegex(BuildError, "exactly one H1"):
                build_site(root)


if __name__ == "__main__":
    unittest.main()
