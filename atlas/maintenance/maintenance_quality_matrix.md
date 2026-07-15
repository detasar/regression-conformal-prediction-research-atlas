# Maintenance Quality Matrix

This matrix records the public maintenance and CI checks currently attached to the Research Atlas. It distinguishes implemented checks from planned sustainability work so the atlas does not imply broader maintenance coverage than it has.

## Summary

- overall_status: `source_backed_public_builder_modularization_started`
- check_count: `9`
- implemented_check_count: `6`
- partial_check_count: `3`
- planned_check_count: `0`
- ci_enforced_check_count: `8`

## Checks

| Check | Status | CI enforced | Scope | Remaining work |
|---|---|---:|---|---|
| Public smoke CI | `implemented` | `True` | public package install, rebuild commands, artifact/schema/link checks, reader-surface checks, and runner entry points | Keep expanding public smoke lanes as new atlas surfaces are added. |
| Package content check | `implemented` | `True` | experiment configs, public rebuild modules, and runner entry points | Add checksum checks for future larger release assets. |
| Reader-language check | `implemented` | `True` | public README, HTML article/supplement/document, atlas, KG, and evidence pages | Add any newly rejected public phrases to the scanner before publication. |
| Link and schema smoke check | `implemented` | `True` | local links, indexed public artifacts, KG schema, and manifest coverage | Add browser-level crawl checks for dynamically generated route states. |
| Public environment lock | `implemented` | `True` | public smoke-test dependency surface | Add a full experiment container or lockfile before Benchmark v2 execution. |
| Accessibility and academic metadata check | `partial` | `False` | main public pages and atlas pages | Add automated axe/lighthouse-style checks and tagged-PDF validation. |
| Lint, type, and security checks | `partial` | `True` | Python style, import hygiene, type surface, dependency and secret scanning | Add ruff, mypy/pyright subset, and pip-audit gates after the public package dependency surface stabilizes. |
| Builder modularization check | `partial` | `True` | knowledge graph and publication builders | Continue splitting large source builders into DAG tasks with shared schema, path, provenance, and rendering helpers. |
| Schema migration check | `implemented` | `True` | versioned atlas, KG, evidence, and result-cube schemas | Extend the registry when Benchmark v2 result schemas are generated. |
