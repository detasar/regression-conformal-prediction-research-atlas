# Final Audit Response Matrix

This matrix records how the Research Atlas responds to the final external audit. It separates completed public-readiness repairs from forward protocol work and larger maintenance work.

| Priority | Item | Status | Evidence |
|---|---|---|---|
| P0 | Rename the one-sided coverage gate and selected-cell semantics. | `completed` | `atlas/results/result_cube_public.csv`<br>`atlas/results/selected_under_coverage_gate_cells.csv`<br>`reproducibility/tests/test_public_research_atlas_smoke.py` |
| P0 | Use pipeline-level empirical wording for the CQR signal. | `completed` | `README.md`<br>`paper/research_document.html`<br>`evidence/claim_evidence_matrix.md` |
| P0 | Keep row-level bands out of headline inferential language. | `completed` | `paper/article.html`<br>`paper/supplement.html`<br>`reproducibility/tests/test_public_research_atlas_smoke.py` |
| P0 | Publish public rebuild modules, default CLI config resolution, package-data configs, and wheel checks. | `completed` | `reproducibility/experiments/regression/scripts/build_public_research_atlas.py`<br>`reproducibility/experiments/regression/scripts/build_research_atlas_package.py`<br>`reproducibility/experiments/regression/scripts/build_public_release_scope.py`<br>`pyproject.toml`<br>`.github/workflows/public-ci.yml` |
| P0 | Expose provenance as manifest resolution rather than pretending private source files are public. | `completed` | `atlas/provenance/artifact_manifest.json`<br>`evidence/public_artifact_manifest.json`<br>`site/kg_browser_data.json` |
| P0 | Add numerical pathology flags and display policy fields. | `completed` | `atlas/results/result_cube_public.csv`<br>`atlas/results/index.html` |
| P0 | Link substantive public artifacts from the HTML artifact index. | `completed` | `atlas/artifacts/index.html`<br>`atlas/artifacts/public_artifact_index.json` |
| P1 | Define the balanced, paired, leakage-safe Benchmark v2 before new result generation. | `protocol_defined_not_executed` | `atlas/scope/benchmark_v2_protocol.md`<br>`atlas/scope/benchmark_v2_protocol.json` |
| P1 | Build the interactive result-atlas layer. | `partially_completed` | `atlas/results/index.html`<br>`atlas/ui_data/dataset_method_heatmap.json`<br>`atlas/ui_data/method_family_summary.json` |
| P1 | Improve KG loading architecture beyond the current static full-graph JSON. | `planned` | `site/kg_browser.html`<br>`site/kg_browser_data.json` |
| P2 | Modularize monolithic builders and add broader maintenance gates. | `planned` | `reproducibility/experiments/regression/scripts/` |

P0 items are required public-readiness repairs. P1/P2 items remain forward work unless marked completed.
