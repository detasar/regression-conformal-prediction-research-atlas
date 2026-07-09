import json
from pathlib import Path

from experiments.regression.scripts import (
    build_private_sterile_publication_package as package,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "experiments/regression/manuscript/"
    / "private_sterile_publication_package_manifest.json"
)
KG_QUALITY = ROOT / "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"


def test_private_sterile_package_builder_creates_clean_private_package(tmp_path):
    package_root = tmp_path / "private_package"

    payload = package.build_payload(
        repo_root=ROOT,
        package_root=package_root,
        initialize_git=False,
    )
    summary = payload["summary"]

    assert summary["overall_status"] == "private_sterile_publication_package_ready"
    assert summary["author_name"] == "Emre Tasar"
    assert summary["author_role"] == "Data Scientist"
    assert summary["author_email"] == "detasar@gmail.com"
    assert summary["author_header"] == "Author: Emre Tasar, Data Scientist"
    assert summary["copied_file_count"] > 100
    assert summary["path_risk_hit_count"] == 0
    assert summary["secret_pattern_hit_count"] == 0
    assert summary["public_release_authorized"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["raw_data_or_secret_inclusion_authorized"] is False
    assert summary["generated_review_surface_count"] == 6
    assert summary["generated_review_surface_pass_count"] == 6
    assert summary["generated_review_surface_missing_count"] == 0
    assert summary["generated_review_surface_phrase_issue_count"] == 0
    assert summary["generated_review_surface_empty_table_cell_count"] == 0
    assert summary["private_static_site_quality_status"] == "pass"
    assert summary["private_static_site_html_page_count"] == 2
    assert summary["private_static_site_local_link_count"] >= 10
    assert summary["private_static_site_broken_local_link_count"] == 0
    assert summary["private_static_site_missing_required_phrase_count"] == 0
    assert summary["private_static_site_boundary_violation_count"] == 0
    assert summary["private_static_site_kg_data_status"] == "pass"
    assert summary["private_static_site_visual_smoke_status"] == "pass"
    assert summary["private_static_site_visual_smoke_issue_count"] == 0
    assert summary["private_static_site_layout_guard_status"] == "pass"
    assert summary["private_static_site_first_screen_status"] == "pass"
    assert summary["private_static_site_navigation_row_count"] == 4
    assert summary["private_static_site_navigation_pass_count"] == 4
    assert summary["private_static_site_navigation_issue_count"] == 0
    assert summary["reviewer_front_door_row_count"] == 4
    assert summary["review_at_a_glance_row_count"] == 6
    assert summary["first_ten_minute_review_row_count"] == 5
    assert summary["reviewer_acceptance_row_count"] == 5
    assert summary["result_verification_command_row_count"] == 5
    assert summary["environment_data_access_row_count"] == 5
    assert summary["research_question_row_count"] == 6
    assert summary["contribution_finding_row_count"] == 7
    assert summary["paper_architecture_row_count"] == 5
    assert summary["claim_safe_reading_row_count"] == 8
    assert summary["claim_evidence_review_row_count"] == 8
    assert summary["main_article_guarantee_boundary_row_count"] == 5
    assert summary["provenance_graph_log_row_count"] == 5
    assert summary["repository_map_row_count"] == 9
    assert summary["reader_contract_row_count"] == 4
    assert summary["kg_browser_guided_trace_preset_count"] == 7
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["kg_browser_node_count"] == graph["node_count"]
    assert summary["kg_browser_edge_count"] == graph["edge_count"]
    assert len(payload["reviewer_front_door_rows"]) == 4
    assert len(payload["review_at_a_glance_rows"]) == 6
    assert len(payload["first_ten_minute_review_rows"]) == 5
    assert len(payload["reviewer_acceptance_rows"]) == 5
    assert len(payload["result_verification_command_rows"]) == 5
    assert len(payload["environment_data_access_rows"]) == 5
    assert len(payload["paper_architecture_rows"]) == 5
    assert len(payload["repository_map_rows"]) == 9
    assert len(payload["reader_contract_rows"]) == 4

    assert (package_root / "README.md").exists()
    assert (package_root / "PUBLIC_RELEASE_REVIEW_CHECKLIST.md").exists()
    checklist = (package_root / "PUBLIC_RELEASE_REVIEW_CHECKLIST.md").read_text(
        encoding="utf-8"
    )
    assert "Claim-Safe Reading Map has been checked against the Research Document guardrails" in checklist
    assert "KG browser guided trace presets have been reviewed before public release" in checklist
    assert "Final selected-method gate" in checklist
    assert "Venn-Abers bridge gate" in checklist
    assert "Claim/evidence matrix" in checklist
    assert "Private GitHub visibility and remote/local commit match remain verified" in checklist
    assert "Release Authorization Record Inputs" in checklist
    assert "Public repository visibility" in checklist
    assert "GitHub Pages site" in checklist
    assert "KG as supplementary/web artifact" in checklist
    assert "A release record cannot silently open positive claims." in checklist
    readme = (package_root / "README.md").read_text(encoding="utf-8")
    assert "This private review package contains" in readme
    assert "future sterile repository is planned" not in readme
    assert "This README describes the private sterile publication review package" in readme
    assert "Reviewer Acceptance Checklist" in readme
    assert "[ ] Private review status is unambiguous." in readme
    assert "[ ] The central empirical wording is scoped." in readme
    assert "[ ] Negative evidence is narrow enough." in readme
    assert "[ ] Closed positive claims stay closed." in readme
    assert "[ ] Traceability is useful but not citable yet." in readme
    assert "Reviewer Front Door" in readme
    assert "first 60-second route" in readme
    assert "First 10 Minutes Review Protocol" in readme
    assert "acceptance-check driven route" in readme
    assert "Result Verification Commands" in readme
    assert "Use these commands from the source repository root" in readme
    assert "Rebuild the private review README draft" in readme
    assert "Check reader-facing publication artifacts" in readme
    assert "Regenerate the sterile private package" in readme
    assert "Check KG metadata freshness" in readme
    assert "Run the full source test suite" in readme
    assert "Expected current result: 834 tests pass" in readme
    assert "Environment And Data Access" in readme
    assert "Runtime and dependency specification" in readme
    assert "Executable source, configs, and tests" in readme
    assert "Data access and preprocessing policy" in readme
    assert "Raw-data, cache, and secret exclusion" in readme
    assert "Current path-risk hits: 0; secret-pattern hits: 0." in readme
    assert "not a raw-data archive" in readme
    assert "| Trace | `site/kg_browser.html`" in readme
    assert "No citable KG, public site, or GitHub Pages release" in readme
    assert "Research Document Entry Point" in readme
    assert "`manuscript/research_document.md`" in readme
    assert "`governance/publication_authoring_decision_record.md`" in readme
    assert "Start with `USER_REVIEW_HANDOFF.md`" in readme
    assert (
        f"{summary['copied_file_count']} copied files, "
        f"{summary['excluded_file_count']} excluded files"
        in readme
    )
    assert (package_root / "USER_REVIEW_HANDOFF.md").exists()
    handoff = (package_root / "USER_REVIEW_HANDOFF.md").read_text(
        encoding="utf-8"
    )
    assert "Recommended Review Order" in handoff
    assert "Reviewer Front Door" in handoff
    assert "first 60-second route" in handoff
    assert "First 10 Minutes Review Protocol" in handoff
    assert "acceptance-check driven route" in handoff
    assert "Trace one claim through the KG and release checklist" in handoff
    assert "| Read | `manuscript/research_document.md`" in handoff
    assert "| Trace | `site/kg_browser.html`" in handoff
    assert "Reviewer Decision Matrix" in handoff
    assert "Reviewer Acceptance Checklist" in handoff
    assert "[ ] Private review status is unambiguous." in handoff
    assert "[ ] The central empirical wording is scoped." in handoff
    assert "[ ] Negative evidence is narrow enough." in handoff
    assert "[ ] Closed positive claims stay closed." in handoff
    assert "[ ] Traceability is useful but not citable yet." in handoff
    assert "What empirical object does this Research Document evaluate?" in handoff
    assert "145,839 completed rows, 67 datasets, 95 dataset-alpha cells" in handoff
    assert "Which conformal approaches looked practically useful" in handoff
    assert "CQR/CV+ were observed as strong practical candidates" in handoff
    assert "|  |" not in handoff
    assert "Result Interpretation Guide" in handoff
    assert "Frontier cells" in handoff
    assert "Closed claim gates" in handoff
    assert "Scientific framing" in handoff
    assert "KG/site value" in handoff
    assert "`site/kg_browser.html` for guided KG trace presets" in handoff
    assert "Provenance Graph And Log Entry Points" in handoff
    assert "provenance/data_scientist_log.md" in handoff
    assert "provenance/graphs/data_flow.mmd" in handoff
    assert "Final selected-method gate" in handoff
    assert "Venn-Abers bridge gate" in handoff
    assert "Claim/evidence matrix" in handoff
    assert "Research Document guardrail" in handoff
    assert "`PUBLIC_RELEASE_REVIEW_CHECKLIST.md`" in handoff
    assert "`manuscript/research_document.md` for the integrated Research Document" in handoff
    assert "`governance/publication_authoring_decision_record.md`" in handoff
    assert "Public release requires explicit user approval after review." in handoff
    assert "Method recommendation authorized: `False`" in handoff
    assert (package_root / "PRIVATE_REVIEW_BOUNDARIES.md").exists()
    boundaries = (package_root / "PRIVATE_REVIEW_BOUNDARIES.md").read_text(
        encoding="utf-8"
    )
    assert (
        "Package status: `private_sterile_publication_package_ready`"
        in boundaries
    )
    assert "pending_audit" not in boundaries
    assert (package_root / "manuscript/research_document.md").exists()
    assert (package_root / "manuscript/research_document.json").exists()
    assert (package_root / "manuscript/publication_exemplar_review.md").exists()
    assert (package_root / "manuscript/publication_exemplar_review.json").exists()
    assert (
        package_root / "governance/publication_authoring_decision_record.md"
    ).exists()
    assert (
        package_root / "governance/publication_authoring_decision_record.json"
    ).exists()
    assert (package_root / "manuscript/main_article_draft.md").exists()
    assert (package_root / "manuscript/supplementary_document_draft.md").exists()
    assert (package_root / "rendered_outputs/main_article_review.tex").exists()
    assert (package_root / "rendered_outputs/main_article_review.html").exists()
    assert (
        package_root / "rendered_outputs/supplementary_document_review.tex"
    ).exists()
    assert (
        package_root / "rendered_outputs/supplementary_document_review.html"
    ).exists()
    assert (
        package_root / "metadata/private_latex_html_review_outputs_manifest.json"
    ).exists()
    assert (
        package_root / "metadata/private_latex_html_review_output_audit.json"
    ).exists()
    assert (package_root / "knowledge_graph/knowledge_graph.json").exists()
    assert (package_root / "knowledge_graph/quality_summary.json").exists()
    assert (package_root / "provenance/data_scientist_log.md").exists()
    assert (package_root / "provenance/graphs/data_flow.mmd").exists()
    assert (package_root / "provenance/graphs/control_flow.mmd").exists()
    assert (package_root / "provenance/graphs/dependency_graph.mmd").exists()
    assert (package_root / "provenance/graphs/system_ontology.mmd").exists()
    assert (package_root / "reproducibility/cpfi/regression/conformal.py").exists()
    assert (package_root / "site/index.html").exists()
    assert (package_root / "site/kg_browser.html").exists()
    assert (package_root / "site/kg_browser_data.json").exists()
    index = (package_root / "site/index.html").read_text(encoding="utf-8")
    assert "User review handoff" in index
    assert "Public release review checklist" in index
    assert "Research Document" in index
    assert "Emre Tasar" in index
    assert "detasar@gmail.com" in index
    assert "mailto:detasar@gmail.com" in index
    assert "Publication authoring decision record" in index
    assert "Knowledge graph browser" in index
    assert "One-Minute Thesis" in index
    assert "CQR/CV+ were observed as strong practical candidates in these experiments" in index
    assert "expected strong regression solution did not emerge" in index
    assert "browsable traceability surface linking claims, reports, methods" in index
    assert "Public KG citation and GitHub Pages publication remain closed" in index
    assert "overflow-wrap: anywhere" in index
    assert ".reviewer-front-door-table, .review-glance-table, .paper-architecture-table" in index
    assert "table-layout: fixed" in index
    assert ".reviewer-front-door-table th:nth-child(5)" in index
    assert ".review-glance-table th:nth-child(4)" in index
    assert "Reviewer Front Door" in index
    assert "Private-site version of the README first 60-second route" in index
    assert "No citable KG, public site, or GitHub Pages release" in index
    assert "First 10 Minutes Review Protocol" in index
    assert "Private-site version of the README acceptance-check driven route" in index
    assert "Reviewer Acceptance Checklist" in index
    assert "Private-site version of the README readiness checklist" in index
    assert "acceptance-checklist-table" in index
    assert "Private review status is unambiguous." in index
    assert "The central empirical wording is scoped." in index
    assert "Negative evidence is narrow enough." in index
    assert "Closed positive claims stay closed." in index
    assert "Traceability is useful but not citable yet." in index
    assert "public release still requires a separate authorization record" in index
    assert "Trace one claim through the KG and release checklist" in index
    assert (
        "Stop if KG citation, GitHub Pages, or public visibility appears authorized by implication"
        in index
    )
    assert "Reader Contract" in index
    assert "Read this document in four layers" in index
    assert "Empirical object" in index
    assert "Observed pattern" in index
    assert "Traceability and release" in index
    assert (
        "The KG is a navigation and traceability artifact, not an independent scientific claim."
        in index
    )
    assert "Article / Supplement / Knowledge Graph review triad" in index
    assert "Minimal main article" in index
    assert "Broad supplementary document" in index
    assert "Browsable knowledge graph" in index
    assert "Review lanes" in index
    assert "Reviewer decision queue" in index
    assert "Research Question Answer Map" in index
    assert "Research Document route into the research question answer map" in index
    assert "What empirical object does this Research Document evaluate?" in index
    assert "Which conformal approaches looked practically useful" in index
    assert "How can a reviewer audit or navigate the evidence?" in index
    assert "Contribution And Finding Snapshot" in index
    assert "Research Document route into the contribution and finding map" in index
    assert "Audited regression-CP experiment scope" in index
    assert "Practical candidate pattern" in index
    assert "Venn-Abers bridge negative evidence" in index
    assert "Closed positive claims are part of the result" in index
    assert "Traceability and reproducibility surface" in index
    assert "Publication package architecture" in index
    assert "This is not a final selected method, global superiority claim, or recommendation" in index
    assert "This does not yet make the KG a public citable component" in index
    assert "Review At A Glance" in index
    assert "Private-site version of the README first 30-second review map" in index
    assert "Main empirical wording" in index
    assert "Closed positive claims" in index
    assert "No final selected method, best-method claim, or recommendation" in index
    assert "No prose may convert zero-ready gates into validity or fairness claims" in index
    assert "Result interpretation guide" in index
    assert "Paper Architecture And Review Contract" in index
    assert "README-level route into the main article review contract" in index
    assert "Use the supplement for method detail, robustness diagnostics" in index
    assert "Use the site and KG browser to trace claims to source artifacts" in index
    assert "No prose may convert a blocked claim into a positive conclusion" in index
    assert "KG citation, GitHub Pages, and public site deployment remain closed" in index
    assert "Guarantee Boundary Snapshot" in index
    assert "Main-article route into the Research Document guarantee boundary ledger" in index
    assert "The conformal guarantee is a marginal coverage statement" in index
    assert "not conditional, subgroup, endpoint, or deployment coverage" in index
    assert "not final method selection or universal superiority claims" in index
    assert "not a rejection of predictive-distribution or generalized Venn-Abers research" in index
    assert "Claim-Safe Reading Map" in index
    assert "README-level route into the Research Document guardrails" in index
    assert "CQR/CV+ were observed as strong practical candidates in these experiments" in index
    assert "The current evidence does not authorize a final selected method" in index
    assert "Do not call CQR, CV+, or any method a final recommendation" in index
    assert "bridge-specific negative evidence" in index
    assert "broader Venn-Abers literature" in index
    assert "Claim-Evidence Verification Snapshot" in index
    assert "publication_claim_evidence_verification_matrix" in index
    assert "paper_method_scope_evidence" in index
    assert "Method descriptions need literature citations" in index
    assert "paper_main_results_blocked_evidence" in index
    assert (
        "Do not present a final main-results table, selected method, or positive method conclusion."
        in index
    )
    assert "supplement_venn_abers_negative_evidence" in index
    assert "Artifact entry points" in index
    assert "Provenance graph and log entry points" in index
    assert "Repository Map" in index
    assert "Package path" in index
    assert '<a href="../manuscript/research_document.md">manuscript/research_document.md</a>' in index
    assert '<a href="kg_browser.html">site/kg_browser.html</a>' in index
    assert '<a href="index.html">site/index.html</a>' in index
    assert '<a href="../governance/">governance/</a>' in index
    assert '<a href="../provenance/">provenance/</a>' in index
    assert (
        '<td><a href="../manuscript/research_document.md">'
        "manuscript/research_document.md</a></td><td>Read the integrated narrative"
        in index
    )
    assert '<td><a href="../README.md">README.md</a></td>' in index
    assert (
        '<a href="../manuscript/supplementary_document_draft.md">'
        "supplementary_document_draft.md</a>; Claim-Safe Reading Map"
        in index
    )
    assert (
        '<a href="kg_browser.html">site/kg_browser.html</a>; '
        '<a href="../PUBLIC_RELEASE_REVIEW_CHECKLIST.md">'
        "PUBLIC_RELEASE_REVIEW_CHECKLIST.md</a>"
        in index
    )
    assert "Use this table to choose the concrete private-package path for each review job" in index
    assert "Package path links are review aids only" in index
    assert "data scientist log" in index
    assert "../provenance/data_scientist_log.md" in index
    assert "../provenance/graphs/data_flow.mmd" in index
    assert "../provenance/graphs/control_flow.mmd" in index
    assert "../provenance/graphs/dependency_graph.mmd" in index
    assert "../provenance/graphs/system_ontology.mmd" in index
    assert "Article-supplement evidence crosswalk" in index
    assert "Non-specialist method primer" in index
    assert "Method Primer For Non-Specialist Readers and Reader Safety Checklist" in index
    assert (
        "Orientation does not open method recommendation, final selection, population fairness, or validated Venn-Abers regression claims"
        in index
    )
    assert (
        "including the Method Primer, Reader Safety Checklist, and Guarantee And Claim Boundary Snapshot"
        in index
    )
    assert "Research Document Entry Point" in index
    assert "No general best-method recommendation is authorized." in index
    assert "The broader Venn-Abers literature is not rejected." in index
    assert "KG citation, GitHub Pages, and public repository release remain closed." in index
    assert "Row-weighted coverage" in index
    assert "Cannot be opened by prose alone" in index
    assert "Scientific framing" in index
    assert "Public repository release" in index
    assert "Evidence snapshot" in index
    assert "Result Verification Commands" in index
    assert "Private-site version of the README verification command table" in index
    assert "Rebuild the private review README draft" in index
    assert "Check reader-facing publication artifacts" in index
    assert "Regenerate the sterile private package" in index
    assert "Check KG metadata freshness" in index
    assert "Run the full source test suite" in index
    assert "Expected current result: 834 tests pass" in index
    assert "Environment And Data Access" in index
    assert "Private-site version of the README environment and data-access contract" in index
    assert "Runtime and dependency specification" in index
    assert "Executable source, configs, and tests" in index
    assert "Data access and preprocessing policy" in index
    assert "Raw-data, cache, and secret exclusion" in index
    assert "Current path-risk hits: 0; secret-pattern hits: 0." in index
    assert f"{graph['node_count']:,} nodes, {graph['edge_count']:,} edges" in index
    assert f"{graph['node_count']:,} KG browser nodes" in index
    assert "3,577 nodes, 20,271 edges" not in index
    assert "3,577 KG browser nodes, 20,271 KG browser edges" not in index
    assert "Claim boundaries" in index
    assert "<tr><th>Public release authorized</th><td><code>False</code></td></tr>" in index
    assert (
        "<tr><th>Method recommendation authorized</th><td><code>False</code></td></tr>"
        in index
    )
    assert (
        "<tr><th>Positive claim promotion authorized</th><td><code>False</code></td></tr>"
        in index
    )
    assert (
        "<tr><th>Public release authorized</th><td><code>Public release authorized</code></td></tr>"
        not in index
    )
    assert "Publication exemplar review" in index
    assert "Knowledge graph entry point" in index
    assert "guided presets for the Final selected-method gate" in index
    assert "Claim/evidence matrix" in index
    assert "Research Document guardrail" in index
    assert "Positive claim promotion" in index
    assert "Public release</dt>" in index
    assert "../USER_REVIEW_HANDOFF.md" in index
    assert "kg_browser.html" in index
    assert "../rendered_outputs/main_article_review.html" in index
    assert "../rendered_outputs/supplementary_document_review.html" in index
    assert "KG citation and GitHub Pages deployment remain closed." in index
    assert "These boundaries are package-level controls" in index
    assert "winner" not in index.lower()
    browser = (package_root / "site/kg_browser.html").read_text(encoding="utf-8")
    assert "CPFI Knowledge Graph Browser" in browser
    assert "How to read this graph" in browser
    assert "Use this browser as a traceability surface, not as a claim generator" in browser
    assert "A typed object such as a dataset, method, report, claim, paper gate" in browser
    assert "Confidence and provenance" in browser
    assert "For claims, follow <code>SUPPORTED_BY</code> and <code>BLOCKED_BY</code>" in browser
    assert "Back to private review portal" in browser
    assert "Open KG quality summary" in browser
    assert "Guided trace presets" in browser
    assert "Final selected-method gate" in browser
    assert "Venn-Abers bridge gate" in browser
    assert "Claim-safe README map" in browser
    assert "Search nodes" in browser
    assert "Research Atlas Graph Canvas" in browser
    assert "Relation filter" in browser
    assert "Confidence floor" in browser
    assert "Graph depth" in browser
    assert "sigma@2.4.0" in browser
    assert "graphology@0.25.4" in browser
    assert 'id="fallbackCanvas"' in browser
    assert 'id="sigmaLayer"' in browser
    assert "Fallback evidence table" in browser
    assert "url.searchParams.set('node', id)" in browser
    assert "Edge provenance" in browser
    browser_data = json.loads(
        (package_root / "site/kg_browser_data.json").read_text(encoding="utf-8")
    )
    graph = json.loads(
        (ROOT / "experiments/regression/catalogs/knowledge_graph.json").read_text(
            encoding="utf-8"
        )
    )
    assert browser_data["summary"]["node_count"] == graph["node_count"]
    assert browser_data["summary"]["edge_count"] == graph["edge_count"]
    assert browser_data["summary"]["isolated_node_count"] == 0
    assert browser_data["summary"]["guided_trace_preset_count"] == 7
    assert browser_data["schema"] == "cpfi_publication_kg_browser_data_v2"
    assert browser_data["visual_palette"]["background"] == "#f7f3ea"
    assert browser_data["semantic_zone_counts"]
    node_ids = {node["id"] for node in browser_data["nodes"]}
    assert len(browser_data["guided_trace_presets"]) == 7
    assert {
        preset["node_id"] for preset in browser_data["guided_trace_presets"]
    } <= node_ids
    assert {
        preset["label"] for preset in browser_data["guided_trace_presets"]
    } >= {
        "Final selected-method gate",
        "Venn-Abers bridge gate",
        "Claim-safe README map",
    }
    for preset in browser_data["guided_trace_presets"]:
        assert preset["route_node_ids"]
        assert preset["route_node_ids"][0] == preset["node_id"]
        assert set(preset["route_node_ids"]) <= node_ids
        assert preset["default_depth"] == 1
    assert browser_data["nodes"]
    assert browser_data["edges"]
    first_node = browser_data["nodes"][0]
    assert isinstance(first_node["degree"], int)
    assert first_node["semantic_zone"]
    assert isinstance(first_node["x"], float)
    assert isinstance(first_node["y"], float)
    assert first_node["size"] > 0
    assert first_node["color"].startswith("#")
    review_surfaces = {
        row["surface_id"]: row for row in payload["generated_review_surface_rows"]
    }
    assert set(review_surfaces) == {
        "private_review_readme",
        "private_review_boundaries",
        "private_user_review_handoff",
        "private_public_release_review_checklist",
        "private_review_site_index",
        "private_kg_browser",
    }
    for row in review_surfaces.values():
        assert row["verification_status"] == "pass"
        assert row["exists"] is True
        assert row["missing_required_phrases"] == []
        assert row["empty_markdown_table_cell_count"] == 0
        assert row["public_release_authorized"] is False
        assert row["method_recommendation_authorized"] is False
        assert row["positive_claim_promotion_authorized"] is False
    site_quality = payload["private_static_site_quality"]
    assert site_quality["overall_status"] == "pass"
    assert site_quality["visual_smoke_status"] == "pass"
    assert site_quality["visual_smoke_issue_count"] == 0
    assert site_quality["visual_smoke_layout_guard_status"] == "pass"
    assert site_quality["visual_smoke_first_screen_status"] == "pass"
    assert site_quality["missing_visual_layout_guards"] == []
    assert site_quality["missing_visual_first_screen_phrases"] == []
    assert site_quality["broken_local_links"] == []
    assert site_quality["boundary_violations"] == []
    assert site_quality["kg_browser_summary_matches_payload"] is True
    navigation_rows = {
        row["surface_id"]: row for row in payload["private_static_site_navigation_rows"]
    }
    assert set(navigation_rows) == {
        "site_index_html",
        "site_kg_browser_html",
        "site_kg_browser_data_json",
        "site_visual_smoke_static_guards",
    }
    assert all(row["status"] == "pass" for row in navigation_rows.values())
    assert navigation_rows["site_index_html"]["local_link_count"] > 10
    assert navigation_rows["site_kg_browser_html"]["local_link_count"] == 2
    assert navigation_rows["site_kg_browser_data_json"]["node_count"] == graph[
        "node_count"
    ]
    assert navigation_rows["site_kg_browser_data_json"]["edge_count"] == graph[
        "edge_count"
    ]
    assert (
        navigation_rows["site_visual_smoke_static_guards"][
            "missing_layout_guard_count"
        ]
        == 0
    )
    assert (
        navigation_rows["site_visual_smoke_static_guards"][
            "missing_first_screen_phrase_count"
        ]
        == 0
    )
    assert (
        package_root
        / "metadata/private_sterile_publication_package_manifest.json"
    ).exists()
    assert not list(package_root.rglob("__pycache__"))
    assert not list(package_root.rglob("*.pyc"))
    assert not (package_root / "review_only/draft_visual_table_artifacts").exists()
    assert not list(package_root.rglob("*private_publication_repository_remote_audit*"))


def test_private_sterile_package_blocks_before_copy_if_release_cut_opens_public_release(
    tmp_path,
):
    release_cut = json.loads((ROOT / package.RELEASE_CUT).read_text(encoding="utf-8"))
    release_cut["summary"]["public_release_authorized"] = True
    release_cut_path = tmp_path / "release_cut.json"
    release_cut_path.write_text(json.dumps(release_cut), encoding="utf-8")
    package_root = tmp_path / "blocked_package"

    payload = package.build_payload(
        repo_root=ROOT,
        package_root=package_root,
        initialize_git=False,
        release_cut_path=release_cut_path,
    )
    checks = {row["check_id"]: row for row in payload["checks"]}

    assert payload["summary"]["overall_status"] == (
        "private_sterile_publication_package_blocked"
    )
    assert payload["summary"]["copied_file_count"] == 0
    assert checks["release_cut_authorizes_private_package_only"]["status"] == "fail"
    assert not package_root.exists()


def test_checked_in_private_sterile_package_manifest_records_ready_state():
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    summary = payload["summary"]

    assert summary["overall_status"] == "private_sterile_publication_package_ready"
    assert summary["copied_file_count"] > 100
    assert summary["source_artifact_count"] >= 46
    assert summary["private_latex_html_output_audit_status"] == (
        "private_latex_html_review_output_audit_pass"
    )
    assert summary["excluded_file_count"] >= 1
    assert summary["path_risk_hit_count"] == 0
    assert summary["secret_pattern_hit_count"] == 0
    assert summary["public_release_authorized"] is False
    assert summary["working_repository_final_citable"] is False
    assert summary["method_recommendation_authorized"] is False
    assert summary["positive_claim_promotion_authorized"] is False
    assert summary["raw_data_or_secret_inclusion_authorized"] is False
    assert summary["generated_review_surface_count"] == 6
    assert summary["generated_review_surface_pass_count"] == 6
    assert summary["generated_review_surface_missing_count"] == 0
    assert summary["generated_review_surface_phrase_issue_count"] == 0
    assert summary["generated_review_surface_empty_table_cell_count"] == 0
    assert summary["private_static_site_quality_status"] == "pass"
    assert summary["private_static_site_broken_local_link_count"] == 0
    assert summary["private_static_site_missing_required_phrase_count"] == 0
    assert summary["private_static_site_boundary_violation_count"] == 0
    assert summary["private_static_site_kg_data_status"] == "pass"
    assert summary["private_static_site_visual_smoke_status"] == "pass"
    assert summary["private_static_site_visual_smoke_issue_count"] == 0
    assert summary["private_static_site_layout_guard_status"] == "pass"
    assert summary["private_static_site_first_screen_status"] == "pass"
    assert summary["private_static_site_navigation_row_count"] == 4
    assert summary["private_static_site_navigation_pass_count"] == 4
    assert summary["private_static_site_navigation_issue_count"] == 0
    assert summary["reviewer_front_door_row_count"] == 4
    assert summary["review_at_a_glance_row_count"] == 6
    assert summary["first_ten_minute_review_row_count"] == 5
    assert summary["reviewer_acceptance_row_count"] == 5
    assert summary["research_question_row_count"] == 6
    assert summary["contribution_finding_row_count"] == 7
    assert summary["paper_architecture_row_count"] == 5
    assert summary["claim_safe_reading_row_count"] == 8
    assert summary["claim_evidence_review_row_count"] == 8
    assert summary["provenance_graph_log_row_count"] == 5
    assert summary["repository_map_row_count"] == 9
    assert summary["reader_contract_row_count"] == 4
    assert summary["kg_browser_guided_trace_preset_count"] == 7
    graph = json.loads(KG_QUALITY.read_text(encoding="utf-8"))["graph"]
    assert summary["kg_browser_node_count"] == graph["node_count"]
    assert summary["kg_browser_edge_count"] == graph["edge_count"]
    assert len(payload["reviewer_front_door_rows"]) == 4
    assert len(payload["review_at_a_glance_rows"]) == 6
    assert len(payload["first_ten_minute_review_rows"]) == 5
    assert len(payload["reviewer_acceptance_rows"]) == 5
    assert len(payload["repository_map_rows"]) == 9
    assert len(payload["reader_contract_rows"]) == 4
    assert len(payload["paper_architecture_rows"]) == 5
    assert summary["kg_browser_node_type_count"] > 0
    assert summary["kg_browser_relation_type_count"] > 0
    assert summary["local_git_initialized"] is False
    assert summary["local_git_commit"] is None
    assert summary["failed_check_count"] == 0
    rows = {
        row["surface_id"]: row
        for row in payload["generated_review_surface_rows"]
    }
    assert all(
        row["empty_markdown_table_cell_count"] == 0
        for row in rows.values()
    )
    assert rows["private_user_review_handoff"]["package_path"] == (
        "USER_REVIEW_HANDOFF.md"
    )
    assert rows["private_public_release_review_checklist"]["package_path"] == (
        "PUBLIC_RELEASE_REVIEW_CHECKLIST.md"
    )
    assert rows["private_review_site_index"]["package_path"] == "site/index.html"
    assert rows["private_kg_browser"]["package_path"] == "site/kg_browser.html"
    checks = {row["check_id"]: row for row in payload["checks"]}
    assert checks["private_static_site_quality_passes"]["status"] == "pass"
    assert payload["private_static_site_quality"]["overall_status"] == "pass"
    navigation_rows = {
        row["surface_id"]: row for row in payload["private_static_site_navigation_rows"]
    }
    assert set(navigation_rows) == {
        "site_index_html",
        "site_kg_browser_html",
        "site_kg_browser_data_json",
        "site_visual_smoke_static_guards",
    }
    assert all(row["status"] == "pass" for row in navigation_rows.values())
    assert all(row["broken_local_link_count"] == 0 for row in navigation_rows.values())
    assert all(
        row["boundary_violation_count"] == 0 for row in navigation_rows.values()
    )
    assert (
        navigation_rows["site_visual_smoke_static_guards"][
            "missing_layout_guard_count"
        ]
        == 0
    )
    assert "Private Static Site Navigation Integrity" in (
        ROOT
        / "experiments/regression/manuscript/"
        / "private_sterile_publication_package_manifest.md"
    ).read_text(encoding="utf-8")
    assert payload["private_static_site_quality"]["visual_smoke_status"] == "pass"
    assert payload["private_static_site_quality"]["visual_smoke_issue_count"] == 0
    copied_paths = {row["package_path"] for row in payload["copied_files"]}
    assert "manuscript/research_document.md" in copied_paths
    assert "manuscript/research_document.json" in copied_paths
    assert "governance/publication_authoring_decision_record.md" in copied_paths
    assert "governance/publication_authoring_decision_record.json" in copied_paths
    assert "provenance/data_scientist_log.md" in copied_paths
    assert "provenance/graphs/data_flow.mmd" in copied_paths
    assert "provenance/graphs/control_flow.mmd" in copied_paths
    assert "provenance/graphs/dependency_graph.mmd" in copied_paths
    assert "provenance/graphs/system_ontology.mmd" in copied_paths


def test_markdown_table_empty_cell_guard_detects_blank_review_cells():
    assert package.count_empty_markdown_table_cells("| A | B |\n|---|---|\n| x | y |\n") == 0
    assert package.count_empty_markdown_table_cells("| A | B |\n|---|---|\n|  | y |\n") == 1
    assert package.count_empty_markdown_table_cells("| A | B | C |\n|---|---|---|\n| x |  |  |\n") == 2
