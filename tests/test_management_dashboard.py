"""Tests for the management dashboard PBIR generator.

The generator is pure: it takes the parts list Fabric returns from getDefinition
and returns the parts list to send to updateDefinition. Everything here runs
offline; the PBIR schemas under tests/schemas are the vendored Microsoft contract.
"""
import base64
import json
import pathlib

import pytest
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

import management_dashboard as md

SCHEMAS = pathlib.Path(__file__).parent / "schemas"
SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"


def _retrieve(uri: str) -> Resource:
    rel = uri.replace(SCHEMA_BASE, "")
    name = (
        rel.replace("/schema.json", "")
        .replace("/schema-embedded.json", "-embedded")
        .replace("/schema.embedded.json", "-embedded")
        .replace("/", "_")
        + ".json"
    )
    return Resource.from_contents(json.loads((SCHEMAS / name).read_text()), default_specification=DRAFT7)


REGISTRY = Registry(retrieve=_retrieve)


def _part(path: str, obj) -> dict:
    return {"path": path, "payload": base64.b64encode(json.dumps(obj).encode()).decode(), "payloadType": "InlineBase64"}


def _decode(part: dict):
    return json.loads(base64.b64decode(part["payload"]))


@pytest.fixture(scope="module")
def base_parts():
    """What Fabric hands back for the current report: metadata plus the old pages."""
    return [
        _part("definition.pbir", {"version": "4.0", "datasetReference": {"byConnection": {"connectionString": "x"}}}),
        _part("definition/version.json", {"$schema": SCHEMA_BASE + "versionMetadata/1.0.0/schema.json", "version": "2.0.0"}),
        _part("definition/report.json", {"$schema": SCHEMA_BASE + "report/3.3.0/schema.json", "themeCollection": {"baseTheme": {"name": "Fluent2-CY26SU10", "type": "SharedResources", "reportVersionAtImport": {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"}}}}),
        _part("definition/pages/pages.json", {"$schema": SCHEMA_BASE + "pagesMetadata/1.1.0/schema.json", "pageOrder": ["oldpage"], "activePageName": "oldpage"}),
        _part("definition/pages/oldpage/page.json", {"name": "oldpage", "displayName": "Old"}),
        _part("definition/pages/oldpage/visuals/old_slicer/visual.json", {"name": "old_slicer", "visual": {"visualType": "slicer"}}),
    ]


@pytest.fixture(scope="module")
def parts(base_parts):
    return md.build_parts(base_parts)


@pytest.fixture(scope="module")
def by_path(parts):
    return {p["path"]: _decode(p) for p in parts if p["path"].endswith(".json")}


def test_every_generated_json_part_validates_against_its_declared_schema(by_path):
    failures = []
    for path, doc in by_path.items():
        schema_uri = doc.get("$schema")
        if not schema_uri:
            continue
        validator = Draft7Validator(_retrieve(schema_uri).contents, registry=REGISTRY)
        for err in validator.iter_errors(doc):
            failures.append(f"{path}: {'/'.join(map(str, err.absolute_path))}: {err.message[:160]}")
    assert not failures, "\n".join(failures)


def test_page_holds_a_title_and_exactly_four_charts(by_path):
    page_name = by_path["definition/pages/pages.json"]["pageOrder"][0]
    visuals = [doc for path, doc in by_path.items() if path.startswith(f"definition/pages/{page_name}/visuals/")]
    types = sorted(v["visual"]["visualType"] for v in visuals)
    assert types.count("textbox") == 1
    charts = [t for t in types if t != "textbox"]
    assert len(charts) == 4, types
    assert not {"slicer", "tableEx", "card"} & set(charts), types


def test_pages_metadata_points_to_all_pages(by_path, parts):
    meta = by_path["definition/pages/pages.json"]
    assert len(meta["pageOrder"]) == 3
    assert meta["pageOrder"] == [md.PAGE_NAME, md.PAGE_2_NAME, md.PAGE_3_NAME]
    for p in meta["pageOrder"]:
        assert f"definition/pages/{p}/page.json" in by_path
    assert not any(p["path"].startswith("definition/pages/oldpage") for p in parts)


def test_page_2_holds_governance_layout(by_path):
    visuals = [doc for path, doc in by_path.items() if path.startswith(f"definition/pages/{md.PAGE_2_NAME}/visuals/")]
    types = [v["visual"]["visualType"] for v in visuals]
    assert types.count("textbox") == 1
    assert types.count("card") == 4
    assert types.count("tableEx") == 2
    assert types.count("clusteredBarChart") == 1


def test_page_3_holds_proveedores_layout(by_path):
    visuals = [doc for path, doc in by_path.items() if path.startswith(f"definition/pages/{md.PAGE_3_NAME}/visuals/")]
    types = [v["visual"]["visualType"] for v in visuals]
    assert types.count("textbox") == 1
    assert types.count("card") == 5
    assert types.count("tableEx") == 2
    assert types.count("clusteredBarChart") == 1


def test_report_metadata_from_the_base_definition_is_kept(parts):
    kept = {p["path"] for p in parts}
    assert {"definition.pbir", "definition/version.json", "definition/report.json"} <= kept


def test_every_balance_measure_excludes_subtotal_accounts(by_path):
    ext = by_path["definition/reportExtensions.json"]
    measures = [m for e in ext["entities"] for m in e["measures"]]
    assert measures
    for m in measures:
        if "netChange" in m["expression"]:
            assert 'accounts[accountType] = "Posting"' in m["expression"], m["name"]


def test_every_chart_measure_exists_in_the_extension(by_path):
    ext = by_path["definition/reportExtensions.json"]
    defined = {(e["name"], m["name"]) for e in ext["entities"] for m in e["measures"]}
    page_name = by_path["definition/pages/pages.json"]["pageOrder"][0]
    used = set()

    def walk(o):
        if isinstance(o, dict):
            if "Measure" in o and o["Measure"]["Expression"]["SourceRef"].get("Schema") == "extension":
                used.add((o["Measure"]["Expression"]["SourceRef"]["Entity"], o["Measure"]["Property"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for path, doc in by_path.items():
        if path.startswith(f"definition/pages/{page_name}/visuals/"):
            walk(doc)
    assert used, "charts should be driven by report-level measures"
    assert used <= defined, used - defined
