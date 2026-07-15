# Regression CP Research Atlas

This atlas makes the experiment universe visible: scope, datasets, methods, result cube, interpretation boundaries, and provenance.

## At A Glance

- Publication-scoped completed rows: 145,839
- Canonical completed rows: 156,233
- Publication datasets: 67
- Dataset-alpha cells: 95
- Publication method labels: 28
- Result cube rows: 641
- Knowledge graph: 3,643 nodes / 21,019 edges / 0 isolated nodes

## Directory Map

- `scope/` records the accounting boundary and row-unit definition.
- `datasets/` records public aggregate dataset catalog entries, source metadata, and cards.
- `methods/` records method labels, families, ontology, and cards.
- `results/` records the public aggregate result cube and selected result surfaces.
- `claims/` records interpretation scope and evidence-supported statements.
- `provenance/` records source status, hashes, RO-Crate metadata, and PROV traces.
- `ui_data/` contains compact JSON used by the public website.
- `maintenance/` records public CI and maintenance gates.
- `scope/benchmark_v2_protocol.*` records the frozen design requirements for the next balanced benchmark.
- `scope/benchmark_v2_execution_manifest.*` records the paired run-grid contract for Benchmark v2.
- `scope/benchmark_v2_public_evidence_contract.*` records the minimum public evidence required before Benchmark v2 result interpretation.
- `benchmark_v2/preflight/` records public preflight templates, run-grid cardinality, and readiness gates before Benchmark v2 execution.
- `benchmark_v2/candidates/` records draft source and task-variant registries for Benchmark v2 planning.
- `scope/audit_response_matrix.*` records the response to the final external audit.
- `scope/planned_attempted_completed_matrix.*` records which accounting phases are public aggregates and which require restricted source ledgers.

Use this atlas as the citable record for the audited experiment. Broader conclusions require separate validation.
