# Changelog

All notable changes to this server are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org).

## [0.1.0] - Unreleased

First release. A stdio MCP server for the FastOCR Document OCR API with the tools
`ocr_file` (a local PDF, PNG, JPG, JPEG, GIF, WebP or BMP file), `get_document`,
`list_documents` and `delete_document`. `ocr_pdf` is the same tool as `ocr_file` under its
earlier name. Needs `fastocr-sdk` 0.2.0 or later for image uploads. API requests send the
User-Agent `fastocr-mcp/<version>` followed by the SDK's own.
