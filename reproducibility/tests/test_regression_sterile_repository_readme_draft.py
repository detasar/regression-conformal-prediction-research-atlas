import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT / "experiments/regression/manuscript/sterile_repository_readme_draft.json"
)
README = ROOT / "experiments/regression/manuscript/sterile_repository_readme_draft.md"
REGISTRY = ROOT / "experiments/regression/manuscript/publication_citation_registry.json"
KG_QUALITY = (
    ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
)


def load_artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_sterile_repository_readme_draft_is_source_backed_and_neutral():
    payload = load_artifact()
    summary = payload["summary"]
    kg_quality = json.loads(KG_QUALITY.read_text(encoding="utf-8"))
    graph = kg_quality["graph"]

    assert summary["overall_status"] == "sterile_repository_readme_draft_ready"
    assert summary["draft_not_final"] is True
    assert summary["author_name"] == "Emre Tasar"
    assert summary["author_role"] == "Data Scientist"
    assert summary["author_email"] == "detasar@gmail.com"
    assert summary["author_header"] == "Author: Emre Tasar, Data Scientist"
    assert summary["publication_completed_rows"] == 145839
    assert summary["dataset_count"] == 67
    assert summary["dataset_alpha_cell_count"] == 95
    assert summary["method_count"] == 28
    assert summary["cqr_frontier_cell_count"] == 56
    assert summary["mondrian_frontier_cell_count"] == 15
    assert summary["cv_plus_frontier_cell_count"] == 13
    assert summary["venn_undercoverage_run_count"] == 14
    assert summary["bounded_support_validity_ready_bundle_count"] == 0
    assert summary["fairness_population_ready_bundle_count"] == 0
    assert summary["supplement_section_count"] == 6
    assert summary["sterile_required_content_row_count"] == 9
    assert summary["sterile_required_content_traceable_count"] == 9
    assert summary["sterile_candidate_inclusion_risk_hit_count"] == 0
    assert summary["citation_row_count"] == 15
    assert summary["bibtex_entry_count"] == 15
    assert summary["kg_node_count"] == graph["node_count"]
    assert summary["kg_edge_count"] == graph["edge_count"]
    assert summary["kg_isolated_node_count"] == 0
    assert (
        summary["private_review_package_status"]
        == "private_sterile_publication_package_ready"
    )
    assert summary["private_review_package_copied_file_count"] > 100
    assert summary["private_review_package_failed_check_count"] == 0
    assert summary["private_review_surface_count"] == 6
    assert summary["private_review_surface_pass_count"] == 6
    assert summary["kg_browser_node_count"] == graph["node_count"]
    assert summary["kg_browser_edge_count"] == graph["edge_count"]
    assert summary["kg_browser_node_type_count"] > 0
    assert summary["kg_browser_relation_type_count"] > 0
    assert summary["kg_browser_guided_trace_preset_count"] == 7
    assert (
        summary["research_document_status"]
        == "research_document_private_authoring_ready"
    )
    assert summary["research_document_authoring_authorized"] is True
    assert summary["research_document_public_release_authorized"] is False
    assert summary["publication_authoring_decision_status"] == (
        "research_document_authoring_decision_ready"
    )
    assert summary["publication_authoring_final_public_release_authorized"] is False
    assert summary["private_remote_visibility"] == "PRIVATE"
    assert summary["private_remote_commit_match"] is True
    assert summary["private_review_package_created"] is True
    assert summary["private_publication_repository_created"] is True
    assert summary["private_publication_repository_visibility"] == "PRIVATE"
    assert summary["private_publication_repository_commit_match"] is True
    assert summary["private_render_audit_status"] == (
        "private_latex_html_review_output_audit_pass"
    )
    assert summary["private_render_audit_html_quality_pass_count"] == 3
    assert summary["private_render_audit_latex_compile_pass_count"] == 2
    assert summary["private_render_audit_failed_check_count"] == 0
    assert summary["publication_exemplar_source_row_count"] == 10
    assert summary["publication_exemplar_design_decision_row_count"] == 10
    assert summary["reviewer_front_door_row_count"] == 4
    assert summary["review_at_a_glance_row_count"] == 6
    assert summary["first_ten_minute_review_row_count"] == 5
    assert summary["reviewer_acceptance_row_count"] == 5
    assert summary["private_review_contract_row_count"] == 5
    assert summary["reader_mode_selector_row_count"] == 4
    assert summary["result_verification_command_row_count"] == 5
    assert summary["environment_data_access_row_count"] == 5
    assert summary["reviewer_decision_row_count"] == 5
    assert summary["finalization_blocker_row_count"] == 10
    assert summary["blocked_finalization_blocker_row_count"] == 10
    assert summary["artifact_entry_row_count"] == 6
    assert summary["provenance_graph_log_row_count"] == 5
    assert summary["repository_map_row_count"] == 9
    assert summary["article_supplement_crosswalk_row_count"] == 5
    assert summary["research_question_row_count"] == 5
    assert summary["contribution_finding_row_count"] == 6
    assert summary["paper_architecture_row_count"] == 5
    assert summary["main_article_guarantee_boundary_row_count"] == 5
    assert summary["plain_language_summary_row_count"] == 5
    assert summary["research_document_plain_language_summary_row_count"] == 5
    assert summary["result_interpretation_ladder_row_count"] == 6
    assert summary["research_document_result_interpretation_ladder_row_count"] == 6
    assert summary["claim_safe_reading_row_count"] == 8
    assert summary["research_document_claim_language_guardrail_row_count"] == 8
    assert summary["research_document_claim_review_status_counts"] == {"pass": 8}
    assert len(payload["artifact_entry_rows"]) == 6
    assert len(payload["provenance_graph_log_rows"]) == 5
    assert len(payload["repository_map_rows"]) == 9
    repository_paths = {row["package_path"] for row in payload["repository_map_rows"]}
    assert {
        "README.md",
        "manuscript/research_document.md",
        "manuscript/main_article_draft.md",
        "manuscript/supplementary_document_draft.md",
        "site/kg_browser.html",
        "site/index.html",
        "governance/",
        "provenance/",
    }.issubset(repository_paths)
    assert len(payload["article_supplement_crosswalk_rows"]) == 5
    assert len(payload["reviewer_front_door_rows"]) == 4
    assert len(payload["first_ten_minute_review_rows"]) == 5
    assert len(payload["reviewer_acceptance_rows"]) == 5
    acceptance_items = {
        row["acceptance_item"] for row in payload["reviewer_acceptance_rows"]
    }
    assert {
        "Private review status is unambiguous.",
        "The central empirical wording is scoped.",
        "Negative evidence is narrow enough.",
        "Closed positive claims stay closed.",
        "Traceability is useful but not citable yet.",
    } == acceptance_items
    assert all(
        row["evidence"] and row["reject_if"]
        for row in payload["reviewer_acceptance_rows"]
    )
    assert len(payload["private_review_contract_rows"]) == 5
    assert {
        row["review_action"] for row in payload["private_review_contract_rows"]
    } == {
        "Read and critique the package privately.",
        "Cite, publish, or make the repository public.",
        "Use CQR/CV+ as the practical reading of the evidence.",
        "Interpret the Venn-Abers result.",
        "Use the KG and site to navigate evidence.",
    }
    assert all(
        row["current_answer"] and row["evidence"] and row["boundary"]
        for row in payload["private_review_contract_rows"]
    )
    assert len(payload["reader_mode_selector_rows"]) == 4
    assert {row["reader_mode"] for row in payload["reader_mode_selector_rows"]} == {
        "Fast orientation",
        "Scientific review",
        "Claim audit",
        "Release review",
    }
    assert all(
        row["use_when"]
        and row["open_first"]
        and row["then_check"]
        and row["do_not_do"].startswith("Do not ")
        for row in payload["reader_mode_selector_rows"]
    )
    claim_audit_row = next(
        row
        for row in payload["reader_mode_selector_rows"]
        if row["reader_mode"] == "Claim audit"
    )
    assert "`site/kg_browser.html`" == claim_audit_row["open_first"]
    assert f"{summary['kg_browser_node_count']:,}" in claim_audit_row["then_check"]
    assert f"{summary['kg_browser_edge_count']:,}" in claim_audit_row["then_check"]
    assert "explicit release authorization" in claim_audit_row["do_not_do"]
    assert len(payload["result_verification_command_rows"]) == 5
    assert {
        row["verification_task"] for row in payload["result_verification_command_rows"]
    } == {
        "Rebuild the private review README draft",
        "Check reader-facing publication artifacts",
        "Regenerate the sterile private package",
        "Check KG metadata freshness",
        "Run the full source test suite",
    }
    assert all(
        row["command"]
        and row["expected_evidence"]
        and row["primary_artifact"]
        and row["boundary"]
        for row in payload["result_verification_command_rows"]
    )
    assert any(
        row["expected_evidence"]
        == "Expected current result: 834 tests pass with the existing LightGBM feature-name warning."
        for row in payload["result_verification_command_rows"]
    )
    assert all(
        "public release" in row["boundary"].lower()
        or "citable" in row["boundary"].lower()
        or "method recommendation" in row["boundary"].lower()
        for row in payload["result_verification_command_rows"]
    )
    assert len(payload["environment_data_access_rows"]) == 5
    assert {
        row["surface"] for row in payload["environment_data_access_rows"]
    } == {
        "Runtime and dependency specification",
        "Executable source, configs, and tests",
        "Data access and preprocessing policy",
        "Raw-data, cache, and secret exclusion",
        "Authority of generated review artifacts",
    }
    assert all(
        row["package_path"] and row["reader_use"] and row["evidence"] and row["boundary"]
        for row in payload["environment_data_access_rows"]
    )
    raw_exclusion_row = next(
        row
        for row in payload["environment_data_access_rows"]
        if row["surface"] == "Raw-data, cache, and secret exclusion"
    )
    assert "path-risk hits: 0" in raw_exclusion_row["evidence"]
    assert "secret-pattern hits: 0" in raw_exclusion_row["evidence"]
    assert {row["lane"] for row in payload["reviewer_front_door_rows"]} == {
        "Read",
        "Check",
        "Trace",
        "Decide",
    }
    assert all(
        row["safe_takeaway"] and row["closed_boundary"]
        for row in payload["reviewer_front_door_rows"]
    )
    trace_row = next(
        row for row in payload["reviewer_front_door_rows"] if row["lane"] == "Trace"
    )
    assert "`site/kg_browser.html`" == trace_row["open_first"]
    assert "0 isolated nodes" in trace_row["safe_takeaway"]
    assert "GitHub Pages" in trace_row["closed_boundary"]
    assert {row["minute"] for row in payload["first_ten_minute_review_rows"]} == {
        "0-1",
        "1-3",
        "3-5",
        "5-7",
        "7-10",
    }
    assert all(
        row["review_action"]
        and row["artifact"]
        and row["acceptance_check"]
        and row["stop_if_missing"]
        for row in payload["first_ten_minute_review_rows"]
    )
    assert len(payload["research_question_rows"]) == 5
    assert len(payload["contribution_finding_rows"]) == 6
    kg_reader_rows = json.dumps(
        payload["research_question_rows"] + payload["contribution_finding_rows"]
    )
    assert f"{summary['kg_node_count']:,}" in kg_reader_rows
    assert f"{summary['kg_edge_count']:,}" in kg_reader_rows
    assert "3,566" not in kg_reader_rows
    assert "20,219" not in kg_reader_rows
    assert len(payload["paper_architecture_rows"]) == 5
    assert len(payload["review_at_a_glance_rows"]) == 6
    assert len(payload["finalization_blocker_rows"]) == 10
    blocker_rows = {
        row["blocker_id"]: row for row in payload["finalization_blocker_rows"]
    }
    assert set(blocker_rows) >= {
        "final_manuscript_prose_not_authorized",
        "publication_site_deployment_not_authorized",
        "kg_citable_component_not_authorized",
        "method_recommendation_not_authorized",
        "positive_claim_promotion_not_authorized",
    }
    assert {
        row["authorization_status"] for row in payload["finalization_blocker_rows"]
    } == {"blocked_no_final_authorization"}
    assert all(
        row["blocked_current_action"]
        and row["allowed_current_action"]
        and row["evidence_summary"]
        for row in payload["finalization_blocker_rows"]
    )
    assert len(payload["main_article_guarantee_boundary_rows"]) == 5
    assert len(payload["plain_language_summary_rows"]) == 5
    assert {
        row["reader_question"] for row in payload["plain_language_summary_rows"]
    } == {
        "What is the shortest correct reading of the study?",
        "What does the CQR/CV+ finding mean?",
        "What does `1 - alpha` mean here?",
        "How should the Venn-Abers bridge result be read?",
        "Why keep the KG and private package in the review path?",
    }
    assert all(
        row["plain_language_answer"] and row["evidence_anchor"] and row["boundary"]
        for row in payload["plain_language_summary_rows"]
    )
    assert all(
        row["boundary"].startswith("Do not ")
        for row in payload["plain_language_summary_rows"]
    )
    assert len(payload["result_interpretation_ladder_rows"]) == 6
    assert {
        row["evidence_layer"] for row in payload["result_interpretation_ladder_rows"]
    } == {
        "Nominal target",
        "Observed aggregate coverage",
        "Coverage-width trade-off",
        "Robustness retention",
        "Negative bridge evidence",
        "Closed gates",
    }
    assert all(
        row["what_it_can_support"]
        and row["evidence_in_this_study"]
        and row["what_it_cannot_support"]
        and row["reader_action"]
        for row in payload["result_interpretation_ladder_rows"]
    )
    assert any(
        "strong practical candidates observed in these experiments"
        in row["reader_action"]
        for row in payload["result_interpretation_ladder_rows"]
    )
    assert any(
        "cannot reject predictive-distribution or generalized Venn-Abers"
        in row["what_it_cannot_support"]
        for row in payload["result_interpretation_ladder_rows"]
    )
    assert any(
        "Closed gates cannot be reopened by optimistic prose"
        in row["what_it_cannot_support"]
        for row in payload["result_interpretation_ladder_rows"]
    )
    assert len(payload["claim_safe_reading_rows"]) == 8
    assert {
        row["claim_review_status"] for row in payload["claim_safe_reading_rows"]
    } == {"pass"}
    assert summary["private_repository_created"] is True
    assert summary["sterile_repository_creation_authorized"] is False
    assert summary["release_authorized"] is False
    assert summary["public_release_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["final_manuscript_prose_permission"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["method_champion_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["analysis_only_no_champion_method"] is True
    assert summary["failed_check_count"] == 0


def test_sterile_repository_readme_draft_uses_registered_citations():
    payload = load_artifact()
    readme = README.read_text(encoding="utf-8")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registered = {row["citation_key"] for row in registry["citation_rows"]}
    cited = set(re.findall(r"\[@([A-Za-z0-9_]+)", readme))
    cited.update(re.findall(r"; @([A-Za-z0-9_]+)", readme))
    cited.update(re.findall(r"`@([A-Za-z0-9_]+)`", readme))

    assert cited
    assert cited.issubset(registered)
    for required_key in [
        "lei2017distribution_free_regression",
        "romano2019conformalized_quantile_regression",
        "barber2020jackknife_plus",
        "kim2020jackknife_after_bootstrap",
        "nouretdinov2018ivapd",
    ]:
        assert required_key in cited
        assert required_key in payload["citation_keys"].values()


def test_sterile_repository_readme_draft_keeps_claim_boundaries_visible():
    readme = README.read_text(encoding="utf-8")

    assert "- Author: Emre Tasar, Data Scientist." in readme
    assert "- Contact: detasar@gmail.com." in readme
    for heading in [
        "## One-Minute Thesis",
        "## Status",
        "## Reader Mode Selector",
        "## Private Review Contract",
        "## Reviewer Acceptance Checklist",
        "## Reviewer Front Door",
        "## Review At A Glance",
        "## Plain-Language Summary",
        "## Evidence-To-Claim Ladder",
        "## First 10 Minutes Review Protocol",
        "## Research Question Answer Map",
        "## Contribution And Finding Snapshot",
        "## Method Reading Guide",
        "## Guarantee Boundary Snapshot",
        "## Review Path",
        "## Artifact Entry Points",
        "## Provenance Graph And Log Entry Points",
        "## Claim-Safe Reading Map",
        "## Reviewer Decision Matrix",
        "## Finalization Blocker Snapshot",
        "## Publication Design Basis",
        "## Current Evidence Snapshot",
        "## Result Verification Commands",
        "## Environment And Data Access",
        "## Evidence Snapshot Reading Notes",
        "## Article-Supplement Evidence Crosswalk",
        "## Repository Map",
        "## Private Review Package",
        "## Research Document Entry Point",
        "## Review Handoff",
        "## Claim Boundaries",
        "## Knowledge Graph",
        "## References",
        "## Source Artifacts",
    ]:
        assert heading in readme

    assert "Private review package created: `True`" in readme
    assert "private, sterile review package for a neutral empirical study" in readme
    assert (
        "CQR/CV+ were observed as strong practical candidates in these experiments"
        in readme
    )
    assert "expected strong regression solution did not emerge" in readme
    assert "browsable traceability surface linking claims, reports, methods" in readme
    assert "public KG citation and GitHub Pages publication remain closed" in readme
    assert "mirrors the Research Document's plain-language reader surface" in readme
    assert "| Reader question | Plain-language answer | Evidence anchor | Boundary |" in readme
    assert "What is the shortest correct reading of the study?" in readme
    assert "This is an audited measurement record for regression conformal prediction" in readme
    assert "What does the CQR/CV+ finding mean?" in readme
    assert "CQR/CV+ looked practically useful in these experiments" in readme
    assert "What does `1 - alpha` mean here?" in readme
    assert "`1 - alpha` is the target coverage level" in readme
    assert "How should the Venn-Abers bridge result be read?" in readme
    assert "The evaluated regression bridge produced negative failure-mode evidence" in readme
    assert "Why keep the KG and private package in the review path?" in readme
    assert "They let a reviewer trace claims to reports, scripts, citations" in readme
    assert (
        "README-level ladder mirrors the Research Document's Evidence-To-Claim Interpretation Ladder"
        in readme
    )
    assert (
        "| Evidence layer | What it can support | Evidence in this study | What it cannot support | Reader action |"
        in readme
    )
    assert "Nominal target" in readme
    assert "Observed aggregate coverage" in readme
    assert "Coverage-width trade-off" in readme
    assert "Robustness retention" in readme
    assert "Negative bridge evidence" in readme
    assert "Closed gates" in readme
    assert (
        "Use coverage as one descriptive axis, not as a standalone recommendation"
        in readme
    )
    assert (
        "Read CQR/CV+ as strong practical candidates observed in these experiments"
        in readme
    )
    assert (
        "Report the bridge result as negative evidence exactly at the evaluated bridge scope"
        in readme
    )
    assert "Closed gates cannot be reopened by optimistic prose" in readme
    assert "Private GitHub review repository: `PRIVATE`" in readme
    assert "Use these commands from the source repository root" in readme
    assert "| Verification task | Command | Expected evidence | Primary artifact | Boundary |" in readme
    assert "Rebuild the private review README draft" in readme
    assert "Check reader-facing publication artifacts" in readme
    assert "Regenerate the sterile private package" in readme
    assert "Check KG metadata freshness" in readme
    assert "Run the full source test suite" in readme
    assert "tests/test_regression_sterile_repository_readme_draft.py" in readme
    assert "tests/test_regression_research_document.py" in readme
    assert "tests/test_regression_publication_kg_metadata_freshness.py" in readme
    assert "Expected current result: 834 tests pass" in readme
    assert "source repository remains the authoritative execution environment" in readme
    assert "Use this table before running verification commands" in readme
    assert "| Surface | Package path | Reader use | Evidence | Boundary |" in readme
    assert "Runtime and dependency specification" in readme
    assert "requirements.txt" in readme
    assert "Executable source, configs, and tests" in readme
    assert "reproducibility/" in readme
    assert "Data access and preprocessing policy" in readme
    assert "data_policy_registry.md" in readme
    assert "Raw-data, cache, and secret exclusion" in readme
    assert "Current path-risk hits: 0; secret-pattern hits: 0." in readme
    assert "not a raw-data archive" in readme
    assert "not a locked container image" in readme
    assert "Use this selector before scrolling through the full README" in readme
    assert "| Reader mode | Use when | Open first | Then check | Do not do |" in readme
    assert "| Fast orientation | You need the study thesis and current status in two minutes." in readme
    assert "| Scientific review | You need to judge whether the empirical interpretation is defensible." in readme
    assert "| Claim audit | You need to trace a sentence, number, method, or gate to evidence." in readme
    assert "| Release review | You need to decide whether public release can be considered later." in readme
    assert "Do not treat the README as a public release or recommendation" in readme
    assert "Do not upgrade descriptive diagnostics into final selection claims" in readme
    assert "Do not cite the KG or site before explicit release authorization" in readme
    assert "Do not make the repository public without a later approval record" in readme
    assert "Use this contract before interpreting any result" in readme
    assert "| Reviewer action | Current answer | Evidence | Boundary |" in readme
    assert "Read and critique the package privately." in readme
    assert "Allowed for private scientific review." in readme
    assert "Cite, publish, or make the repository public." in readme
    assert "Not allowed at this stage." in readme
    assert "Use CQR/CV+ as the practical reading of the evidence." in readme
    assert "Allowed only as experiment-scoped observation." in readme
    assert "Use the KG and site to navigate evidence." in readme
    assert "Allowed as private review navigation." in readme
    assert "Public release, GitHub Pages, and citable repository status need" in readme
    assert "No public KG citation, public site, or GitHub Pages release" in readme
    assert "Use `manuscript/research_document.md` as the primary reader-facing" in readme
    assert "governance/publication_authoring_decision_record.md" in readme
    assert "Start with `USER_REVIEW_HANDOFF.md` for the private review order" in readme
    assert (
        "Use this checklist before treating the package as reader-ready for private review"
        in readme
    )
    assert (
        "| Acceptance item | Evidence to inspect | Reject private review readiness if |"
        in readme
    )
    assert "[ ] Private review status is unambiguous." in readme
    assert "[ ] The central empirical wording is scoped." in readme
    assert "[ ] Negative evidence is narrow enough." in readme
    assert "[ ] Closed positive claims stay closed." in readme
    assert "[ ] Traceability is useful but not citable yet." in readme
    assert "These checks accept review readability only" in readme
    assert (
        "do not authorize public release, KG citation, final prose, or a method recommendation"
        in readme
    )
    assert "Any reader can mistake this package for a public release" in readme
    assert "Zero-ready gates are converted into bounded-support validity" in readme
    assert "cited or published before the release authorization record exists" in readme
    assert "first 60-second route" in readme
    assert (
        "| Lane | Open first | Reader action | Safe takeaway | Closed boundary |"
        in readme
    )
    assert "| Read | `manuscript/research_document.md`" in readme
    assert "| Check | `manuscript/supplementary_document_draft.md`" in readme
    assert "| Trace | `site/kg_browser.html`" in readme
    assert "| Decide | `PUBLIC_RELEASE_REVIEW_CHECKLIST.md`" in readme
    assert "No citable KG, public site, or GitHub Pages release" in readme
    assert "Public release requires explicit approval" in readme
    assert "first 30-second review map" in readme
    assert "acceptance-check driven route" in readme
    assert (
        "| Minute | Review action | Artifact | Acceptance check | Stop if missing |"
        in readme
    )
    assert "| 0-1 | Read the One-Minute Thesis and Status block." in readme
    assert "| 1-3 | Open the Research Document through the Read lane." in readme
    assert "| 3-5 | Check the main empirical wording against evidence." in readme
    assert "| 5-7 | Check the Venn-Abers and closed-claim boundaries." in readme
    assert "| 7-10 | Trace one claim through the KG and release checklist." in readme
    assert (
        "Stop if private visibility, release status, or method-recommendation status is ambiguous"
        in readme
    )
    assert (
        "Stop if the wording becomes a final selected method, best-method claim, or recommendation"
        in readme
    )
    assert "public release still requires a separate authorization record" in readme
    assert "Main empirical wording" in readme
    assert "Negative evidence" in readme
    assert "Closed positive claims" in readme
    assert "Traceability" in readme
    assert "Release state" in readme
    assert "No final selected method, best-method claim, or recommendation" in readme
    assert (
        "No prose may convert zero-ready gates into validity or fairness claims"
        in readme
    )
    assert "Public release requires a later explicit approval record" in readme
    assert "README-level view of the final-output authorization protocol" in readme
    assert "final_manuscript_prose_not_authorized" in readme
    assert "publication_site_deployment_not_authorized" in readme
    assert "kg_citable_component_not_authorized" in readme
    assert "method_recommendation_not_authorized" in readme
    assert "positive_claim_promotion_not_authorized" in readme
    assert "goal_can_mark_complete=False" in readme
    assert "release_authorized_count=0" in readme
    assert "positive_claim_ready_gate_count=0" in readme
    assert "PUBLIC_RELEASE_REVIEW_CHECKLIST.md" in readme
    assert "manuscript/research_document.md" in readme
    assert (
        "README-level map routes into the Research Document's research questions"
        in readme
    )
    assert "What empirical object does this Research Document evaluate?" in readme
    assert "Which stronger scientific claims remain closed?" in readme
    assert "How can a reviewer audit or navigate the evidence?" in readme
    assert (
        "README-level snapshot routes into the Research Document's Contribution And Finding Map"
        in readme
    )
    assert "Audited regression-CP experiment scope" in readme
    assert "Practical candidate pattern" in readme
    assert "Venn-Abers bridge negative evidence" in readme
    assert "Closed positive claims are part of the result" in readme
    assert "Traceability and reproducibility surface" in readme
    assert "Publication package architecture" in readme
    assert (
        "This is not a final selected method, global superiority claim, or recommendation"
        in readme
    )
    assert "This does not yet make the KG a public citable component" in readme
    assert (
        "Use this table to choose the right file for the review task at hand" in readme
    )
    assert (
        "The package is intentionally split into narrative, evidence, browser" in readme
    )
    assert (
        "Use these files when the review question is about how the study was executed"
        in readme
    )
    assert "`experiments/regression/diary/data_scientist_log.md`" in readme
    assert "`provenance/data_scientist_log.md`" in readme
    assert "`provenance/graphs/data_flow.mmd`" in readme
    assert "`provenance/graphs/control_flow.mmd`" in readme
    assert "`provenance/graphs/dependency_graph.mmd`" in readme
    assert "`provenance/graphs/system_ontology.mmd`" in readme
    assert "they do not create new empirical evidence, method recommendations" in readme
    assert "Paper Architecture And Review Contract" in readme
    assert (
        "README-level table routes into the main article's Paper Architecture And Review Contract"
        in readme
    )
    assert "Use the supplement for method detail, robustness diagnostics" in readme
    assert "Use the site and KG browser to trace claims to source artifacts" in readme
    assert "No prose may convert a blocked claim into a positive conclusion" in readme
    assert (
        "KG citation, GitHub Pages, and public site deployment remain closed" in readme
    )
    assert "README-level route into the Research Document guardrails" in readme
    assert "How should CQR/CV+ be described?" in readme
    assert (
        "CQR/CV+ were observed as strong practical candidates in these experiments"
        in readme
    )
    assert "Do not call CQR, CV+, or any method a final recommendation" in readme
    assert "The current evidence does not authorize a final selected method" in readme
    assert "bridge-specific negative evidence" in readme
    assert "broader Venn-Abers literature" in readme
    assert "`manuscript/main_article_draft.md`" in readme
    assert "`manuscript/supplementary_document_draft.md`" in readme
    assert "`site/kg_browser.html`" in readme
    assert "compact decoder before reading the Research Document" in readme
    assert "Method Primer For Non-Specialist Readers" in readme
    assert "Reader Safety Checklist" in readme
    assert (
        "explain `1 - alpha`, CQR, CV+, Mondrian/group calibration, and the Venn-Abers bridge result"
        in readme
    )
    assert (
        "do not open method recommendation, final selection, population fairness, or validated Venn-Abers regression claims"
        in readme
    )
    assert "Split conformal" in readme
    assert "adaptive interval" in readme
    assert "Negative evidence for the evaluated bridge" in readme
    assert (
        "README-level snapshot mirrors the main article's guarantee and claim boundary table"
        in readme
    )
    assert "The conformal guarantee is a marginal coverage statement" in readme
    assert "not conditional, subgroup, endpoint, or deployment coverage" in readme
    assert "not final method selection or universal superiority claims" in readme
    assert (
        "not a rejection of predictive-distribution or generalized Venn-Abers research"
        in readme
    )
    assert "Frontier-cell counts describe observed coverage/width trade-offs" in readme
    assert "closed claim gates" in readme
    assert "The main article is intentionally compact" in readme
    assert "Supplement Reader Crosswalk; S1-S2" in readme
    assert "No validated Venn-Abers regression interval claim" in readme
    assert "No public citable KG/site/repository release" in readme
    assert (
        "| Private review package item | Package path | Review job | Current review status |"
        in readme
    )
    assert "`README.md`" in readme
    assert "`site/index.html`" in readme
    assert "`governance/`" in readme
    assert "`provenance/`" in readme
    assert (
        "Use the private web portal for reviewer lanes, rendered outputs, and KG navigation"
        in readme
    )
    assert (
        "Review-only provenance available; it does not upgrade empirical claims"
        in readme
    )
    assert "not public release or final method selection" in readme
    assert "scientific_framing" in readme
    assert "public_release_timing" in readme
    assert "Public release requires a later explicit approval record" in readme
    assert "source-backed review of comparable conformal prediction papers" in readme
    assert "not empirical method evidence" in readme
    assert "Use a minimal main article and a broad supplementary document" in readme
    assert "Make the README a review router" in readme
    assert "site/kg_browser.html" in readme
    assert "node-type filtering" in readme
    assert "guided trace presets" in readme
    assert "Final selected-method gate" in readme
    assert "Venn-Abers bridge gate" in readme
    assert "Claim-safe README map" in readme
    assert "Research Document guardrail" in readme
    assert "edge provenance" in readme
    assert "local/private sterile review package has been generated" in readme
    assert "authorize public release" in readme
    assert "does not recommend a conformal method" in readme
    assert "public/citable release remains blocked" in readme
    assert (
        "CQR is not claimed as the best regression conformal method in general"
        in readme
    )
    assert "does not support a validated regression interval claim" in readme
    assert "Group diagnostics do not establish population fairness" in readme
    assert "Endpoint diagnostics do not establish bounded-support validity" in readme
    assert "winner" not in readme.lower()
