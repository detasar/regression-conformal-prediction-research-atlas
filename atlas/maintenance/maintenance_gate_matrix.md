# Maintenance Gate Matrix

This matrix records the public maintenance and CI gates currently attached to the Research Atlas. It distinguishes implemented public gates from planned sustainability work so the atlas does not imply broader maintenance coverage than it has.

## Summary

- overall_status: `schema_migration_seeded_modularization_pending`
- gate_count: `9`
- implemented_gate_count: `6`
- partial_gate_count: `3`
- planned_gate_count: `0`
- ci_enforced_gate_count: `8`

## Gates

| Gate | Status | CI enforced | Scope | Remaining work |
|---|---|---:|---|---|
| Public smoke CI | `implemented` | `True` | public package install, artifact smoke checks, and root command help | Keep expanding public smoke coverage as new atlas surfaces are added. |
| Package content gate | `implemented` | `True` | experiment configs, public rebuild modules, and runner entry points | Add checksum checks for future larger release assets. |
| Reader-language gate | `implemented` | `True` | public README, HTML article/supplement/document, atlas, KG, and evidence pages | Add any newly rejected public phrases to the scanner before release. |
| Link and schema smoke gate | `implemented` | `True` | local links, indexed public artifacts, KG schema, and manifest coverage | Add browser-level crawl checks for dynamically generated route states. |
| Public environment lock | `implemented` | `True` | public smoke-test dependency surface | Add a full experiment container or lockfile before Benchmark v2 execution. |
| Accessibility and academic metadata gate | `partial` | `False` | main public pages and atlas pages | Add automated axe/lighthouse-style checks and tagged-PDF validation. |
| Lint, type, and security gates | `partial` | `True` | Python style, import hygiene, type surface, dependency and secret scanning | Add ruff, mypy/pyright subset, and pip-audit gates after the public package dependency surface stabilizes. |
| Builder modularization gate | `partial` | `True` | knowledge graph and publication builders | Continue splitting large source builders into DAG tasks with shared schema, path, provenance, and rendering helpers. |
| Schema migration gate | `implemented` | `True` | versioned atlas, KG, evidence, and result-cube schemas | Extend the registry when Benchmark v2 result schemas are generated. |
