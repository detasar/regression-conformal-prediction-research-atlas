from pathlib import Path

import yaml

from experiments.regression.scripts import backfill_legacy_claim_guards as backfill


def test_patch_quality_controls_inserts_before_logging():
    text = """experiment_id: toy_v0
cp_methods:
  - cqr
logging:
  ledger: results/ledger.jsonl
"""

    patched = backfill.patch_quality_controls(
        text,
        {backfill.CQR_GUARD: True, backfill.VA_GUARD: True},
    )

    assert "quality_controls:\n" in patched
    assert "  interpret_cqr_as_fixed_quantile_backend: true\n" in patched
    assert "  forbid_validated_venn_abers_regression_claims: true\n" in patched
    assert patched.index("quality_controls:") < patched.index("logging:")
    parsed = yaml.safe_load(patched)
    assert parsed["quality_controls"][backfill.CQR_GUARD] is True
    assert parsed["quality_controls"][backfill.VA_GUARD] is True


def test_patch_quality_controls_extends_existing_block():
    text = """experiment_id: toy_v0
quality_controls:
  require_atomic_checkpoints: true
logging:
  ledger: results/ledger.jsonl
"""

    patched = backfill.patch_quality_controls(text, {backfill.VA_GUARD: True})

    parsed = yaml.safe_load(patched)
    assert parsed["quality_controls"]["require_atomic_checkpoints"] is True
    assert parsed["quality_controls"][backfill.VA_GUARD] is True
    assert patched.index("forbid_validated") < patched.index("logging:")


def test_backfill_claim_guards_updates_only_required_configs(tmp_path):
    cqr_va = tmp_path / "experiments/regression/configs/cqr_va.yaml"
    split_only = tmp_path / "experiments/regression/configs/split_only.yaml"
    cqr_va.parent.mkdir(parents=True)
    cqr_va.write_text(
        """experiment_id: cqr_va_v0
cp_methods:
  - split_abs
  - cqr
  - venn_abers_quantile
logging:
  ledger: results/ledger.jsonl
""",
        encoding="utf-8",
    )
    split_only.write_text(
        """experiment_id: split_only_v0
cp_methods:
  - split_abs
logging:
  ledger: results/ledger.jsonl
""",
        encoding="utf-8",
    )

    payload = backfill.build_payload(
        root=tmp_path,
        config_glob="experiments/regression/configs/*.yaml",
        explicit_paths=[],
        dry_run=False,
    )

    assert payload["summary"]["configs_scanned"] == 2
    assert payload["summary"]["configs_touched"] == 1
    assert payload["summary"]["guard_backfill_counts"] == {
        backfill.CQR_GUARD: 1,
        backfill.VA_GUARD: 1,
    }
    parsed = yaml.safe_load(cqr_va.read_text(encoding="utf-8"))
    assert parsed["quality_controls"][backfill.CQR_GUARD] is True
    assert parsed["quality_controls"][backfill.VA_GUARD] is True
    assert "quality_controls" not in yaml.safe_load(split_only.read_text(encoding="utf-8"))


def test_render_markdown_lists_touched_rows(tmp_path):
    config = tmp_path / "experiments/regression/configs/cqr.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        """experiment_id: cqr_v0
cp_methods:
  - cqr
""",
        encoding="utf-8",
    )
    payload = backfill.build_payload(
        root=tmp_path,
        config_glob="experiments/regression/configs/*.yaml",
        explicit_paths=[],
        dry_run=True,
    )
    markdown = backfill.render_markdown(payload)

    assert "# Legacy Claim Guard Backfill" in markdown
    assert "`experiments/regression/configs/cqr.yaml`" in markdown
    assert backfill.CQR_GUARD in markdown
