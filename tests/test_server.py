"""Every tool through a real MCP client session, with the FastOCR API mocked at the HTTP layer."""
import json

import httpx
import pytest
import respx
from fastocr_sdk import AsyncFastOCR
from mcp import Client

from fastocr_mcp import server as server_module
from fastocr_mcp.server import KEYS_URL, MAX_INLINE_CHARS, create_server

BASE_URL = "https://api.test"
UPLOAD_URL = "https://s3.test/uploads/original.pdf?X-Amz-Signature=sig"
TEXT_URL = "https://s3.test/out/ocr-text.txt?X-Amz-Signature=sig"
PDF_URL = "https://s3.test/out/searchable.pdf?X-Amz-Signature=sig"
DOC = "doc_1"


def completed(**extra):
    return {
        "id": DOC,
        "status": "completed",
        "external_id": None,
        "pages_billed": 2,
        "pages_total": 2,
        "outputs": {"text": {"available": True}, "pdf": {"available": True}},
        **extra,
    }


def failed(code, retryable=False):
    return {
        "id": DOC,
        "status": "failed",
        "external_id": None,
        "error": {"type": "x", "code": code, "message": "Server says no.", "retryable": retryable},
    }


def factory():
    client = AsyncFastOCR(api_key="fok_test", base_url=BASE_URL, max_retries=0)

    async def no_sleep(seconds):
        return None

    client._sleep = no_sleep
    return client


async def call(tool, client_factory=factory, **arguments):
    async with Client(create_server(client_factory)) as client:
        result = await client.call_tool(tool, arguments)
    return result.is_error, result.content[0].text


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "scan.v2.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path


@pytest.fixture
def api():
    with respx.mock(assert_all_called=False) as router:
        yield router


def mock_flow(api, job, text="Hello from page one.", start=None):
    api.post(f"{BASE_URL}/v1/documents").respond(
        201, json={"id": DOC, "status": "awaiting_upload", "upload_url": UPLOAD_URL, "expires_at": "2026-10-20T12:00:00Z"}
    )
    upload = api.put(UPLOAD_URL).respond(200)
    api.post(f"{BASE_URL}/v1/documents/{DOC}/start").mock(return_value=start or httpx.Response(202, json={"status": "processing"}))
    api.get(f"{BASE_URL}/v1/documents/{DOC}").mock(
        side_effect=[httpx.Response(200, json={"id": DOC, "status": "processing"}), httpx.Response(200, json=job)]
    )
    api.get(f"{BASE_URL}/v1/documents/{DOC}/output", params={"format": "text"}).respond(
        200, json={"format": "text", "url": TEXT_URL, "expires_at": "x"}
    )
    api.get(f"{BASE_URL}/v1/documents/{DOC}/output", params={"format": "pdf"}).respond(
        200, json={"format": "pdf", "url": PDF_URL, "expires_at": "x"}
    )
    api.get(TEXT_URL).respond(200, content=text.encode("utf-8"))
    api.get(PDF_URL).respond(200, content=b"%PDF searchable")
    return upload


