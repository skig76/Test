# Elena SEO Site + Agent Writer Lite

This repository contains the static Elena Gofman Cosmetology website, the Gemini article writer, and the publishing bridge that turns approved Markdown articles into static blog pages.

The workflow keeps approval and deployment separate:

- article generation starts manually through GitHub Actions;
- Gemini saves the Russian article in `content/blog/`;
- GitHub opens a separate Pull Request for human review;
- a human decides whether to merge it;
- the site build converts approved Markdown into HTML in `dist/blog/`;
- deployment to Cloudflare remains a separate manual action.

There is no automatic merge and no automatic deployment.

## What the system does

When you run the GitHub Actions workflow manually and provide a topic:

1. the workflow calls `scripts/generate_article.py`;
2. the script sends the prompt to Google Gemini using `GEMINI_API_KEY`;
3. Gemini returns a Markdown article in Russian;
4. the script saves the article in `content/blog/`;
5. the workflow creates a separate branch and opens a Pull Request into `main`;
6. after review and manual merge, the next manual site build includes the article.

## Add `GEMINI_API_KEY`

1. Open the repository on GitHub.
2. Go to `Settings` -> `Secrets and variables` -> `Actions`.
3. Click `New repository secret`.
4. Create a secret named `GEMINI_API_KEY`.
5. Paste your Gemini API key as the value.

Do not store the API key in the code or commit it to the repository.

## Run the workflow manually

1. Open the `Actions` tab in GitHub.
2. Select the workflow `Generate SEO Article`.
3. Click `Run workflow`.
4. Enter the article topic in the `topic` field.
5. Start the workflow.

## Where the article appears

Generated articles are saved in:

`content/blog/`

Each generated file includes frontmatter like:

```yaml
---
title: "..."
description: "..."
date: "YYYY-MM-DD"
language: ru
status: published
---
```

`status: published` makes the file eligible for the site build. It does not deploy the branch. The approval gate is the manual Pull Request merge, and publishing still requires a separate manual deployment.

## How to review the Pull Request

After the workflow finishes:

1. open the generated Pull Request;
2. review the Markdown article content;
3. request edits if needed;
4. merge manually only after human approval.

This repository does not auto-merge or auto-deploy.

## Build the site

```bash
npm ci
npm test
npm run build
```

The build validates article metadata, copies `public/` to a fresh `dist/` directory, creates the blog index and article pages, and adds their URLs to `dist/sitemap.xml`. It does not modify the existing source pages in `public/`.

`dist/` is generated output and is not committed. The npm commands can find Python 3 through `py`, `python`, or `python3`, which supports Windows as well as Linux and macOS.

## Website source

The existing website source remains in `public/`:

- `public/index.html`
- `public/tipulei-panim-beer-yaakov/index.html`
- `public/akne-beer-yaakov/index.html`
- `public/pigmentatzia-beer-yaakov/index.html`
- `public/rf-ipl-beer-yaakov/index.html`
- `public/assets/`
- `public/robots.txt`
- `public/sitemap.xml`

Blog Markdown remains in `content/blog/`. Templates are in `templates/`, and the build logic is in `scripts/build_site.py`.

Cloudflare serves the generated `dist/` directory according to `wrangler.jsonc`.

## Local preview

```bash
npm run dev
```

This builds the site first and then starts Wrangler locally.

## Manual deployment

```bash
npm run deploy
```

This rebuilds the site and starts a real Wrangler deployment. Run it only after reviewing the merged changes. GitHub Actions validates the bundle with `wrangler deploy --dry-run`; it never performs the real deployment.
