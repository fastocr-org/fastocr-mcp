"""FastOCR MCP server: OCR local PDFs from any MCP client."""

from ._version import __version__
from .server import create_server, main

__all__ = ["__version__", "create_server", "main"]
