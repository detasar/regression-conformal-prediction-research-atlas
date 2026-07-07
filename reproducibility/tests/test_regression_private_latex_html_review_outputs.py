import json
from pathlib import Path

from experiments.regression.scripts import (
    audit_private_latex_html_review_outputs as audit,
    build_private_latex_html_review_outputs as outputs,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "experiments/regression/manuscript/"
    / "private_latex_html_review_outputs_manifest.json"
)
AUDIT_ARTIFACT = (
    ROOT
    / "experiments/regression/manuscript/"
    / "private_latex_html_review_output_audit.json"
)


def test_private_latex_html_builder_creates_review_outputs(tmp_path):
    output_dir = tmp_path / "review_outputs"

    payload = outputs.build_payload(ROOT, output_dir)
    summary = payload["summary"]
    rows = {row["output_id"]: row for row in payload["output_rows"]}

    assert summary["overall_status"] == "private_latex_html_review_outputs_ready"
    assert summary["latex_output_count"] == 2
    assert summary["html_output_count"] == 3
    assert summary["bibtex_output_count"] == 1
    assert summary["failed_check_count"] == 0
    assert summary["public_release_authorized"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["raw_data_or_secret_inclusion_authorized"] is False
    assert summary["secret_pattern_hit_count"] == 0

    main_tex = output_dir / "main_article_review.tex"
    main_html = output_dir / "main_article_review.html"
    supplement_tex = output_dir / "supplementary_document_review.tex"
    supplement_html = output_dir / "supplementary_document_review.html"
    index_html = output_dir / "index.html"
    for path in [main_tex, main_html, supplement_tex, supplement_html, index_html]:
        assert path.exists(), path

    assert "\\documentclass" in main_tex.read_text(encoding="utf-8")
    main_tex_text = main_tex.read_text(encoding="utf-8")
    main_html_text = main_html.read_text(encoding="utf-8")
    assert "\\cite{lei2017distribution_free_regression}" in main_tex_text
    assert r"\texttt{1 - alpha}" in main_tex_text
    assert r"\texttt{alpha} is the target miscoverage rate" in main_tex_text
    assert (
        "The core coverage target is \\cite{romano2019conformalized_quantile_regression};"
        not in main_tex_text
    )
    assert "\\bibliography{references}" in main_tex_text
    assert "Private review draft" in main_html_text
    assert "Regression Conformal Prediction" in main_html_text
    assert "Paper Architecture And Review Contract" in main_html_text
    assert "No prose may convert a blocked claim into a positive conclusion" in main_html_text
    assert "<code>1 - alpha</code>" in main_html_text
    assert "<code>alpha</code> is the target miscoverage rate" in main_html_text
    assert (
        "The core coverage target is [<a href=\"https://arxiv.org/abs/1905.03222\">"
        not in main_html_text
    )
    assert '<a href="<a href=' not in main_html_text
    assert "&quot;&gt;@" not in main_html_text
    supplement_tex_text = supplement_tex.read_text(encoding="utf-8")
    supplement_html_text = supplement_html.read_text(encoding="utf-8")
    assert "Supplementary Document Draft" in supplement_html_text
    assert r"\texttt{1 - alpha} is the target coverage level" in supplement_tex_text
    assert r"\texttt{alpha} is the target miscoverage rate" in supplement_tex_text
    assert "<code>1 - alpha</code> is the target coverage level" in supplement_html_text
    assert "<code>alpha</code> is the target miscoverage rate" in supplement_html_text
    assert rows["main_article_latex"]["sha256"]
    assert rows["supplementary_document_html"]["bytes"] > 1000


def test_private_latex_html_builder_blocks_if_release_cut_render_is_closed(tmp_path):
    release_cut = json.loads((ROOT / outputs.RELEASE_CUT).read_text(encoding="utf-8"))
    release_cut["summary"]["neutral_latex_html_static_site_package_authorized"] = False
    release_path = tmp_path / outputs.RELEASE_CUT
    release_path.parent.mkdir(parents=True, exist_ok=True)
    release_path.write_text(json.dumps(release_cut), encoding="utf-8")

    for path in outputs.SOURCE_PATHS.values():
        src = ROOT / path
        dst = tmp_path / path
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    payload = outputs.build_payload(tmp_path, tmp_path / "outputs")
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "private_latex_html_review_outputs_blocked"
    )
    assert payload["summary"]["output_count"] == 0
    assert payload["summary"]["latex_output_count"] == 0
    assert payload["summary"]["html_output_count"] == 0
    assert payload["summary"]["bibtex_output_count"] == 0
    assert payload["summary"]["secret_pattern_hit_count"] == 0
    assert "LaTeX / HTML / BibTeX outputs: 0 / 0 / 0" in outputs.render_markdown(payload)
    assert checks["release_cut_authorizes_private_latex_html_only"]["status"] == "fail"
    assert not (tmp_path / "outputs").exists()


def test_checked_in_private_latex_html_manifest_is_private_review_only():
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    summary = payload["summary"]
    rows = {row["output_id"]: row for row in payload["output_rows"]}

    assert summary["overall_status"] == "private_latex_html_review_outputs_ready"
    assert summary["latex_output_count"] == 2
    assert summary["html_output_count"] == 3
    assert summary["bibtex_output_count"] == 1
    assert summary["failed_check_count"] == 0
    assert summary["public_release_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["method_advocacy_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["raw_data_or_secret_inclusion_authorized"] is False
    assert summary["secret_pattern_hit_count"] == 0
    assert rows["main_article_latex"]["output_path"].endswith(
        "main_article_review.tex"
    )
    assert rows["main_article_html"]["output_path"].endswith(
        "main_article_review.html"
    )
    assert rows["supplementary_document_latex"]["output_path"].endswith(
        "supplementary_document_review.tex"
    )
    assert rows["supplementary_document_html"]["output_path"].endswith(
        "supplementary_document_review.html"
    )


def test_checked_in_private_latex_html_review_output_audit_passes():
    payload = json.loads(AUDIT_ARTIFACT.read_text(encoding="utf-8"))
    summary = payload["summary"]

    assert summary["overall_status"] == "private_latex_html_review_output_audit_pass"
    assert summary["html_quality_pass_count"] == 3
    assert summary["latex_compile_pass_count"] == 2
    assert summary["failed_check_count"] == 0
    assert summary["secret_pattern_hit_count"] == 0
    assert summary["authorization_violation_count"] == 0
    assert summary["public_release_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False

    main_html = (
        ROOT
        / "experiments/regression/manuscript/review_latex_html_outputs/"
        / "main_article_review.html"
    )
    quality = audit.html_quality(main_html, ROOT)
    assert quality["status"] == "pass"
    assert quality["broken_local_links"] == []
    assert quality["unresolved_tokens"] == []
