"""server.json must validate against the MCP Registry schema and agree with the package."""
import json
import re
from pathlib import Path

import jsonschema

from fastocr_mcp import __version__

ROOT = Path(__file__).resolve().parent.parent
SERVER = json.loads((ROOT / "server.json").read_text())


def test_server_json_matches_registry_schema():
    schema = json.loads((Path(__file__).parent / "server.schema.json").read_text())
    assert SERVER["$schema"] == schema["$id"]
    jsonschema.validate(SERVER, schema)


def test_versions_names_and_links_agree():
    pyproject = (ROOT / "pyproject.toml").read_text()
    package = SERVER["packages"][0]
    assert SERVER["version"] == package["version"] == __version__
    assert f'name = "{package["identifier"]}"' in pyproject
    assert 'Documentation = "https://fastocr.org/docs"\n' in pyproject
    readme = (ROOT / "README.md").read_text()
    assert re.search(r"mcp-name: (\S+) -->", readme).group(1) == SERVER["name"]
    assert "https://fastocr.org/docs" in readme and "https://fastocr.org/developers/keys" in readme
