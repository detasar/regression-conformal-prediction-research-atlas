import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "experiments/regression/manuscript"
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


KG_COUNT_KEYS = {
    "kg_node_count": "node_count",
    "main_article_kg_node_count": "node_count",
    "source_kg_node_count": "node_count",
    "kg_browser_node_count": "node_count",
    "kg_edge_count": "edge_count",
    "source_kg_edge_count": "edge_count",
    "kg_browser_edge_count": "edge_count",
}

FORBIDDEN_STALE_KG_TEXT_PATTERNS = [
    re.compile(r"KG[^\n]{0,80}3,?564", re.IGNORECASE),
    re.compile(r"3,?564[^\n]{0,80}(KG|nodes|edges)", re.IGNORECASE),
    re.compile(r"KG[^\n]{0,80}20,?213", re.IGNORECASE),
    re.compile(r"20,?213[^\n]{0,80}(KG|nodes|edges)", re.IGNORECASE),
    re.compile(r"KG[^\n]{0,80}3,?566", re.IGNORECASE),
    re.compile(r"3,?566[^\n]{0,80}(KG|nodes|edges)", re.IGNORECASE),
    re.compile(r"KG[^\n]{0,80}20,?219", re.IGNORECASE),
    re.compile(r"20,?219[^\n]{0,80}(KG|nodes|edges)", re.IGNORECASE),
]


def iter_json_count_values(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in KG_COUNT_KEYS:
                yield key, child, child_path
            yield from iter_json_count_values(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_json_count_values(child, f"{path}[{index}]")


def test_publication_manuscript_kg_count_metadata_matches_current_snapshot():
    kg = json.loads(KG_QUALITY.read_text(encoding="utf-8"))["graph"]
    mismatches = []

    for path in sorted(MANUSCRIPT.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for key, value, selector in iter_json_count_values(payload):
            if value is None:
                continue
            expected = kg[KG_COUNT_KEYS[key]]
            if value != expected:
                mismatches.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "selector": selector,
                        "key": key,
                        "value": value,
                        "expected": expected,
                    }
                )

    assert mismatches == []


def test_publication_markdown_has_no_stale_kg_snapshot_counts():
    hits = []
    for path in sorted(MANUSCRIPT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_STALE_KG_TEXT_PATTERNS:
            match = pattern.search(text)
            if match:
                hits.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "pattern": pattern.pattern,
                        "match": match.group(0),
                    }
                )

    assert hits == []
