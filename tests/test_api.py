"""Integration tests for the FastAPI surface.

Drives the real engine through `httpx.TestClient` against every fixture in
`examples/inputs/`, plus the negative paths (no-applicable-method, malformed body,
unknown method-weight key).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vc_audit.api import app
from vc_audit.models import TriangulatedValuation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples" / "inputs"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.json"))


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_methods_lists_three_descriptors(client: TestClient) -> None:
    resp = client.get("/methods")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    names = {d["name"] for d in data}
    assert names == {"comps", "last_round", "dcf"}
    for d in data:
        assert d["description"]
        assert isinstance(d["required_inputs"], list)
        assert d["required_inputs"]  # non-empty


@pytest.mark.parametrize("fixture", EXAMPLE_FILES, ids=lambda p: p.name)
def test_post_valuations_json(client: TestClient, fixture: Path) -> None:
    body = json.loads(fixture.read_text())
    resp = client.post("/valuations", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    valuation = TriangulatedValuation.model_validate(resp.json())
    assert valuation.company.name == body["company"]["name"]


@pytest.mark.parametrize("fixture", EXAMPLE_FILES, ids=lambda p: p.name)
def test_post_valuations_markdown(client: TestClient, fixture: Path) -> None:
    body = json.loads(fixture.read_text())
    resp = client.post("/valuations?format=markdown", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "# VC Audit Report" in resp.text


@pytest.mark.parametrize("fixture", EXAMPLE_FILES, ids=lambda p: p.name)
def test_post_valuations_both(client: TestClient, fixture: Path) -> None:
    body = json.loads(fixture.read_text())
    resp = client.post("/valuations?format=both", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    payload = resp.json()
    assert set(payload.keys()) == {"valuation", "markdown_report"}
    valuation = TriangulatedValuation.model_validate(payload["valuation"])
    assert valuation.company.name == body["company"]["name"]
    assert payload["markdown_report"].startswith("# VC Audit Report")


def test_post_valuations_no_applicable_method(client: TestClient) -> None:
    body = {"company": {"name": "Empty Co"}, "as_of_date": "2026-03-31"}
    resp = client.post("/valuations", json=body)
    assert resp.status_code == 422
    assert "No registered method applies" in resp.json()["detail"]


def test_post_valuations_malformed_body(client: TestClient) -> None:
    resp = client.post("/valuations", json={"company": "not-an-object"})
    assert resp.status_code == 422


def test_post_valuations_unknown_method_weight(client: TestClient) -> None:
    body = json.loads((EXAMPLES_DIR / "comps_only.json").read_text())
    body["method_weights"] = {"not_a_method": "1.0"}
    resp = client.post("/valuations", json=body)
    assert resp.status_code == 422
    assert "Unknown method weight key" in resp.json()["detail"]


def test_openapi_schema_lists_endpoints(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/health" in paths
    assert "/methods" in paths
    assert "/valuations" in paths
