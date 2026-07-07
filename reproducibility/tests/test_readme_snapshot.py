import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _flat_text(text: str) -> str:
    return " ".join(text.split())


def _readmes() -> tuple[str, str]:
    return (
        (ROOT / "README.md").read_text(),
        (ROOT / "experiments/regression/README.md").read_text(),
    )


def test_readmes_explain_how_to_rebuild_inventory_without_static_counts():
    root_readme, regression_readme = _readmes()

    for text in (root_readme, regression_readme):
        assert (
            "Run these commands from the repository root instead of trusting stale numbers"
            in text
        )
        assert "git ls-files 'experiments/regression/audits/**/audit.json'" in text
        assert "experiments/regression/catalogs/knowledge_graph.json" in text
        assert "| Artifact | Git-tracked value |" not in text
        assert "Status rows represented by committed pilot summaries" not in text
        assert "<!-- BEGIN: observed-method-ids -->" not in text

    assert "Print the checked-in pilot-summary index from source files" in regression_readme


def test_readmes_state_claim_boundaries():
    root_readme, regression_readme = _readmes()

    for text in (root_readme, regression_readme):
        assert "not a completed empirical paper" in _flat_text(text)
        assert "exhaustive internet dataset coverage" in text
        assert "exhaustive conformal-regression literature coverage" in text
        assert "a globally best conformal method" in text
        assert "publication-ready fairness conclusions" in text

    assert "If this README conflicts" in root_readme
    assert "Use this precedence order" in regression_readme


def test_readmes_warn_that_readme_is_not_experiment_evidence():
    root_readme, regression_readme = _readmes()

    for text in (root_readme, regression_readme):
        flat = _flat_text(text)
        assert "README prose alone" in text
        assert "git status --short --branch" in text
        assert "git log -1 --oneline" in text
        assert "local uncommitted work" in flat or "Local ignored runtime folders" in flat

    assert "Use this README as a map, not as evidence" in root_readme
    assert "not a live view" in regression_readme


def test_readmes_do_not_embed_method_leaderboards():
    root_readme, regression_readme = _readmes()

    forbidden_fragments = [
        "globally best method is",
        "best conformal method is",
        "recommended conformal method is",
        "interval-score minimum:",
        "closest nominal marginal coverage:",
        "smallest group coverage gap:",
        "Score-Min Coverage Caveats",
        "Aggregate Readout",
        "Machine-Checked Aggregate Readout",
        "Lowest interval-score row",
        "lowest interval-score row",
    ]
    for text in (root_readme, regression_readme):
        for fragment in forbidden_fragments:
            assert fragment not in text


def test_readmes_do_not_embed_static_dataset_or_method_counts():
    root_readme, regression_readme = _readmes()
    forbidden_patterns = [
        r"Audit JSON files\s*\|\s*\d+",
        r"Regression configs\s*\|\s*\d+",
        r"Pilot summary JSON files\s*\|\s*\d+",
        r"Dataset IDs in pilot summaries\s*\|\s*\d+",
        r"CP method IDs observed in pilot summaries\s*\|\s*\d+",
        r"Knowledge graph nodes\s*\|\s*\d+",
        r"completed=\d",
        r"skipped_method=\d",
    ]

    for text in (root_readme, regression_readme):
        for pattern in forbidden_patterns:
            assert re.search(pattern, text) is None


def test_readmes_do_not_embed_static_promoted_dataset_lists():
    root_readme, regression_readme = _readmes()

    forbidden_fragments = [
        "Small OpenML promotions such as",
        "Basketball, Auto Price",
        "Mercury in Bass, seropositive",
    ]
    for text in (root_readme, regression_readme):
        for fragment in forbidden_fragments:
            assert fragment not in text


def test_readmes_keep_venn_abers_regression_claim_boundary():
    root_readme, regression_readme = _readmes()

    assert "`venn_abers_quantile`" in root_readme
    assert "`venn_abers_split_fallback`" in root_readme
    assert "not as validated\nregression coverage evidence" in root_readme
    assert "not an exact or validated Venn-Abers regression solution" in root_readme
    assert "`venn_abers_quantile`" in regression_readme
    assert "`venn_abers_split_fallback`" in regression_readme
    assert "diagnostic\nbridge only" in regression_readme
    assert "ordinary split-conformal safety envelope" in regression_readme
    assert (
        "not as validated Venn-Abers regression coverage evidence"
        in _flat_text(regression_readme)
    )
