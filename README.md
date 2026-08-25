# Elena SEO Writer / Agent Writer Lite

This repository contains a minimal test prototype that generates a draft SEO article in Russian through Google Gemini, saves it to the repository, and opens a Pull Request for human review.

This test version is intentionally limited:

- manual запуск через GitHub Actions;
- ручной ввод темы статьи;
- сохранение результата только в GitHub;
- проверка человеком через Pull Request;
- никакой автопубликации на сайт;
- никаких тяжёлых компонентов вроде PostgreSQL, Prisma, Next.js или внешних SEO-платформ.

## What the system does

When you run the GitHub Actions workflow manually and provide a topic:

1. the workflow calls `scripts/generate_article.py`;
2. the script sends the prompt to Google Gemini using `GEMINI_API_KEY`;
3. Gemini returns a Markdown article in Russian;
4. the script saves the draft article in `content/blog/`;
5. the workflow creates a separate branch and opens a Pull Request into `main`.

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
status: draft
---
```

## How to review the Pull Request

After the workflow finishes:

1. open the generated Pull Request;
2. review the Markdown article content;
3. request edits if needed;
4. merge manually only after human approval.

This repository does not auto-merge and does not auto-publish anything.
