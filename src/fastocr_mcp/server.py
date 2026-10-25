"""MCP server exposing the FastOCR Document OCR API as tools."""
import json
import tempfile
from pathlib import Path
from typing import Annotated, Any, Callable, Dict, Literal, Optional

from fastocr_sdk import (
    AsyncFastOCR,
    AuthenticationError,
    Balance,
    DocumentFailedError,
    DocumentJob,
    FastOCRError,
    NotFoundError,
    PollingTimeoutError,
    RateLimitError,
)
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from ._version import __version__

DOCS_URL = "https://fastocr.org/docs"
KEYS_URL = "https://fastocr.org/developers/keys"
BUY_PAGES_URL = "https://fastocr.org/pricing?from=api#packs"
MAX_INLINE_CHARS = 20_000
# Stay under the 60 s request timeout many MCP clients use; longer documents are resumed with get_document.
WAIT_SECONDS = 45.0

ClientFactory = Callable[[], AsyncFastOCR]
USER_AGENT = f"fastocr-mcp/{__version__}"


def default_client() -> AsyncFastOCR:
    """An SDK client whose User-Agent names this server, so API access logs can count MCP traffic."""
    client = AsyncFastOCR()
    sdk_agent = client._http.headers.get("User-Agent", "")
    client._http.headers["User-Agent"] = f"{USER_AGENT} {sdk_agent}".strip()
    return client

INSTRUCTIONS = f"""\
FastOCR extracts text from scanned PDFs and images and makes searchable PDFs, in 100+ languages.
Use ocr_file for a local PDF, PNG, JPG, GIF, WebP or BMP file; pass an absolute path. Every processed
page (an image is one page) uses one page of the account's FastOCR page balance, so do not OCR the
same file twice. Use get_balance to see how many pages are left. The server reads the API key
from the FASTOCR_API_KEY environment variable. Docs: {DOCS_URL}"""

DocumentId = Annotated[str, Field(description="The document id returned by ocr_file or list_documents.")]
InputPath = Annotated[str, Field(description="Absolute path to a local PDF, PNG, JPG, JPEG, GIF, WebP or BMP file.")]
OcrOutput = Annotated[
    Literal["text", "pdf"],
    Field(description="'text' returns the extracted text; 'pdf' saves a searchable PDF with a text layer."),
]
OutputPath = Annotated[
    Optional[str],
    Field(description="Optional absolute path for the result file. An existing file there is replaced."),
]


def explain(error: FastOCRError) -> str:
    """Turn an SDK error into a message an AI agent or a developer can act on."""
    if isinstance(error, AuthenticationError):
        return (
            "FastOCR did not accept the API key, or none is set. Set FASTOCR_API_KEY in this MCP server's "
            f"environment to a key from {KEYS_URL} (any signed-in account can create one "
            "after accepting the API terms)."
        )
    if error.code == "buy_pages":
        document = f" (document {error.document_id})" if isinstance(error, DocumentFailedError) else ""
        return (
            f"The FastOCR account is out of pages{document}. Buy pages at {BUY_PAGES_URL}, "
            "then run ocr_file again."
        )
    if error.code == "concurrency_limit":
        return (
            "Too many documents are already processing for this FastOCR account. Wait until one "
            "finishes (check list_documents), then try again. Accounts with an API contract or 10,000 or "
            f"more pages bought can process 10 documents at once: {BUY_PAGES_URL}"
        )
    if isinstance(error, RateLimitError):
        wait = int(error.retry_after) if error.retry_after else 60
        return f"FastOCR is rate limiting requests. Try again in {wait} seconds."
    if isinstance(error, NotFoundError):
        return "No document with that id exists in this FastOCR account."
    if error.code == "document_processing":
        return "The document is still processing and cannot be deleted yet. Try again when it has finished."
    if isinstance(error, DocumentFailedError):
        advice = "Trying again may work." if error.retryable else "Trying the same file again will not help."
        return f"OCR failed for document {error.document_id} (code: {error.code}): {error.message} {advice}"
    return f"FastOCR request failed: {error}. See {DOCS_URL}"


def _summary(job: DocumentJob) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "document_id": job.id,
        "status": job.status,
        "pages_total": job.pages_total,
        "pages_billed": job.pages_billed,
        "text_available": job.outputs.text_available,
        "pdf_available": job.outputs.pdf_available,
    }
    if job.external_id:
        summary["external_id"] = job.external_id
    if job.error:
        summary["error"] = {"code": job.error.code, "message": job.error.message, "retryable": job.error.retryable}
    if job.is_failed:
        summary["next_step"] = explain(_failure(job))
    return summary


