# Maintenance Gate Matrix

This matrix records the public maintenance and CI gates currently attached to the Research Atlas. It distinguishes implemented public gates from planned sustainability work so the atlas does not imply broader maintenance coverage than it has.

## Summary

- overall_status: `maintenance_gates_defined_modularization_pending`
- gate_count: `9`
- implemented_gate_count: `5`
- partial_gate_count: `1`
- planned_gate_count: `3`
- ci_enforced_gate_count: `5`

## Gates

| Gate | Status | CI enforced | Scope | Remaining work |
|---|---|---:|---|---|
| Public smoke CI | `implemented` | `True` | public package install, artifact smoke checks, and root command help | Keep expanding public smoke coverage as new atlas surfaces are added. |
| Package content gate | `implemented` | `True` | experiment configs, public rebuild modules, and runner entry points | Add checksum checks for future larger release assets. |
| Reader-language gate | `implemented` | `True` | public README, HTML article/supplement/document, atlas, KG, and evidence pages | Add any newly rejected public phrases to the scanner before release. |
| Link and schema smoke gate | `implemented` | `True` | local links, indexed public artifacts, KG schema, and manifest coverage | Add browser-level crawl checks for dynamically generated route states. |
| Public environment lock | `implemented` | `True` | public smoke-test dependency surface | Add a full experiment container or lockfile before Benchmark v2 execution. |
| Accessibility and academic metadata gate | `partial` | `False` | main public pages and atlas pages | Add automated axe/lighthouse-style checks and tagged-PDF validation. |
| Lint, type, and security gates | `planned` | `False` | Python style, import hygiene, type surface, dependency and secret scanning | Introduce ruff, mypy/pyright subset, pip-audit, and secret scan gates after public/private test split stabilizes. |
| Builder modularization gate | `planned` | `False` | knowledge graph and publication builders | Split builders into DAG tasks with shared schema, path, provenance, and rendering helpers. |
| Schema migration gate | `planned` | `False` | versioned atlas, KG, evidence, and result-cube schemas | Add schema fixtures and migration tests before Benchmark v2 results are generated. |
