# Schema Migration Fixtures

These fixtures pin the field-renaming and split-schema conventions that were introduced while preparing the public Research Atlas. They are intentionally small and are exercised by the public smoke tests.

| Fixture | Family | Source schema | Target schema | Status |
|---|---|---|---|---|
| `result_cube_selection_labels_v0_to_v1` | `result_cube` | `regression_cp_result_cube_public_legacy_v0` | `regression_cp_result_cube_public_v1` | `covered_by_public_smoke` |
| `kg_provenance_label_v0_to_v1` | `knowledge_graph` | `regression_cp_evidence_graph_public_legacy_v0` | `regression_cp_evidence_graph_v2` | `covered_by_public_smoke` |
| `public_manifest_included_to_file_included_v1` | `public_artifact_manifest` | `regression_cp_public_artifact_manifest_legacy_v0` | `regression_cp_public_artifact_manifest_v1` | `covered_by_public_smoke` |
| `kg_index_split_from_full_graph_v1` | `knowledge_graph_lazy_loading` | `regression_cp_evidence_graph_v2` | `regression_cp_evidence_graph_index_v1 + regression_cp_evidence_graph_edges_v1` | `covered_by_public_smoke` |
| `claim_matrix_public_v1` | `claim_evidence_matrix` | `regression_cp_claim_evidence_matrix_public_v1` | `regression_cp_claim_evidence_matrix_public_v1` | `covered_by_public_smoke` |
| `artifact_index_public_v1` | `artifact_index` | `regression_cp_public_artifact_index_v1` | `regression_cp_public_artifact_index_v1` | `covered_by_public_smoke` |
| `audit_response_matrix_public_v1` | `audit_response_matrix` | `regression_cp_final_audit_response_matrix_v1` | `regression_cp_final_audit_response_matrix_v1` | `covered_by_public_smoke` |
| `maintenance_gate_matrix_public_v1` | `maintenance_gate_matrix` | `regression_cp_public_maintenance_gate_matrix_v1` | `regression_cp_public_maintenance_gate_matrix_v1` | `covered_by_public_smoke` |
