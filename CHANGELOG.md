# Changelog

All notable changes to this server are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org).

## [0.2.0] - 2026-10-25

- New tool `get_balance`: the pages left in free, contract and Page Pack balances, and where
  to buy more. Needs `fastocr-sdk` 0.3.0 or later.
- Out-of-pages messages point to the pricing page for Page Packs and say "out of pages".
  The `concurrency_limit` message states the limits: 2 documents at once, 10 with an API
  contract or 10,000 or more pages bought.

## [0.1.1] - 2026-10-25

Documentation only: a redesigned README with setup for Claude Code, Claude Desktop, Cursor
and VS Code first. No code changes.

## [0.1.0] - 2026-10-24

First release. A stdio MCP server for the FastOCR Document OCR API with the tools
`ocr_file` (a local PDF, PNG, JPG, JPEG, GIF, WebP or BMP file), `get_document`,
`list_documents` and `delete_document`. `ocr_pdf` is the same tool as `ocr_file` under its
earlier name. Needs `fastocr-sdk` 0.2.0 or later for image uploads. API requests send the
User-Agent `fastocr-mcp/<version>` followed by the SDK's own.