async def test_lists_the_tools_with_descriptions():
    async with Client(create_server(factory)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert set(tools) == {"ocr_file", "ocr_pdf", "get_document", "list_documents", "delete_document"}
    assert all(tool.description for tool in tools.values())
    assert tools["ocr_file"].input_schema["required"] == ["path"]
    assert tools["ocr_pdf"].input_schema["properties"] == tools["ocr_file"].input_schema["properties"]
    assert tools["delete_document"].annotations.destructive_hint is True
    assert tools["get_document"].annotations.read_only_hint is False
    assert tools["list_documents"].annotations.read_only_hint is True


async def test_ocr_file_returns_text(api, pdf):
    upload = mock_flow(api, completed())
    is_error, text = await call("ocr_file", path=str(pdf))
    assert not is_error
    assert upload.calls.last.request.content == b"%PDF-1.4 test"
    assert "Hello from page one." in text and "2 page(s) billed" in text
    assert not (pdf.parent / "scan.v2.ocr.txt").exists()


@pytest.mark.parametrize("tool", ["ocr_file", "ocr_pdf"])
@pytest.mark.parametrize("name,content_type", [("photo.png", "image/png"), ("receipt.JPG", "image/jpeg")])
async def test_images_are_uploaded_with_their_content_type(api, tmp_path, tool, name, content_type):
    image = tmp_path / name
    image.write_bytes(b"image bytes")
    upload = mock_flow(api, completed(pages_billed=1, pages_total=1))
    is_error, text = await call(tool, path=str(image), output="pdf")
    assert not is_error
    assert upload.calls.last.request.headers["Content-Type"] == content_type
    assert (tmp_path / (image.stem + ".searchable.pdf")).read_bytes() == b"%PDF searchable"
    assert "1 page(s) billed" in text


async def test_ocr_file_cuts_long_text_and_saves_the_full_text_beside_the_pdf(api, pdf):
    long_text = "a" * MAX_INLINE_CHARS + "TAIL"
    mock_flow(api, completed())
    api.get(TEXT_URL).respond(200, content=long_text.encode())
    is_error, text = await call("ocr_file", path=str(pdf))
    saved = pdf.parent / "scan.v2.ocr.txt"
    assert not is_error
    assert saved.read_text() == long_text
    assert str(saved) in text and "TAIL" not in text


async def test_ocr_file_saves_searchable_pdf(api, pdf, tmp_path):
    mock_flow(api, completed())
    is_error, text = await call("ocr_file", path=str(pdf), output="pdf")
    saved = tmp_path / "scan.v2.searchable.pdf"
    assert not is_error
    assert saved.read_bytes() == b"%PDF searchable"
    assert str(saved) in text


async def test_partial_result_says_how_to_get_the_rest(api, pdf):
    mock_flow(api, completed(status="partial", is_truncated=True, pages_billed=1, pages_total=3))
    is_error, text = await call("ocr_file", path=str(pdf))
    assert not is_error
    assert "only 1 of 3 pages" in text and f"{KEYS_URL}#buy-api-pages" in text


@pytest.mark.parametrize(
    "case, expected",
    [
        ("buy_pages", f"{KEYS_URL}#buy-api-pages"),
        ("bad_key", "FASTOCR_API_KEY"),
        ("concurrency_limit", "list_documents"),
        ("unreadable", "will not help"),
    ],
)
async def test_api_errors_become_actionable_messages(api, pdf, case, expected):
    if case == "bad_key":
        api.post(f"{BASE_URL}/v1/documents").respond(403, json={"message": "Forbidden"})
    elif case == "concurrency_limit":
        mock_flow(api, completed(), start=httpx.Response(
            429, json={"error": {"type": "rate_limit", "code": "concurrency_limit", "message": "busy"}}
        ))
    else:
        mock_flow(api, failed("buy_pages" if case == "buy_pages" else "unreadable_document"))
    is_error, text = await call("ocr_file", path=str(pdf))
    assert is_error
    assert expected in text


async def test_missing_api_key_explains_where_to_get_one(pdf, monkeypatch):
    monkeypatch.delenv("FASTOCR_API_KEY", raising=False)
    is_error, text = await call("ocr_file", client_factory=AsyncFastOCR, path=str(pdf))
    assert is_error and KEYS_URL in text


@pytest.mark.parametrize(
    "name, output_path",
    [("relative.pdf", None), ("/no/such/file.pdf", None), ("notes.txt", None), ("scan.pdf", "out.txt"), ("scan.pdf", "scan.pdf")],
)
async def test_bad_paths_are_rejected_before_any_request(api, tmp_path, name, output_path):
    path = name
    if not name.startswith(("/", "relative")):
        path = str(tmp_path / name)
        (tmp_path / name).write_text("x")
    if output_path == name:
        output_path = path
    arguments = {"path": path} if output_path is None else {"path": path, "output_path": output_path}
    is_error, _ = await call("ocr_file", **arguments)
    assert is_error
    assert not api.calls


async def test_still_processing_returns_the_document_id(api, pdf, monkeypatch):
    monkeypatch.setattr(server_module, "WAIT_SECONDS", 0.0)
    mock_flow(api, completed())
    is_error, text = await call("ocr_file", path=str(pdf))
    assert not is_error
    assert f"document_id='{DOC}'" in text and "get_document" in text

    api.get(f"{BASE_URL}/v1/documents/{DOC}").respond(200, json={"id": DOC, "status": "processing"})
    is_error, text = await call("get_document", document_id=DOC, output="text")
    assert not is_error and "still processing" in text


async def test_get_document_status_and_text(api, tmp_path):
    api.get(f"{BASE_URL}/v1/documents/{DOC}").respond(200, json=failed("buy_pages"))
    _, status = await call("get_document", document_id=DOC)
    assert json.loads(status)["status"] == "failed"
    assert KEYS_URL in json.loads(status)["next_step"]

    mock_flow(api, completed())
    api.get(f"{BASE_URL}/v1/documents/{DOC}").respond(200, json=completed())
    out = tmp_path / "out.txt"
    is_error, text = await call("get_document", document_id=DOC, output="text", output_path=str(out))
    assert not is_error
    assert out.read_text() == "Hello from page one." and "Hello from page one." in text

    api.get(f"{BASE_URL}/v1/documents/{DOC}").respond(200, json=completed(outputs={"text": {"available": True}}))
    is_error, text = await call("get_document", document_id=DOC, output="pdf")
    assert is_error and "no searchable PDF" in text


async def test_list_and_delete_documents(api):
    api.get(f"{BASE_URL}/v1/documents", params={"limit": "5"}).respond(
        200, json={"documents": [completed(), failed("timeout", retryable=True)], "next_cursor": None}
    )
    _, listing = await call("list_documents", limit=5)
    rows = [json.loads(line) for line in listing.splitlines()]
    assert [row["status"] for row in rows] == ["completed", "failed"]

    api.delete(f"{BASE_URL}/v1/documents/{DOC}").respond(
        409, json={"error": {"type": "conflict", "code": "document_processing", "message": "busy"}}
    )
    is_error, text = await call("delete_document", document_id=DOC)
    assert is_error and "still processing" in text

    api.delete(f"{BASE_URL}/v1/documents/{DOC}").respond(202, json={"status": "deleting"})
    is_error, text = await call("delete_document", document_id=DOC)
    assert not is_error and "being deleted" in text


async def test_default_client_names_the_mcp_server_in_user_agent(api, monkeypatch):
    monkeypatch.setenv("FASTOCR_API_KEY", "fok_test")
    monkeypatch.setenv("FASTOCR_BASE_URL", BASE_URL)
    route = api.get(f"{BASE_URL}/v1/documents", params={"limit": "1"}).respond(
        200, json={"documents": [], "next_cursor": None}
    )
    _, text = await call("list_documents", client_factory=server_module.default_client, limit=1)
    assert "No documents" in text
    agent = route.calls.last.request.headers["User-Agent"]
    assert agent.startswith(f"{server_module.USER_AGENT} fastocr-python/")