def _balance_summary(balance: Balance) -> Dict[str, Any]:
    return {
        "pages_remaining": balance.pages_remaining,
        "free_pages_remaining": balance.free_pages_remaining,
        "free_pages_per_month": balance.free_pages_per_month,
        "free_pages_reset_at": balance.free_pages_reset_at,
        "contract_pages_remaining": balance.contract_pages_remaining,
        "contract_pages_per_month": balance.contract_pages_per_month,
        "statement_pages_remaining": balance.statement_pages_remaining,
        "buy_pages_url": BUY_PAGES_URL,
    }


def _partial_note(job: DocumentJob) -> str:
    if not job.is_partial:
        return ""
    return (
        f"\nNote: only {job.pages_billed} of {job.pages_total} pages were processed because the account "
        f"ran out of pages. Buy pages at {BUY_PAGES_URL} and run ocr_file again to process the whole file."
    )


def _beside(stem: Path, suffix: str) -> Path:
    return stem.with_name(stem.name + suffix)


def _write_text(path: Path, text: str) -> Path:
    path = path.expanduser()
    path.write_text(text, encoding="utf-8")
    return path


async def _deliver(
    client: AsyncFastOCR,
    job: DocumentJob,
    output: str,
    output_path: Optional[str],
    default_stem: Path,
) -> str:
    header = f"Document {job.id}: {job.status}, {job.pages_billed} page(s) billed."
    if output == "pdf":
        if not job.outputs.pdf_available:
            raise ToolError(f"Document {job.id} has no searchable PDF. Use output='text' instead.")
        destination = Path(output_path).expanduser() if output_path else _beside(default_stem, ".searchable.pdf")
        await client.documents.download_searchable_pdf(job.id, destination)
        return f"{header}\nSearchable PDF saved to {destination}{_partial_note(job)}"

    text = await client.documents.get_text(job.id)
    saved = None
    if output_path:
        saved = _write_text(Path(output_path), text)
    elif len(text) > MAX_INLINE_CHARS:
        saved = _write_text(_beside(default_stem, ".ocr.txt"), text)
    if len(text) > MAX_INLINE_CHARS:
        return (
            f"{header}{_partial_note(job)}\nThe text has {len(text)} characters; the first "
            f"{MAX_INLINE_CHARS} are below. The full text is in {saved}.\n\n{text[:MAX_INLINE_CHARS]}"
        )
    where = f"\nFull text saved to {saved}." if saved else ""
    return f"{header}{where}{_partial_note(job)}\n\n{text}"


def _output_file(output_path: Optional[str], source: Optional[Path] = None) -> None:
    if not output_path:
        return
    target = Path(output_path).expanduser()
    if not target.is_absolute():
        raise ToolError(f"output_path must be an absolute path, not '{output_path}'.")
    if source and target.resolve() == source.resolve():
        raise ToolError("output_path must differ from the input file.")


SUPPORTED_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def _source(path: str) -> Path:
    source = Path(path).expanduser()
    if not source.is_absolute():
        raise ToolError(f"Pass an absolute path to the file, not '{path}'.")
    if not source.is_file():
        raise ToolError(f"No file at {source}.")
    if source.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ToolError("FastOCR's API accepts PDF, PNG, JPG, JPEG, GIF, WebP and BMP files.")
    return source


