<a href="https://fastocr.org"><img src="https://raw.githubusercontent.com/fastocr-org/fastocr-mcp/main/docs/images/logo.png" alt="FastOCR" width="56" height="56"></a>

# FastOCR MCP server

OCR any scanned PDF or image from Claude, Cursor and other MCP clients, in 100+ languages. **[fastocr.org](https://fastocr.org)** · [Docs](https://fastocr.org/docs) · [Get an API key](https://fastocr.org/developers/keys)

<!-- mcp-name: io.github.fastocr-org/fastocr-mcp -->

[![PyPI](https://img.shields.io/pypi/v/fastocr-mcp.svg)](https://pypi.org/project/fastocr-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An [MCP](https://modelcontextprotocol.io) server for the
[FastOCR Document OCR API](https://fastocr.org/docs). It lets Claude Desktop,
Claude Code, Cursor and other MCP clients OCR a local scanned PDF or image and get
back its text or a searchable PDF.

- PDF files up to 1 GiB, and PNG, JPG, JPEG, GIF, WebP and BMP images up to 20 MiB; 100+ languages.
- Built on the official [`fastocr-sdk`](https://pypi.org/project/fastocr-sdk/) and the
  official MCP Python SDK. Runs locally over stdio; your files go only to the FastOCR API.

![A scanned Arabic book page beside the text FastOCR returned for it](https://raw.githubusercontent.com/fastocr-org/fastocr-mcp/main/docs/images/ocr-before-after.png)

A real scanned page and the first lines of the text FastOCR returned for it, unedited.

API reference and guides: **https://fastocr.org/docs**

## Get an API key

Any signed-in FastOCR account can create an API key and start right away.

1. Sign in and create an API key in the
   [developer console](https://fastocr.org/developers/keys). You accept the
   [API terms](https://fastocr.org/api-terms) with your first key.
2. Set the key as `FASTOCR_API_KEY` in your MCP client config (see below).
3. When you need more than the free pages, buy a prepaid API page pack by card in the
   [developer console](https://fastocr.org/developers/keys#buy-api-pages).

Each account gets 50 free document pages per month.

## Install

With [uv](https://docs.astral.sh/uv/) there is nothing to install; MCP clients run it with
`uvx fastocr-mcp`. Or install it with pip and run `fastocr-mcp`:

```bash
pip install fastocr-mcp
```

Python 3.10 or newer. The server reads the key from `FASTOCR_API_KEY`.

## Configure your MCP client

### Claude Code

```bash
claude mcp add fastocr -e FASTOCR_API_KEY=your_api_key -- uvx fastocr-mcp
```

### Claude Desktop

Add this to `claude_desktop_config.json` (Settings > Developer > Edit Config), then restart
Claude Desktop:

```json
{
  "mcpServers": {
    "fastocr": {
      "command": "uvx",
      "args": ["fastocr-mcp"],
      "env": { "FASTOCR_API_KEY": "your_api_key" }
    }
  }
}
```

### Cursor

Add the same block to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project):

```json
{
  "mcpServers": {
    "fastocr": {
      "command": "uvx",
      "args": ["fastocr-mcp"],
      "env": { "FASTOCR_API_KEY": "your_api_key" }
    }
  }
}
```

If you installed with pip, use `"command": "fastocr-mcp"` and `"args": []`.

## Tools

| Tool | What it does |
|---|---|
| `ocr_file(path, output="text", output_path=None)` | Uploads a local PDF or image, runs OCR and waits up to 45 seconds; a larger document returns its id for `get_document`. `output="text"` returns the text (text over 20,000 characters is cut, and the full text is saved to `output_path` or `<file>.ocr.txt` next to the input file). `output="pdf"` saves a searchable PDF to `output_path` or `<file>.searchable.pdf`. |
| `ocr_pdf(path, output="text", output_path=None)` | The same tool as `ocr_file` under its earlier name, kept so existing setups keep working. |
| `get_document(document_id, output="status", output_path=None)` | Status and page counts of a document; with `output="text"` or `"pdf"`, waits up to 45 seconds and fetches the finished result. Fetching a result again costs no pages. |
| `list_documents(limit=20)` | The most recent documents in the account, newest first. |
| `delete_document(document_id)` | Deletes a document and its stored files on FastOCR. Local files are not touched. |

Try asking: *"OCR ~/Downloads/scanned-contract.pdf and summarize the termination clause"*,
*"Read the text in /Users/me/Desktop/receipt.jpg"* or
*"Make a searchable copy of /Users/me/archive/1998-letters.pdf"*.

Every processed page uses one page of the account's API allowance; an image is one page. A document that runs out
of pages fails with `buy_pages`; the tool says so and links to the
[developer console](https://fastocr.org/developers/keys#buy-api-pages).

## Errors

Tool errors are written for the agent to act on: a rejected key, an account out of pages
(`buy_pages`), too many documents processing at once (`concurrency_limit`), a missing file, or an
unsupported file type. Each message says what to do next. Error codes are listed in the
[API docs](https://fastocr.org/docs/documents).

## Configuration

| Variable | Purpose |
|---|---|
| `FASTOCR_API_KEY` | Required. Your API key. |
| `FASTOCR_BASE_URL` | Optional. Overrides `https://api.fastocr.org`. |

## Links

- Docs: https://fastocr.org/docs
- API keys and page packs: https://fastocr.org/developers/keys
- Python SDK: https://github.com/fastocr-org/fastocr-python
- Support: support@fastocr.org

## License

MIT
