import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = (
    ROOT
    / "experiments/regression/scripts/audit_manuscript_manifest_completeness.py"
)


def load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "audit_manuscript_manifest_completeness", AUDIT_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_manifest(path: Path, *, include_selection: bool = True) -> None:
    selection = (
        """
## Selection And Multiplicity Status

- Predeclared operating criterion: exploratory only.
- Ranking scope: one dataset, one model, one method, one seed, and nominal
  0.90 coverage target.
- Multiplicity scope: one atomic row before aggregation.
- Tie-break rule: no method may be promoted.
- Exploratory ranking label: completed-ledger readings are exploratory only.
- Post-selection claim boundary: No method superiority claim is supported.
- Sensitivity or holdout validation: paired sensitivity evidence is scoped to
  this manifest and is not a final selection rule.
"""
        if include_selection
        else ""
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# Publication Readiness Manifest: Demo

Schema:
`experiments/regression/catalogs/manuscript_evidence_manifest_schema.json`
(`cpfi_regression_manuscript_evidence_manifest_v1`).

Status: setup-only bundle.

## Identity

- Experiment id: `demo`.

## Scientific Question

Out of scope:

- final-selection claims.

## Design

- CQR boundary: fixed GradientBoostingRegressor quantile backend.
- Venn-Abers boundary: fast `venn_abers_quantile` is diagnostic negative evidence only; it undercovers and is not Venn-Abers regression validation evidence.

## Data Evidence

- Bounded-support policy: no bounded-support validity claim.

## Model Evidence

- Model family: one model.

## Conformal Evidence

- Method registry entry: present.

{selection}
## Split, Leakage, And Duplicate Controls

- feature-leakage audit: pending.
- endpoint audit: pending.
- claim-register update: pending.

## Metric Contract

No method is promoted solely because it has the smallest score.

## Promotion Gates

- complete ledger: pending.
""",
        encoding="utf-8",
    )


def write_index(root: Path, manifest_path: Path) -> None:
    path = root / "experiments/regression/catalogs/manuscript_bundle_index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "test",
                "bundle_summary": {
                    "manifest_count": 1,
                    "completed_with_caveats_count": 1,
                    "active_run_count": 0,
                    "blocked_or_pending_count": 0,
                },
                "bundles": [
                    {
                        "bundle_id": "demo",
                        "status": "completed_with_caveats",
                        "manifest_path": manifest_path.relative_to(root).as_posix(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_manifest_completeness_passes_for_required_scientific_sections(tmp_path):
    audit = load_audit_module()
    manifest = tmp_path / "experiments/regression/reports/demo/publication_readiness_manifest.md"
    write_manifest(manifest)
    write_index(tmp_path, manifest)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "pass"
    assert payload["summary"]["manifest_count"] == 1
    assert payload["bundle_index"]["status"] == "pass"
    assert payload["bundle_index"]["summary_mismatches"] == {}
    assert payload["summary"]["selection_multiplicity_all_fields_covered"] is True
    assert payload["rows"][0]["selection_multiplicity_evidence"][
        "covered_field_count"
    ] == 8


def test_manifest_completeness_fails_when_selection_multiplicity_is_missing(tmp_path):
    audit = load_audit_module()
    manifest = tmp_path / "experiments/regression/reports/demo/publication_readiness_manifest.md"
    write_manifest(manifest, include_selection=False)
    write_index(tmp_path, manifest)

    payload = audit.build_payload(tmp_path)

    assert payload["summary"]["overall_status"] == "fail"
    assert "## Selection And Multiplicity Status" in payload["rows"][0][
        "missing_required_sections"
    ]
    assert "Predeclared operating criterion" in payload["rows"][0][
        "missing_required_tokens"
    ]
    assert payload["rows"][0]["selection_multiplicity_evidence"]["status"] == "fail"


def test_checked_in_manifests_have_paper_readiness_contracts():
    audit = load_audit_module()

    payload = audit.build_payload(ROOT)

    assert payload["summary"]["overall_status"] == "pass"
    assert payload["summary"]["manifest_count"] >= 7
    assert payload["bundle_index"]["summary_mismatches"] == {}
    assert payload["summary"]["selection_multiplicity_all_fields_covered"] is True
    assert payload["summary"]["selection_multiplicity_manifest_fail_count"] == 0


def test_bundle_index_summary_counts_are_recomputed(tmp_path):
    audit = load_audit_module()
    manifest = tmp_path / "experiments/regression/reports/demo/publication_readiness_manifest.md"
    write_manifest(manifest)
    write_index(tmp_path, manifest)

    index_path = tmp_path / "experiments/regression/catalogs/manuscript_bundle_index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["bundle_summary"]["completed_with_caveats_count"] = 0
    index_path.write_text(json.dumps(payload), encoding="utf-8")

    result = audit.build_payload(tmp_path)

    assert result["bundle_index"]["status"] == "fail"
    assert result["bundle_index"]["summary_mismatches"] == {
        "completed_with_caveats_count": {"declared": 0, "computed": 1}
    }