def create_server(client_factory: ClientFactory = default_client) -> MCPServer:
    server = MCPServer(
        "fastocr",
        title="FastOCR",
        instructions=INSTRUCTIONS,
        website_url=DOCS_URL,
        version=__version__,
    )

    async def run(action: Callable[[AsyncFastOCR], Any]) -> Any:
        try:
            async with client_factory() as client:
                return await action(client)
        except FastOCRError as error:
            raise ToolError(explain(error)) from error
        except OSError as error:
            raise ToolError(f"Could not read or write a local file: {error}") from error

    async def ocr(path: str, output: str, output_path: Optional[str]) -> str:
        source = _source(path)
        _output_file(output_path, source)

        async def action(client: AsyncFastOCR) -> str:
            try:
                job = await client.documents.process(source, timeout=WAIT_SECONDS)
            except PollingTimeoutError as pending:
                return (
                    f"Document {pending.document_id} is still processing. Call get_document with "
                    f"document_id='{pending.document_id}' and output='{output}' to wait for and fetch the result. "
                    "Do not run ocr_file on the same file again."
                )
            return await _deliver(client, job, output, output_path, source.with_suffix(""))

        result: str = await run(action)
        return result

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True))
    async def ocr_file(
        path: InputPath,
        output: OcrOutput = "text",
        output_path: OutputPath = None,
    ) -> str:
        """OCR a local PDF or image with FastOCR and return its text or save a searchable PDF.

        Uploads the file, runs OCR and waits up to 45 seconds. With output='text' the
        text is returned; text longer than 20,000 characters is cut, and the full text is
        written to output_path or to <file>.ocr.txt next to the input file. With
        output='pdf' the searchable PDF is saved to output_path or to <file>.searchable.pdf
        next to the input file. Either default file replaces an earlier result with the
        same name. Each processed page uses one page of the account's balance; an
        image is one page. Large documents take longer: then this returns a document id,
        and get_document with the same output fetches the result. Never call ocr_file
        again for that file, which bills it again.
        """
        return await ocr(path, output, output_path)

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True))
    async def ocr_pdf(
        path: InputPath,
        output: OcrOutput = "text",
        output_path: OutputPath = None,
    ) -> str:
        """The same tool as ocr_file, kept under its earlier name. Prefer ocr_file."""
        return await ocr(path, output, output_path)

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True))
    async def get_document(
        document_id: DocumentId,
        output: Annotated[
            Literal["status", "text", "pdf"],
            Field(description="'status' (default) returns the status at once; 'text' or 'pdf' waits for the document to finish and fetches the result."),
        ] = "status",
        output_path: OutputPath = None,
    ) -> str:
        """Get a FastOCR document's status, and optionally its text or searchable PDF.

        Statuses: awaiting_upload, processing, completed, partial (the account ran out of
        pages partway), failed. With output='text' or 'pdf' this waits up to 45 seconds;
        if the document is still processing, call it again. Fetching a result again costs
        no pages. Without output_path, long text and PDFs are saved in the system temp
        directory.
        """
        _output_file(output_path)

        async def action(client: AsyncFastOCR) -> str:
            if output == "status":
                return _format(_summary(await client.documents.get(document_id)))
            try:
                job = await client.documents.wait_for_completion(document_id, timeout=WAIT_SECONDS)
            except PollingTimeoutError:
                return f"Document {document_id} is still processing. Call get_document again with the same arguments."
            default_stem = Path(tempfile.gettempdir()) / f"fastocr-{job.id}"
            return await _deliver(client, job, output, output_path, default_stem)

        result: str = await run(action)
        return result

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def list_documents(
        limit: Annotated[int, Field(ge=1, le=100, description="How many documents to return, newest first (1 to 100).")] = 20,
    ) -> str:
        """List the most recent documents in the FastOCR account with their status and page counts."""

        async def action(client: AsyncFastOCR) -> str:
            page = await client.documents.list(limit=limit)
            if not page.documents:
                return "No documents in this FastOCR account yet."
            return "\n".join(_format(_summary(job)) for job in page.documents)

        result: str = await run(action)
        return result

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    async def get_balance() -> str:
        """Get how many pages the FastOCR account can still process. Costs no pages.

        Documents spend free pages first (they reset monthly), then contract pages, then
        Page Packs. pages_remaining counts the Page Packs only, so add the free and
        contract pages for the total. contract_* are omitted without an API contract.
        statement_pages_remaining is a separate balance that OCR does not spend. Check this
        before OCRing a large PDF; buy_pages_url is where to add pages.
        """

        async def action(client: AsyncFastOCR) -> str:
            return _format(_balance_summary(await client.get_balance()))

        result: str = await run(action)
        return result

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True))
    async def delete_document(document_id: DocumentId) -> str:
        """Permanently delete a FastOCR document and its stored files (original, text, searchable PDF).

        A document that is still processing cannot be deleted. Local files are not touched.
        """

        async def action(client: AsyncFastOCR) -> str:
            await client.documents.delete(document_id)
            return f"Document {document_id} is being deleted."

        result: str = await run(action)
        return result

    return server


def _failure(job: DocumentJob) -> DocumentFailedError:
    error = job.error
    return DocumentFailedError(
        (error.message if error else "") or "Document processing failed",
        document_id=job.id,
        code=error.code if error else "processing_failed",
        retryable=error.retryable if error else True,
    )


def _format(summary: Dict[str, Any]) -> str:
    return json.dumps({key: value for key, value in summary.items() if value is not None})


def main() -> None:
    create_server().run()
