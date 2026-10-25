<div align="center">

<a href="https://fastocr.org">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/fastocr-org/fastocr-mcp/main/docs/images/logo-dark.png">
    <img src="https://raw.githubusercontent.com/fastocr-org/fastocr-mcp/main/docs/images/logo-light.png" alt="FastOCR" width="200">
  </picture>
</a>

<h3>OCR any scanned PDF or image from Claude, Cursor and other MCP clients.</h3>

<p>
<a href="https://github.com/fastocr-org/fastocr-mcp/actions/workflows/ci.yml"><img src="https://github.com/fastocr-org/fastocr-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="https://pypi.org/project/fastocr-mcp/"><img src="https://img.shields.io/pypi/v/fastocr-mcp.svg?label=pypi" alt="PyPI"></a>
<a href="https://pypi.org/project/fastocr-mcp/"><img src="https://img.shields.io/pypi/pyversions/fastocr-mcp.svg" alt="Python"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
</p>

<p>
<a href="https://fastocr.org">Website</a> ·
<a href="https://fastocr.org/docs">Docs</a> ·
<a href="https://fastocr.org/developers/keys">Get an API key</a>
</p>

<img src="https://raw.githubusercontent.com/fastocr-org/fastocr-mcp/main/docs/images/readme-hero.gif" alt="FastOCR reads a scanned page in English, Arabic and Hindi and returns its text" width="800">

</div>

<!-- mcp-name: io.github.fastocr-org/fastocr-mcp -->

An [MCP](https://modelcontextprotocol.io) server that lets your client OCR a local scanned PDF or image over stdio; files go only to the [FastOCR API](https://fastocr.org/docs).

## Quickstart

1. Create an API key in the [developer console](https://fastocr.org/developers/keys).
2. Add the server to Claude Code:

```bash
claude mcp add fastocr -e FASTOCR_API_KEY=your_api_key -- uvx fastocr-mcp
```

3. Ask: *"OCR ~/Scans/contract.pdf"*.

With [uv](https://docs.astral.sh/uv/) there is nothing to install; the client runs `uvx fastocr-mcp`. Prefer pip? Run `pip install fastocr-mcp` and use the command `fastocr-mcp`. Python 3.10 or newer.

## Other clients

Every client needs the same command, `uvx fastocr-mcp`, and your key in `FASTOCR_API_KEY`.

<details>
<summary>Claude Desktop</summary>

Add this to `claude_desktop_config.json` (Settings > Developer > Edit Config), then restart Claude Desktop:

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

</details>

<details>
<summary>Cursor</summary>

Add this to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project):

```json
{
  "mcpServers": {
    "fastocr": {
      "type": "stdio",
      "command": "uvx",
      "args": ["fastocr-mcp"],
      "env": { "FASTOCR_API_KEY": "your_api_key" }
    }
  }
}
```

</details>

<details>
<summary>VS Code</summary>

Add this to `.vscode/mcp.json` in your workspace. VS Code uses `servers`, not `mcpServers`:

```json
{
  "servers": {
    "fastocr": {
      "type": "stdio",
      "command": "uvx",
      "args": ["fastocr-mcp"],
      "env": { "FASTOCR_API_KEY": "your_api_key" }
    }
  }
}
```

</details>

If you installed with pip, use `"command": "fastocr-mcp"` and `"args": []`.

## Examples

Ask your client in plain language:

- *"OCR ~/Downloads/scanned-contract.pdf and summarize the termination clause."*
- *"Read the text in /Users/me/Desktop/receipt.jpg."*
- *"Make a searchable copy of /Users/me/archive/1998-letters.pdf."*
- *"List my last five FastOCR documents."*

<img src="https://raw.githubusercontent.com/fastocr-org/fastocr-mcp/main/docs/images/mcp-conversation.png" alt="An MCP client calls ocr_file on a scanned letter and gets back its text" width="800">

The text above is the unedited output FastOCR returned for a scanned page.

## Tools

| Tool | What it does |
|---|---|
| `ocr_file(path, output="text", output_path=None)` | Uploads a local PDF or image, runs OCR and waits up to 45 seconds; a larger document returns its id for `get_document`. `output="text"` returns the text (text over 20,000 characters is cut, and the full text is saved to `output_path` or `<file>.ocr.txt` next to the input file). `output="pdf"` saves a searchable PDF to `output_path` or `<file>.searchable.pdf`. |
| `ocr_pdf(path, output="text", output_path=None)` | The same tool as `ocr_file` under its earlier name, kept so existing setups keep working. |
| `get_document(document_id, output="status", output_path=None)` | Status and page counts of a document; with `output="text"` or `"pdf"`, waits up to 45 seconds and fetches the finished result. Fetching a result again costs no pages. |
| `list_documents(limit=20)` | The most recent documents in the account, newest first. |
| `get_balance()` | The pages left on the account: free pages (they reset monthly), contract pages if any, and Page Packs, plus the link to buy more. Costs no pages. |
| `delete_document(document_id)` | Deletes a document and its stored files on FastOCR. Local files are not touched. |

## What you get back

| You get | How |
|---|---|
| The text of the document | `ocr_file(path)`, or `get_document(id, output="text")` |
| A searchable PDF | `ocr_file(path, output="pdf")`, saved beside the input |
| Status and page counts | `get_document(id)` |
| Your recent documents | `list_documents()` |

## Languages and files

- 100+ languages, detected automatically. No language setting is needed.
- PDF files up to 1 GiB, and PNG, JPG, JPEG, GIF, WebP and BMP images up to 20 MiB. An image counts as one page.
- Built on the official [`fastocr-sdk`](https://pypi.org/project/fastocr-sdk/) and the official MCP Python SDK.

## Pages and pricing

Any signed-in FastOCR account can create an API key and start right away. Every account gets 50 free pages a month, shared with PDFs on the website; an image is one page. When you need more, buy a Page Pack on the [pricing page](https://fastocr.org/pricing?from=api#packs). Packs and the page balance are the same on the website and in the API; ask your agent to run `get_balance` to see what is left. Accounts process 2 documents at once, or 10 with an API contract or 10,000 or more pages bought. You accept the [API terms](https://fastocr.org/api-terms) with your first key.

<details>
<summary>Errors and configuration</summary>

Tool errors are written for the agent to act on: a rejected key, an account out of pages (`buy_pages`), too many documents processing at once (`concurrency_limit`), a missing file, or an unsupported file type. Each message says what to do next. A document that runs out of pages fails with `buy_pages`; the tool says so and links to the [pricing page](https://fastocr.org/pricing?from=api#packs). Error codes are listed in the [API docs](https://fastocr.org/docs/documents).

| Variable | Purpose |
|---|---|
| `FASTOCR_API_KEY` | Required. Your API key. |
| `FASTOCR_BASE_URL` | Optional. Overrides `https://api.fastocr.org`. |

</details>

## Support and license

Questions: support@fastocr.org. Bugs and requests: [GitHub issues](https://github.com/fastocr-org/fastocr-mcp/issues). Python SDK: [fastocr-python](https://github.com/fastocr-org/fastocr-python). MIT license; see [LICENSE](LICENSE). Made by [FastOCR](https://fastocr.org).
