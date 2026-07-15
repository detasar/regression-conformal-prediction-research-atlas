# Public Schema Registry

This registry records the public schema identifiers and required fields that readers and smoke tests can rely on for the Atlas v0 release line.

| Artifact | Schema | Format | Required fields | Migration fixture |
|---|---|---|---|---|
| `site/kg_browser_data.json` | `regression_cp_evidence_graph_v2` | `json` | `schema`, `summary`, `nodes`, `edges`, `research_map` | `kg_provenance_label_v0_to_v1` |
| `site/kg_browser_index.json` | `regression_cp_evidence_graph_index_v1` | `json` | `schema`, `summary`, `nodes`, `research_map` | `kg_index_split_from_full_graph_v1` |
| `site/kg_browser_edges.json` | `regression_cp_evidence_graph_edges_v1` | `json` | `schema`, `summary`, `edges` | `kg_index_split_from_full_graph_v1` |
| `evidence/public_artifact_manifest.json` | `regression_cp_public_artifact_manifest_v1` | `json` | `schema`, `strategy`, `summary`, `artifacts` | `public_manifest_included_to_file_included_v1` |
| `evidence/claim_evidence_matrix.json` | `regression_cp_claim_evidence_matrix_public_v1` | `json` | `schema`, `summary`, `claims` | `claim_matrix_public_v1` |
| `atlas/artifacts/public_artifact_index.json` | `regression_cp_public_artifact_index_v1` | `json` | `schema`, `artifact_count`, `artifacts` | `artifact_index_public_v1` |
| `atlas/results/result_cube_public.csv` | `regression_cp_result_cube_public_v1` | `csv` | `dataset_id`, `alpha`, `method_label`, `coverage_lower_bound_pass`, `selected_under_coverage_gate`, `numerical_pathology_flag`, `display_interval_policy` | `result_cube_selection_labels_v0_to_v1` |
| `atlas/scope/audit_response_matrix.json` | `regression_cp_final_audit_response_matrix_v1` | `json` | `schema`, `summary`, `rows` | `audit_response_matrix_public_v1` |
| `atlas/maintenance/maintenance_gate_matrix.json` | `regression_cp_public_maintenance_gate_matrix_v1` | `json` | `schema`, `summary`, `gates` | `maintenance_gate_matrix_public_v1` |

## Policy

- Public readers may rely on these schema identifiers and required fields inside the Atlas v0 release line.
- Any removal or rename of a required field must add a migration fixture and a public smoke assertion before regenerated results are published.
- Benchmark v2 result artifacts must either use these schemas or publish v2 schemas with explicit fixtures before execution results are merged.
