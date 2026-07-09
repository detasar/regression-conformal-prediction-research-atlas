"""Build a machine-readable knowledge graph for regression experiments."""

from __future__ import annotations

import argparse
import glob
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

import yaml

from cpfi.regression.experiment import atomic_write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-candidates",
        default="experiments/regression/catalogs/dataset_candidates.jsonl",
    )
    parser.add_argument(
        "--method-registry",
        default="experiments/regression/catalogs/method_registry.json",
    )
    parser.add_argument(
        "--audit-index",
        default="experiments/regression/catalogs/audit_index.json",
    )
    parser.add_argument(
        "--openml-review-decisions",
        default="experiments/regression/catalogs/openml_review_decisions.jsonl",
    )
    parser.add_argument(
        "--manuscript-claim-register",
        default="experiments/regression/catalogs/manuscript_claim_register.json",
    )
    parser.add_argument(
        "--config-glob",
        default="experiments/regression/configs/*.yaml",
    )
    parser.add_argument(
        "--out",
        default="experiments/regression/catalogs/knowledge_graph.json",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def node_summary(node_id: str, node_type: str, attrs: dict) -> str:
    for key in (
        "summary",
        "purpose",
        "notes",
        "description",
        "fairness_relevance",
        "reason",
    ):
        value = attrs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    path = attrs.get("path") or attrs.get("json_path") or attrs.get("audit_path")
    label = (
        attrs.get("name")
        or attrs.get("method_id")
        or attrs.get("experiment_id")
        or node_id
    )
    if node_type == "dataset":
        target = attrs.get("target")
        source = attrs.get("source")
        return (
            f"Dataset {label} for target {target} from {source}."
            if target
            else f"Dataset {label}."
        )
    if node_type == "method_config":
        method_id = attrs.get("method_id") or label
        params = attrs.get("params")
        if isinstance(params, dict) and params:
            param_text = ", ".join(
                f"{key}={value}" for key, value in sorted(params.items())
            )
            return f"Method configuration {label} for {method_id} with {param_text}."
        return f"Method configuration {label} for base method {method_id}."
    if node_type == "method":
        return f"Regression conformal method {label}."
    if node_type == "model":
        family = attrs.get("family")
        return f"Regression model {label}" + (
            f" in family {family}." if family else "."
        )
    if node_type == "metric":
        return f"Regression evaluation metric {label}."
    if node_type == "commit":
        return f"Git commit evidence node {label}."
    if path:
        return f"{node_type.replace('_', ' ').title()} evidence at {path}."
    return f"{node_type.replace('_', ' ').title()} node {label}."


def add_node(nodes: dict[str, dict], node_id: str, node_type: str, **attrs) -> None:
    clean_attrs = {key: value for key, value in attrs.items() if value is not None}
    summary = node_summary(node_id, node_type, clean_attrs)
    observations = list(clean_attrs.pop("observations", []))
    if summary and summary not in observations:
        observations.insert(0, summary)
    existing = nodes.get(node_id, {})
    existing_observations = list(existing.get("observations", []))
    merged_observations = []
    for value in [*existing_observations, *observations]:
        if value not in merged_observations:
            merged_observations.append(value)
    nodes[node_id] = {
        **existing,
        "id": node_id,
        "type": node_type,
        **clean_attrs,
        "summary": existing.get("summary") or summary,
        "observations": merged_observations,
    }


MAX_MULTIPLICITY_EVIDENCE_SAMPLES = 12
TOPOLOGY_OBSERVATION_PREFIX = "KG topology observation:"
CONFIDENCE_MODEL_VERSION = "kg_edge_confidence_v2"


def add_edge(
    edges: list[dict], source: str, target: str, relation: str, **attrs
) -> None:
    edge = {
        "source": source,
        "target": target,
        "relation": relation,
        "source_file": attrs.pop(
            "source_file",
            "experiments/regression/scripts/build_knowledge_graph.py",
        ),
        **attrs,
    }
    if "confidence" in attrs:
        edge["confidence"] = attrs["confidence"]
    edge.setdefault("provenance_id", f"{source}|{relation}|{target}")
    edges.append(edge)


def yaml_selector(
    field: str, value: object | None = None, *, key: str | None = None
) -> str:
    if value is None:
        return field
    if key:
        return f"{field}[?{key} == {json.dumps(str(value), sort_keys=True)}]"
    return f"{field}[?value == {json.dumps(str(value), sort_keys=True)}]"


def json_array_selector(
    field: str, value: object | None = None, *, root: str = "$"
) -> str:
    if value is None:
        return f"{root}[*]"
    return f"{root}[?(@.{field} == {json.dumps(str(value), sort_keys=True)})]"


def markdown_section_selector(section: str) -> str:
    return f"markdown_heading:{section}"


def row_selector(collection: str, index: int, field: str) -> str:
    return f"{collection}[{index}].{field}"


def artifact_root_selector(evidence_path: str | Path) -> str:
    suffix = Path(str(evidence_path)).suffix.lower()
    if suffix in {".json", ".yaml", ".yml"}:
        return "$"
    if suffix == ".jsonl":
        return "$[*]"
    if suffix == ".md":
        return "markdown_document"
    return "artifact_root"


def dataset_payload_selector(payload: object, dataset_id: object) -> str:
    dataset_text = str(dataset_id)
    if isinstance(payload, dict):
        if str(payload.get("dataset_id") or "") == dataset_text:
            return "dataset_id"
        dataset_ids = payload.get("dataset_ids")
        if isinstance(dataset_ids, list) and dataset_text in {
            str(item) for item in dataset_ids
        }:
            return yaml_selector("dataset_ids", dataset_text)
        dataset_counts = payload.get("dataset_counts")
        if isinstance(dataset_counts, dict) and dataset_text in {
            str(key) for key in dataset_counts
        }:
            return f"dataset_counts.{dataset_text}"
    return f"dataset_reference:{dataset_text}"


NODE_PATH_KEYS = ("json_path", "path", "audit_path", "ledger_path", "report_path")
ARTIFACT_SUPPORT_NODE_TYPE_PRIORITY = (
    "report",
    "manifest",
    "config",
    "catalog",
    "method_spec",
    "dataset_audit",
    "dataset_profile",
)
ARTIFACT_PATH_NODE_ID_OVERRIDES = {
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "final_selection_claim_boundary_audit.json"
    ): ["report:final_selection_claim_boundary_audit"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "publication_methodology_audit.json"
    ): ["report:publication_methodology_audit"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "neutral_reporting_language_audit.json"
    ): ["report:neutral_reporting_language_audit"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "neutral_experiment_closure_audit.json"
    ): ["report:neutral_experiment_closure_audit"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "fairness_population_readiness_audit.json"
    ): ["report:fairness_population_readiness_audit"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "fairness_group_diagnostic_audit.json"
    ): ["report:fairness_group_diagnostic_audit"],
    (
        "experiments/regression/manuscript/"
        "fairness_group_multiplicity_scope.json"
    ): ["report:fairness_group_multiplicity_scope"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_validation_readiness_audit.json"
    ): ["report:venn_abers_validation_readiness_audit"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_grid_ivapd_validation_protocol.json"
    ): ["report:venn_abers_grid_ivapd_validation_protocol"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_grid_expansion_plan.json"
    ): ["report:venn_abers_grid_expansion_plan"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_grid_failure_mode_decomposition.json"
    ): ["report:venn_abers_grid_failure_mode_decomposition"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_claim_gate_matrix.json"
    ): ["report:venn_abers_claim_gate_matrix"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_negative_evidence_disposition_audit.json"
    ): ["report:venn_abers_negative_evidence_disposition_audit"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_grid_expansion_batch.json"
    ): ["report:venn_abers_grid_expansion_batch"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_alpha_expansion_batch.json"
    ): ["report:method_selection_alpha_expansion_batch"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_alpha_expansion_execution_audit.json"
    ): ["report:method_selection_alpha_expansion_execution_audit"],
    (
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_inferential_audit.json"
    ): ["report:method_selection_inferential_audit"],
}

RELATION_FALLBACK_EVIDENCE = {
    "BELONGS_TO_FAMILY": "experiments/regression/catalogs/dataset_candidates.jsonl",
    "CITES_SOURCES": "experiments/regression/catalogs/knowledge_graph.json",
    "CONFIGURES_METHOD": "experiments/regression/configs",
    "DECIDES_DATASET": "experiments/regression/catalogs/dataset_candidates.jsonl",
    "DERIVED_FROM": "experiments/regression/catalogs/openml_ranked_candidates.jsonl",
    "FROM_SOURCE": "experiments/regression/catalogs/dataset_candidates.jsonl",
    "GOVERNED_BY": "experiments/regression/policies/data_policy_registry.md",
    "MIRRORS_DATASET": "experiments/regression/catalogs/dataset_candidates.jsonl",
    "RECORDED_IN": "experiments/regression/catalogs/dataset_candidates.jsonl",
    "REVIEWS_SOURCE": "experiments/regression/catalogs/openml_review_decisions.jsonl",
    "VARIANT_OF_DATASET": "experiments/regression/catalogs/dataset_candidates.jsonl",
    "VARIANT_OF_METHOD": "experiments/regression/method_specs/split_and_cqr_regression.md",
}


def first_node_path(node: dict | None) -> str | None:
    if not node:
        return None
    for key in NODE_PATH_KEYS:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def normalize_artifact_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized or None


def build_node_path_index(nodes: dict[str, dict]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for node_id, node in nodes.items():
        for key in NODE_PATH_KEYS:
            path = normalize_artifact_path(node.get(key))
            if path:
                index.setdefault(path, []).append(node_id)
    return index


def artifact_support_node_ids(
    nodes: dict[str, dict],
    path_index: dict[str, list[str]],
    artifact_path: object,
) -> list[str]:
    path = normalize_artifact_path(artifact_path)
    if not path:
        return []
    candidates = path_index.get(path, [])
    if not candidates:
        return list(ARTIFACT_PATH_NODE_ID_OVERRIDES.get(path, []))

    def rank(node_id: str) -> tuple[int, str]:
        node_type = str(nodes.get(node_id, {}).get("type") or "")
        try:
            priority = ARTIFACT_SUPPORT_NODE_TYPE_PRIORITY.index(node_type)
        except ValueError:
            priority = len(ARTIFACT_SUPPORT_NODE_TYPE_PRIORITY)
        return priority, node_id

    ranked = sorted(candidates, key=rank)
    best_priority = rank(ranked[0])[0]
    return [node_id for node_id in ranked if rank(node_id)[0] == best_priority]


def infer_edge_evidence_path(edge: dict, nodes: dict[str, dict]) -> str | None:
    relation = str(edge.get("relation"))
    source = nodes.get(str(edge.get("source")))
    target = nodes.get(str(edge.get("target")))
    source_path = first_node_path(source)
    target_path = first_node_path(target)

    if relation in {
        "HAS_AUDIT",
        "HAS_PROFILE",
        "MANIFESTS_REPORT",
        "SPECIFIED_BY",
        "SUPPORTED_BY",
        "SUPPORTED_BY_ENDPOINT_AUDIT",
        "USES_SCHEMA",
    }:
        return target_path or source_path
    if relation in {
        "CONFIGURES_METHOD",
        "GOVERNED_BY",
        "RECORDED_IN",
        "REGISTERED_IN",
    }:
        return target_path or source_path or RELATION_FALLBACK_EVIDENCE.get(relation)
    if relation in {
        "DOCUMENTS_GRAPH",
        "AUDITS_GRAPH",
        "EVALUATES_METHOD",
        "EVALUATES_METHOD_CONFIG",
        "EVALUATES_MODEL",
        "EVIDENCES",
        "NOTES",
        "QUEUES_BASELINE_METHOD",
        "QUEUES_DATASET",
        "QUEUES_DIAGNOSTIC_METHOD",
        "QUEUES_METHOD",
        "QUEUES_METHOD_CONFIG",
        "QUEUES_MODEL",
        "REPORTS_METRIC",
        "REVIEWS",
        "SUMMARIZES_CHANGES_TO",
        "SUMMARIZES_CONFIG",
        "SUMMARIZES_CONTROL",
        "SUMMARIZES_DATASET",
        "SUMMARIZES_ENDPOINT_RESULT",
        "SUPPORTS_REPORT",
        "USES_MODULE",
        "USES_REFERENCE",
    }:
        return source_path or target_path or RELATION_FALLBACK_EVIDENCE.get(relation)
    return source_path or target_path or RELATION_FALLBACK_EVIDENCE.get(relation)


def edge_confidence(edge: dict, inferred_path_added: bool) -> tuple[float, str, str]:
    """Calibrate KG edge confidence from provenance granularity.

    This confidence is a traceability score, not empirical scientific certainty.
    Direct fact selectors are strongest; path-only and builder-inferred relations
    are intentionally below 1.0 so downstream paper tooling can distinguish them.
    """

    explicit = edge.get("confidence")
    if isinstance(explicit, bool):
        explicit = None
    if isinstance(explicit, (int, float)):
        return (
            float(explicit),
            "explicit confidence supplied by KG builder call site",
            "explicit",
        )
    if (
        edge.get("evidence_kind") == "artifact_root_selector"
        and str(edge.get("evidence_path", "")).strip()
    ):
        if str(edge.get("artifact_path", "")).strip():
            return (
                0.97,
                "artifact-root selector is paired with a resolved source artifact path",
                "artifact_root_resolved_selector",
            )
        if inferred_path_added:
            return (
                0.94,
                "artifact-root selector uses an artifact path inferred from adjacent node metadata",
                "artifact_root_inferred_selector",
            )
        return (
            0.96,
            "artifact-root selector and artifact path are present",
            "artifact_root_selector",
        )
    if (
        str(edge.get("evidence", "")).strip()
        and str(edge.get("evidence_path", "")).strip()
    ):
        return (
            1.0,
            "fact-level evidence selector and artifact path are present",
            "fact_selector",
        )
    if (
        str(edge.get("artifact_path", "")).strip()
        and str(edge.get("evidence_path", "")).strip()
    ):
        return (
            0.97,
            "artifact path was resolved through a source artifact list",
            "resolved_artifact_path",
        )
    if str(edge.get("evidence_path", "")).strip() and not inferred_path_added:
        return (
            0.94,
            "explicit artifact path is present without a fact-level selector",
            "path_level_explicit",
        )
    if str(edge.get("evidence_path", "")).strip() and inferred_path_added:
        return (
            0.90,
            "artifact path was inferred from adjacent node path metadata",
            "path_level_inferred",
        )
    return (
        0.75,
        "builder inference without artifact-level evidence path",
        "builder_inferred",
    )


def enrich_edge_traceability(edges: list[dict], nodes: dict[str, dict]) -> list[dict]:
    enriched = []
    for edge in edges:
        edge = dict(edge)
        inferred_path = infer_edge_evidence_path(edge, nodes)
        inferred_path_added = False
        if not edge.get("evidence_path") and inferred_path:
            edge["evidence_path"] = inferred_path
            inferred_path_added = True
        if edge.get("evidence_path") and not str(edge.get("evidence", "")).strip():
            edge["evidence"] = artifact_root_selector(edge["evidence_path"])
            edge.setdefault("evidence_kind", "artifact_root_selector")
        confidence, reason, granularity = edge_confidence(edge, inferred_path_added)
        edge["confidence"] = confidence
        edge.setdefault("confidence_reason", reason)
        edge.setdefault("confidence_model", CONFIDENCE_MODEL_VERSION)
        edge.setdefault("provenance_granularity", granularity)
        enriched.append(edge)
    return enriched


def enrich_node_observations(nodes: dict[str, dict], edges: list[dict]) -> None:
    incoming: dict[str, set[str]] = {}
    outgoing: dict[str, set[str]] = {}
    incoming_counts: dict[str, int] = {}
    outgoing_counts: dict[str, int] = {}
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        relation = str(edge.get("relation"))
        outgoing.setdefault(source, set()).add(relation)
        incoming.setdefault(target, set()).add(relation)
        outgoing_counts[source] = outgoing_counts.get(source, 0) + 1
        incoming_counts[target] = incoming_counts.get(target, 0) + 1

    for node_id, node in nodes.items():
        evidence_path = first_node_path(node) or "adjacent-edge provenance"
        outgoing_relations = (
            ", ".join(sorted(outgoing.get(node_id, set()))[:6]) or "none"
        )
        incoming_relations = (
            ", ".join(sorted(incoming.get(node_id, set()))[:6]) or "none"
        )
        observation = (
            f"{TOPOLOGY_OBSERVATION_PREFIX} {node_id} has "
            f"{outgoing_counts.get(node_id, 0)} outgoing and "
            f"{incoming_counts.get(node_id, 0)} incoming edge(s); "
            f"outgoing relations [{outgoing_relations}], incoming relations "
            f"[{incoming_relations}], primary evidence path {evidence_path}."
        )
        observations = list(node.get("observations", []) or [])
        if observation not in observations:
            observations.append(observation)
        node["observations"] = observations


def current_commit_node() -> tuple[str, dict] | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    sha = result.stdout.strip()
    if not sha:
        return None
    return f"commit:{sha}", {"sha": sha}


def add_standard_metric_nodes(nodes: dict[str, dict]) -> None:
    metrics = {
        "coverage": "Fraction of test labels inside the prediction interval.",
        "coverage_error_abs": "Absolute deviation from the nominal target coverage.",
        "coverage_gap": "Maximum group coverage spread for the configured diagnostic group.",
        "mean_width": "Average prediction interval width on the test split.",
        "median_width": "Median prediction interval width on the test split.",
        "width_gap": "Maximum group interval-width spread for the configured diagnostic group.",
        "interval_score": "Interval score combining width and miss penalties.",
        "lower_miss_rate": "Fraction of test labels below the lower interval bound.",
        "upper_miss_rate": "Fraction of test labels above the upper interval bound.",
        "failure_count": "Count of failed atomic experiment rows.",
        "controlled_skip_count": "Count of expected controlled skipped atomic experiment rows.",
        "endpoint_crossings": "Count of reconstructed intervals with lower endpoint above upper endpoint.",
        "endpoint_nonfinite": "Count of reconstructed lower or upper endpoints that are not finite.",
        "endpoint_floor_warning_excursions": "Count of reconstructed endpoints crossing configured floor or warning bounds.",
        "endpoint_observed_support_excursions": "Count of reconstructed endpoints or widths outside observed target support diagnostics.",
        "endpoint_max_width": "Maximum reconstructed prediction interval width in raw target units.",
    }
    for metric_id, summary in metrics.items():
        add_node(
            nodes,
            f"metric:{metric_id}",
            "metric",
            name=metric_id,
            summary=summary,
        )


def endpoint_result_node_id(report_name: str, method_id: str) -> str:
    return f"endpoint_result:{report_name}:{method_id}"


def endpoint_state_node_id(report_name: str, method_id: str) -> str:
    return f"endpoint_state:{report_name}:{method_id}"


def endpoint_caveat_node_id(report_name: str, method_id: str) -> str:
    return f"endpoint_caveat:{report_name}:{method_id}"


def dataset_catalog_decision_id(dataset_id: str, status: str) -> str:
    return f"decision:dataset_candidate:{dataset_id}:{status}"


def should_emit_dataset_catalog_decision(status: str | None) -> bool:
    if not status:
        return False
    return status == "queued_manual_audit" or "not_runner_queued" in status


def slug_fragment(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unnamed"


def manuscript_claim_node_id(claim_id: object) -> str:
    text = str(claim_id or "").strip()
    if text.startswith("manuscript_claim:"):
        return text
    return f"manuscript_claim:{slug_fragment(text)}"


def claim_requirement_node_id(claim_id: object, requirement_id: object) -> str:
    return (
        f"claim_requirement:{slug_fragment(claim_id)}:"
        f"{slug_fragment(requirement_id)}"
    )


def manuscript_claim_json_selector(
    claim_id: object,
    field: str | None = None,
    value: object | None = None,
) -> str:
    base = f"$.claims[?(@.claim_id == {json.dumps(str(claim_id), sort_keys=True)})]"
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def claim_requirement_json_selector(
    claim_id: object,
    requirement_id: object,
    field: str | None = None,
    value: object | None = None,
) -> str:
    base = (
        f"{manuscript_claim_json_selector(claim_id)}.requirements"
        f"[?(@.requirement_id == {json.dumps(str(requirement_id), sort_keys=True)})]"
    )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def paper_gate_json_selector(
    gate_id: object,
    field: str | None = None,
    value: object | None = None,
) -> str:
    base = (
        f"$.blocked_gates[?(@.gate_id == {json.dumps(str(gate_id), sort_keys=True)})]"
    )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def paper_gate_closure_json_selector(
    gate_id: object,
    field: str | None = None,
    value: object | None = None,
) -> str:
    base = (
        f"$.gate_rows[?(@.gate_id == {json.dumps(str(gate_id), sort_keys=True)})]"
    )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def paper_gate_execution_action_json_selector(
    action_id: object,
    field: str | None = None,
    value: object | None = None,
) -> str:
    base = (
        "$.action_rows"
        f"[?(@.action_id == {json.dumps(str(action_id), sort_keys=True)})]"
    )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def paper_gate_protocol_design_json_selector(
    action_id: object,
    field: str | None = None,
    value: object | None = None,
) -> str:
    base = (
        "$.protocol_design_rows"
        f"[?(@.action_id == {json.dumps(str(action_id), sort_keys=True)})]"
    )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def fairness_sampling_weight_policy_json_selector(
    bundle_id: object | None = None,
    field: str | None = None,
    value: object | None = None,
) -> str:
    if bundle_id is None:
        base = "$"
    else:
        base = (
            "$.bundle_policy_rows"
            f"[?(@.bundle_id == {json.dumps(str(bundle_id), sort_keys=True)})]"
        )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def fairness_group_diagnostic_json_selector(
    bundle_id: object | None = None,
    field: str | None = None,
    value: object | None = None,
) -> str:
    if bundle_id is None:
        base = "$"
    else:
        base = (
            "$.rows"
            f"[?(@.bundle_id == {json.dumps(str(bundle_id), sort_keys=True)})]"
        )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def fairness_group_multiplicity_scope_json_selector(
    bundle_id: object | None = None,
    field: str | None = None,
    value: object | None = None,
) -> str:
    if bundle_id is None:
        base = "$"
    else:
        base = (
            "$.rows"
            f"[?(@.bundle_id == {json.dumps(str(bundle_id), sort_keys=True)})]"
        )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


def goal_completion_requirement_json_selector(
    requirement_id: object,
    field: str | None = None,
    value: object | None = None,
) -> str:
    base = (
        "$.requirement_rows"
        f"[?(@.requirement_id == {json.dumps(str(requirement_id), sort_keys=True)})]"
    )
    if field is None:
        return base
    if value is None:
        return f"{base}.{field}"
    return f"{base}.{field}[?(@ == {json.dumps(str(value), sort_keys=True)})]"


ENDPOINT_COUNT_ALIASES = {
    "intervals": ("intervals", "endpoints", "endpoint_count"),
    "crossings": ("crossings", "interval_crossing", "interval_crossing_count"),
    "nonfinite_lower": ("nonfinite_lower",),
    "nonfinite_upper": ("nonfinite_upper",),
    "nonfinite_endpoint": ("nonfinite_endpoint", "nonfinite_endpoint_count"),
    "lower_below_floor": (
        "lower_below_floor",
        "lower_below_zero",
        "lower_below_zero_count",
    ),
    "upper_above_warning": (
        "upper_above_warning",
        "upper_above_100_count",
        "upper_above_20_count",
    ),
    "width_above_twice_observed_range": ("width_above_twice_observed_range",),
    "inverse_saturation_lower": (
        "inverse_saturation_lower",
        "lower_inverse_saturation",
        "inverse_lower_saturation_count",
    ),
    "inverse_saturation_upper": (
        "inverse_saturation_upper",
        "upper_inverse_saturation",
        "inverse_upper_saturation_count",
    ),
    "lower_below_observed_min": (
        "lower_below_observed_min",
        "lower_below_observed_min_count",
    ),
    "upper_above_observed_max": (
        "upper_above_observed_max",
        "upper_above_observed_max_count",
    ),
    "width_above_observed_range": ("width_above_observed_range",),
}


def endpoint_count(summary: dict, key: str) -> int:
    for candidate in ENDPOINT_COUNT_ALIASES.get(key, (key,)):
        value = summary.get(candidate)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def endpoint_float(summary: dict, key: str) -> float | None:
    value = summary.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def manifest_int_field(manifest_text: str, field_name: str) -> int | None:
    pattern = rf"^- {re.escape(field_name)}:\s*([0-9][0-9,]*)"
    match = re.search(pattern, manifest_text, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def collect_dataset_ids(payload: object) -> set[str]:
    dataset_ids: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "dataset_id" and isinstance(value, str):
                dataset_ids.add(value)
            elif key == "dataset_ids" and isinstance(value, list):
                dataset_ids.update(str(item) for item in value if item)
            elif key == "dataset_counts" and isinstance(value, dict):
                dataset_ids.update(str(item) for item in value)
            else:
                dataset_ids.update(collect_dataset_ids(value))
    elif isinstance(payload, list):
        for item in payload:
            dataset_ids.update(collect_dataset_ids(item))
    return dataset_ids


def collect_report_sidecars(report_dir: Path) -> dict[str, Path]:
    sidecars = {
        "pre_run_profile": report_dir / "pre_run_profile.json",
        "split_profile": report_dir / "split_profile.json",
        "endpoint_audit": report_dir / "endpoint_audit.json",
        "endpoint_audit_core_methods": report_dir / "endpoint_audit_core_methods.json",
        "feature_leakage_audit": report_dir / "feature_leakage_audit.json",
        "sensitivity_comparison": report_dir / "sensitivity_comparison.json",
        "runtime_cap_audit": report_dir / "runtime_cap_audit.json",
        "experiment_notes": report_dir / "experiment_notes.md",
        "post_run_execution_plan": report_dir / "post_run_execution_plan.md",
    }
    discovered = {
        sidecar_name: sidecar_path
        for sidecar_name, sidecar_path in sidecars.items()
        if sidecar_path.exists()
    }
    for path in sorted(report_dir.glob("endpoint_audit__*.json")):
        discovered[path.stem] = path
    for path in sorted(report_dir.glob("feature_leakage_audit_*")):
        if path.name in {"feature_leakage_audit.json", "feature_leakage_audit.md"}:
            continue
        if path.suffix not in {".json", ".md"}:
            continue
        discovered[path.stem] = path
    return discovered


def sidecar_attrs(sidecar_name: str, sidecar_path: Path, report_name: str) -> dict:
    return {
        "path": str(sidecar_path) if sidecar_path.suffix == ".md" else None,
        "json_path": str(sidecar_path) if sidecar_path.suffix == ".json" else None,
        "summary": (
            f"{sidecar_name.replace('_', ' ').title()} sidecar for " f"{report_name}."
        ),
    }


def endpoint_support_status(summary: dict) -> str:
    if endpoint_count(summary, "intervals") <= 0:
        return "schema_incomplete_endpoint_diagnostic"
    structural = (
        endpoint_count(summary, "crossings")
        + endpoint_count(summary, "nonfinite_lower")
        + endpoint_count(summary, "nonfinite_upper")
        + endpoint_count(summary, "nonfinite_endpoint")
    )
    boundary = (
        endpoint_count(summary, "lower_below_floor")
        + endpoint_count(summary, "upper_above_warning")
        + endpoint_count(summary, "width_above_twice_observed_range")
        + endpoint_count(summary, "inverse_saturation_lower")
        + endpoint_count(summary, "inverse_saturation_upper")
    )
    observed_support = (
        endpoint_count(summary, "lower_below_observed_min")
        + endpoint_count(summary, "upper_above_observed_max")
        + endpoint_count(summary, "width_above_observed_range")
    )
    if structural:
        return "structural_endpoint_failure"
    if boundary:
        return "boundary_pathology_diagnostic"
    if observed_support:
        return "observed_support_excursion_diagnostic"
    return "clean_endpoint_support_diagnostic"


def add_endpoint_result_nodes(
    nodes: dict[str, dict],
    edges: list[dict],
    *,
    report_name: str,
    report_id: str,
    sidecar_id: str,
    sidecar_path: Path,
    sidecar_payload: dict,
    dataset_ids: list[str],
    config_id: str | None,
    method_configs_by_label: dict[str, list[tuple[str, str]]],
) -> None:
    method_summary = sidecar_payload.get("method_summary")
    if not isinstance(method_summary, dict):
        return
    evidence_path = str(sidecar_path)
    for method_id, summary in sorted(method_summary.items()):
        if not isinstance(summary, dict):
            continue
        method_id = str(method_id)
        result_id = endpoint_result_node_id(report_name, method_id)
        status = endpoint_support_status(summary)
        structural_failures = (
            endpoint_count(summary, "crossings")
            + endpoint_count(summary, "nonfinite_lower")
            + endpoint_count(summary, "nonfinite_upper")
            + endpoint_count(summary, "nonfinite_endpoint")
        )
        floor_warning_excursions = endpoint_count(
            summary, "lower_below_floor"
        ) + endpoint_count(summary, "upper_above_warning")
        observed_support_excursions = (
            endpoint_count(summary, "lower_below_observed_min")
            + endpoint_count(summary, "upper_above_observed_max")
            + endpoint_count(summary, "width_above_observed_range")
        )
        extreme_width_excursions = endpoint_count(
            summary, "width_above_twice_observed_range"
        )
        inverse_saturation_events = endpoint_count(
            summary, "inverse_saturation_lower"
        ) + endpoint_count(summary, "inverse_saturation_upper")
        runs = endpoint_count(summary, "runs")
        intervals = endpoint_count(summary, "intervals")
        schema_incomplete_events = int(intervals <= 0)
        summary_text = (
            f"Endpoint audit result for {report_name} method {method_id}: "
            f"{runs} runs, {intervals} intervals, status {status}."
        )
        add_node(
            nodes,
            result_id,
            "endpoint_result",
            method_id=method_id,
            report_name=report_name,
            json_path=evidence_path,
            runs=runs,
            intervals=intervals,
            support_status=status,
            crossings=endpoint_count(summary, "crossings"),
            nonfinite_lower=endpoint_count(summary, "nonfinite_lower"),
            nonfinite_upper=endpoint_count(summary, "nonfinite_upper"),
            nonfinite_endpoint=endpoint_count(summary, "nonfinite_endpoint"),
            lower_below_floor=endpoint_count(summary, "lower_below_floor"),
            lower_below_observed_min=endpoint_count(
                summary, "lower_below_observed_min"
            ),
            upper_above_observed_max=endpoint_count(
                summary, "upper_above_observed_max"
            ),
            upper_above_warning=endpoint_count(summary, "upper_above_warning"),
            width_above_observed_range=endpoint_count(
                summary, "width_above_observed_range"
            ),
            width_above_twice_observed_range=extreme_width_excursions,
            inverse_saturation_lower=endpoint_count(
                summary, "inverse_saturation_lower"
            ),
            inverse_saturation_upper=endpoint_count(
                summary, "inverse_saturation_upper"
            ),
            schema_incomplete_events=schema_incomplete_events,
            min_lower=endpoint_float(summary, "min_lower"),
            max_upper=endpoint_float(summary, "max_upper"),
            max_width=endpoint_float(summary, "max_width"),
            summary=summary_text,
            observations=[
                (
                    "Raw endpoint-support diagnostic only; this node does not "
                    "claim bounded-support validity or production suitability."
                )
            ],
        )
        edge_attrs = {
            "evidence_path": evidence_path,
            "evidence": f"method_summary.{method_id}",
        }
        add_edge(
            edges, sidecar_id, result_id, "SUMMARIZES_ENDPOINT_RESULT", **edge_attrs
        )
        add_edge(
            edges, result_id, sidecar_id, "SUPPORTED_BY_ENDPOINT_AUDIT", **edge_attrs
        )
        add_edge(edges, result_id, report_id, "SUPPORTS_REPORT", **edge_attrs)
        method_config = choose_method_config(
            method_configs_by_label, method_id, report_name
        )
        if method_config:
            variant_id, base_method_id = method_config
            add_edge(
                edges, result_id, variant_id, "EVALUATES_METHOD_CONFIG", **edge_attrs
            )
            add_edge(
                edges,
                result_id,
                method_node_id(base_method_id),
                "EVALUATES_METHOD",
                **edge_attrs,
            )
        else:
            add_edge(
                edges,
                result_id,
                method_node_id(method_id),
                "EVALUATES_METHOD",
                **edge_attrs,
            )
        for metric_id in (
            "endpoint_crossings",
            "endpoint_nonfinite",
            "endpoint_floor_warning_excursions",
            "endpoint_observed_support_excursions",
            "endpoint_max_width",
        ):
            add_edge(
                edges, result_id, f"metric:{metric_id}", "REPORTS_METRIC", **edge_attrs
            )
        for dataset_id in dataset_ids:
            add_edge(
                edges,
                result_id,
                f"dataset:{dataset_id}",
                "SUMMARIZES_DATASET",
                **edge_attrs,
            )
        if config_id:
            add_edge(edges, result_id, config_id, "SUMMARIZES_CONFIG", **edge_attrs)

        has_endpoint_caveat = bool(
            structural_failures
            or floor_warning_excursions
            or observed_support_excursions
            or extreme_width_excursions
            or inverse_saturation_events
            or schema_incomplete_events
        )
        state_id = endpoint_state_node_id(report_name, method_id)
        state_label = (
            "caveated_endpoint_state"
            if has_endpoint_caveat
            else "clean_no_caveat_endpoint_state"
        )
        add_node(
            nodes,
            state_id,
            "endpoint_state",
            method_id=method_id,
            report_name=report_name,
            json_path=evidence_path,
            support_status=status,
            endpoint_state=state_label,
            has_caveat=has_endpoint_caveat,
            structural_failures=structural_failures,
            floor_warning_excursions=floor_warning_excursions,
            observed_support_excursions=observed_support_excursions,
            extreme_width_excursions=extreme_width_excursions,
            inverse_saturation_events=inverse_saturation_events,
            schema_incomplete_events=schema_incomplete_events,
            summary=(
                f"Endpoint state for {report_name} method {method_id}: "
                f"{state_label}, support status {status}."
            ),
            observations=[
                (
                    "This node makes endpoint caveat state queryable; it is "
                    "traceability metadata, not bounded-support validity evidence."
                )
            ],
        )
        add_edge(edges, result_id, state_id, "HAS_ENDPOINT_STATE", **edge_attrs)
        add_edge(
            edges,
            state_id,
            sidecar_id,
            "SUPPORTED_BY_ENDPOINT_AUDIT",
            **edge_attrs,
        )

        if has_endpoint_caveat:
            caveat_id = endpoint_caveat_node_id(report_name, method_id)
            add_node(
                nodes,
                caveat_id,
                "endpoint_caveat",
                method_id=method_id,
                report_name=report_name,
                json_path=evidence_path,
                support_status=status,
                structural_failures=structural_failures,
                floor_warning_excursions=floor_warning_excursions,
                observed_support_excursions=observed_support_excursions,
                extreme_width_excursions=extreme_width_excursions,
                inverse_saturation_events=inverse_saturation_events,
                schema_incomplete_events=schema_incomplete_events,
                summary=(
                    f"Endpoint-support caveat for {report_name} method {method_id}: "
                    f"structural={structural_failures}, floor_or_warning="
                    f"{floor_warning_excursions}, observed_support="
                    f"{observed_support_excursions}, extreme_width="
                    f"{extreme_width_excursions}, inverse_saturation="
                    f"{inverse_saturation_events}, schema_incomplete="
                    f"{schema_incomplete_events}."
                ),
                observations=[
                    (
                        "Interpret as a raw endpoint diagnostic and failure-mode "
                        "indicator, not as clinical, legal, fairness, or bounded-support evidence."
                    )
                ],
            )
            add_edge(edges, result_id, caveat_id, "HAS_CAVEAT", **edge_attrs)
            add_edge(
                edges,
                caveat_id,
                sidecar_id,
                "SUPPORTED_BY_ENDPOINT_AUDIT",
                **edge_attrs,
            )


def multiplicity_evidence(edge: dict) -> dict[str, object]:
    return {
        key: edge[key]
        for key in (
            "evidence_path",
            "evidence",
            "artifact_path",
            "provenance_mode",
            "source_file",
        )
        if edge.get(key)
    }


def merge_edge_metadata(base: dict, edge: dict) -> None:
    for key in (
        "evidence_path",
        "evidence",
        "artifact_path",
        "provenance_mode",
        "source_file",
    ):
        if not base.get(key) and edge.get(key):
            base[key] = edge[key]


def dedupe_edges(edges: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for edge in edges:
        key = (edge["source"], edge["relation"], edge["target"])
        evidence = multiplicity_evidence(edge)
        if key not in merged:
            merged[key] = dict(edge)
            merged[key]["multiplicity"] = 1
            merged[key]["multiplicity_evidence_count"] = 1 if evidence else 0
            merged[key]["multiplicity_evidence_samples"] = (
                [evidence] if evidence else []
            )
            continue
        merged[key]["multiplicity"] += 1
        merge_edge_metadata(merged[key], edge)
        if evidence:
            samples = merged[key].setdefault("multiplicity_evidence_samples", [])
            if (
                evidence not in samples
                and len(samples) < MAX_MULTIPLICITY_EVIDENCE_SAMPLES
            ):
                samples.append(evidence)
            merged[key]["multiplicity_evidence_count"] = (
                int(merged[key].get("multiplicity_evidence_count") or 0) + 1
            )
    return list(merged.values())


def iter_config_paths(pattern: str) -> Iterable[Path]:
    return (Path(path) for path in sorted(glob.glob(pattern)))


def method_node_id(method_id: str) -> str:
    aliases = {
        "ivapd_threshold_grid": "ivapd_regression",
    }
    return f"method:{aliases.get(method_id, method_id)}"


def cp_method_settings(config: dict, cp_method: str) -> tuple[str, dict]:
    method_configs = config.get("cp_method_configs", {})
    entry = None
    if isinstance(method_configs, dict):
        entry = method_configs.get(str(cp_method))
    elif isinstance(method_configs, list):
        for candidate in method_configs:
            if str(candidate.get("label", candidate.get("method_id"))) == str(
                cp_method
            ):
                entry = candidate
                break
    if not entry:
        return str(cp_method), {}
    return str(entry.get("method_id", cp_method)), dict(entry.get("params", {}))


def choose_method_config(
    method_configs_by_label: dict[str, list[tuple[str, str]]],
    label: str,
    report_name: str,
) -> tuple[str, str] | None:
    candidates = method_configs_by_label.get(label, [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    matching = [
        (variant_id, method_id)
        for variant_id, method_id in candidates
        if report_name in variant_id
    ]
    if len(matching) == 1:
        return matching[0]
    return None


def add_report_directory(
    nodes: dict[str, dict],
    edges: list[dict],
    *,
    report_dir: Path,
    report_payload: dict | None,
    config_ids_by_report_name: dict[str, str],
    method_configs_by_label: dict[str, list[tuple[str, str]]],
) -> None:
    report_name = report_dir.name
    report_id = f"report:{report_name}"
    report_json = report_dir / "pilot_summary.json"
    report_md = report_dir / "pilot_summary.md"
    source_review_json = report_dir / "source_review_report.json"
    source_review_md = report_dir / "source_review_report.md"
    manifest_md = report_dir / "publication_readiness_manifest.md"
    sidecars = collect_report_sidecars(report_dir)
    source_review_payload = None
    if source_review_json.exists():
        try:
            source_review_payload = json.loads(
                source_review_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            source_review_payload = {}
    if (
        report_payload is None
        and source_review_payload is None
        and not sidecars
        and not manifest_md.exists()
    ):
        return

    report_dataset_ids: list[str] = []
    rows = []
    rows_count = None
    if report_payload is not None:
        metadata = report_payload.get("metadata", {})
        report_dataset_ids = [
            str(dataset_id) for dataset_id in metadata.get("dataset_counts", {})
        ]
        rows = report_payload.get("rows", [])
        rows_count = metadata.get("unique_run_rows")
    else:
        sidecar_dataset_ids: set[str] = set()
        for sidecar_path in sidecars.values():
            if sidecar_path.suffix != ".json":
                continue
            try:
                sidecar_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            sidecar_dataset_ids.update(collect_dataset_ids(sidecar_payload))
        report_dataset_ids = sorted(sidecar_dataset_ids)
        if source_review_payload is not None:
            report_dataset_ids = sorted(
                set(report_dataset_ids)
                | collect_dataset_ids(source_review_payload)
            )

    config_id = config_ids_by_report_name.get(report_name)
    config_payload = None
    config_path = Path("experiments/regression/configs") / f"{report_name}.yaml"
    if config_path.exists():
        config_payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    report_path = report_md if report_md.exists() else source_review_md
    if not report_path.exists():
        report_path = report_dir / "experiment_notes.md"
    if not report_path.exists():
        report_path = None
    report_status = "partial_run"
    report_summary = (
        f"Partial regression report directory {report_name}; "
        "sidecar evidence exists before pilot_summary generation."
    )
    report_observations = [
        (
            "Partial report nodes are progress visibility evidence only; "
            "they do not close methodology backlog actions without final sidecars."
        )
    ]
    if source_review_payload is not None:
        report_status = str(
            source_review_payload.get("status") or "source_review_report"
        )
        report_summary = (
            f"Source-review report directory {report_name}; metadata-only "
            "evidence with modeling blocked unless explicitly approved."
        )
        report_observations = [
            (
                "Source-review reports support source-discovery accounting only; "
                "they are not model-performance or final-claim evidence."
            )
        ]
    if report_payload is not None:
        report_status = "completed_report"
        report_summary = f"Regression report directory {report_name}."
        report_observations = []
    add_node(
        nodes,
        report_id,
        "report",
        path=str(report_path) if report_path else None,
        json_path=(
            str(report_json)
            if report_json.exists()
            else str(source_review_json) if source_review_json.exists() else None
        ),
        rows=rows_count,
        report_status=report_status,
        summary=report_summary,
        observations=report_observations,
    )
    if config_id:
        add_edge(
            edges,
            report_id,
            config_id,
            "SUMMARIZES_CONFIG",
            evidence_path=str(config_path) if config_path.exists() else None,
            evidence="experiment_id" if config_path.exists() else None,
        )
        if not report_dataset_ids:
            if config_payload is not None:
                datasets = config_payload.get("datasets", [])
                if isinstance(datasets, list):
                    report_dataset_ids = [str(dataset_id) for dataset_id in datasets]
    for dataset_id in report_dataset_ids:
        if report_json.exists() and report_payload is not None:
            dataset_edge_attrs = {
                "evidence_path": str(report_json),
                "evidence": json_array_selector("dataset_id", dataset_id, root="rows"),
            }
        elif config_path.exists():
            dataset_edge_attrs = {
                "evidence_path": str(config_path),
                "evidence": yaml_selector("datasets", dataset_id),
            }
        elif source_review_json.exists():
            dataset_edge_attrs = {
                "evidence_path": str(source_review_json),
                "evidence": dataset_payload_selector(source_review_payload, dataset_id),
            }
        else:
            dataset_edge_attrs = {}
        add_edge(
            edges,
            report_id,
            f"dataset:{dataset_id}",
            "SUMMARIZES_DATASET",
            **dataset_edge_attrs,
        )
    if source_review_payload is not None:
        source_review_dataset_id = source_review_payload.get("dataset_id")
        if source_review_dataset_id:
            add_edge(
                edges,
                report_id,
                f"audit:{source_review_dataset_id}",
                "DERIVED_FROM",
                evidence_path=str(source_review_json),
                evidence="dataset_id",
            )

    manifest_id = None
    if manifest_md.exists():
        manifest_id = f"manifest:{report_name}:publication_readiness"
        manifest_text = manifest_md.read_text(encoding="utf-8")
        manifest_status = None
        status_match = re.search(r"^Status:\s*(.+)$", manifest_text, re.MULTILINE)
        if status_match:
            manifest_status = status_match.group(1).strip()
        ledger_info = (
            report_payload.get("ledger") if isinstance(report_payload, dict) else None
        )
        metadata = (
            report_payload.get("metadata", {})
            if isinstance(report_payload, dict)
            else {}
        )
        completed_count = None
        controlled_skip_count = None
        failure_count = None
        status_counts = (
            metadata.get("status_counts") if isinstance(metadata, dict) else None
        )
        if isinstance(status_counts, dict):
            completed_count = status_counts.get("completed")
            controlled_skip_count = status_counts.get("skipped_method")
            failure_count = status_counts.get("failed", 0)
        target = None
        target_transform = None
        diagnostic_group = None
        planned_atomic_rows = (
            metadata.get("ledger_rows") if isinstance(metadata, dict) else None
        )
        target_match = re.search(
            r"^- Target:\s*`?([^`\n.]+)`?", manifest_text, re.MULTILINE
        )
        if target_match:
            target = target_match.group(1).strip()
        group_match = re.search(
            r"^- Diagnostic group:\s*`?([^`\n.]+)`?",
            manifest_text,
            re.MULTILINE,
        )
        if group_match:
            diagnostic_group = group_match.group(1).strip()
        if isinstance(config_payload, dict):
            target_transform = config_payload.get("target_transform")
            datasets_cfg = config_payload.get("dataset_configs")
            if isinstance(datasets_cfg, dict) and report_dataset_ids:
                first_dataset_cfg = datasets_cfg.get(report_dataset_ids[0]) or {}
                if isinstance(first_dataset_cfg, dict):
                    target = target or first_dataset_cfg.get("target")
                    diagnostic_group = diagnostic_group or first_dataset_cfg.get(
                        "group"
                    )
            planned_datasets = config_payload.get("datasets")
            model_configs = config_payload.get("models")
            cp_methods = config_payload.get("cp_methods")
            seeds = config_payload.get("random_seeds")
            if planned_atomic_rows is None and (
                isinstance(planned_datasets, list)
                and isinstance(model_configs, list)
                and isinstance(cp_methods, list)
                and isinstance(seeds, list)
            ):
                planned_atomic_rows = manifest_int_field(
                    manifest_text,
                    "Planned atomic rows",
                ) or (
                    len(planned_datasets)
                    * len(model_configs)
                    * len(cp_methods)
                    * len(seeds)
                )
        add_node(
            nodes,
            manifest_id,
            "manifest",
            path=str(manifest_md),
            ledger_path=(
                ledger_info.get("path")
                if isinstance(ledger_info, dict)
                else str(ledger_info) if isinstance(ledger_info, str) else None
            ),
            report_name=report_name,
            manifest_status=manifest_status,
            target=target,
            target_transform=target_transform,
            diagnostic_group=diagnostic_group,
            planned_atomic_rows=planned_atomic_rows,
            completed_rows=completed_count,
            controlled_skip_count=controlled_skip_count,
            failure_count=failure_count,
            summary=(
                "Publication-readiness manifest controlling manuscript claim "
                f"eligibility for regression report `{report_name}`."
            ),
        )
        add_edge(
            edges,
            manifest_id,
            report_id,
            "MANIFESTS_REPORT",
            evidence_path=str(manifest_md),
            evidence=markdown_section_selector("Identity"),
        )
        add_edge(
            edges,
            manifest_id,
            "catalog:manuscript_evidence_manifest_schema",
            "USES_SCHEMA",
            evidence_path=str(manifest_md),
            evidence=markdown_section_selector("Schema"),
        )
        if config_id:
            add_edge(
                edges,
                manifest_id,
                config_id,
                "SUMMARIZES_CONFIG",
                evidence_path=str(manifest_md),
                evidence=markdown_section_selector("Identity"),
            )
        for dataset_id in report_dataset_ids:
            add_edge(
                edges,
                manifest_id,
                f"dataset:{dataset_id}",
                "SUMMARIZES_DATASET",
                evidence_path=str(manifest_md),
                evidence=markdown_section_selector("Identity"),
            )
        for metric_id in (
            "coverage",
            "coverage_error_abs",
            "coverage_gap",
            "mean_width",
            "median_width",
            "interval_score",
            "failure_count",
            "controlled_skip_count",
        ):
            add_edge(
                edges,
                manifest_id,
                f"metric:{metric_id}",
                "REPORTS_METRIC",
                evidence_path=str(manifest_md),
                evidence=markdown_section_selector("Design"),
            )

    for row in rows:
        model_id = row.get("model_id")
        if model_id:
            add_node(nodes, f"model:{model_id}", "model", name=str(model_id))
            add_edge(
                edges,
                report_id,
                f"model:{model_id}",
                "EVALUATES_MODEL",
                evidence_path=str(report_json),
                evidence=json_array_selector("model_id", model_id, root="rows"),
            )
        cp_method = row.get("cp_method")
        if cp_method:
            cp_method_label = str(cp_method)
            method_config = choose_method_config(
                method_configs_by_label,
                cp_method_label,
                report_name,
            )
            method_edge_attrs = {
                "evidence_path": str(report_json),
                "evidence": json_array_selector(
                    "cp_method", cp_method_label, root="rows"
                ),
            }
            if method_config:
                variant_id, base_method_id = method_config
                add_edge(
                    edges,
                    report_id,
                    variant_id,
                    "EVALUATES_METHOD_CONFIG",
                    **method_edge_attrs,
                )
                add_edge(
                    edges,
                    report_id,
                    method_node_id(base_method_id),
                    "EVALUATES_METHOD",
                    **method_edge_attrs,
                )
            else:
                add_edge(
                    edges,
                    report_id,
                    method_node_id(cp_method_label),
                    "EVALUATES_METHOD",
                    **method_edge_attrs,
                )
    if report_payload is not None:
        for metric_id in (
            "coverage",
            "coverage_error_abs",
            "coverage_gap",
            "mean_width",
            "width_gap",
            "interval_score",
            "lower_miss_rate",
            "upper_miss_rate",
        ):
            add_edge(
                edges,
                report_id,
                f"metric:{metric_id}",
                "REPORTS_METRIC",
                evidence_path=str(report_json),
                evidence=f"rows[*].{metric_id}_mean",
            )

    for sidecar_name, sidecar_path in sidecars.items():
        sidecar_id = f"{report_id}:{sidecar_name}"
        add_node(
            nodes,
            sidecar_id,
            "report",
            **sidecar_attrs(sidecar_name, sidecar_path, report_name),
        )
        add_edge(
            edges,
            sidecar_id,
            report_id,
            "SUPPORTS_REPORT",
        )
        if manifest_id:
            add_edge(
                edges,
                manifest_id,
                sidecar_id,
                "SUPPORTED_BY",
                evidence_path=str(manifest_md),
                evidence=markdown_section_selector("Data Evidence"),
            )
        for dataset_id in report_dataset_ids:
            add_edge(
                edges,
                sidecar_id,
                f"dataset:{dataset_id}",
                "SUMMARIZES_DATASET",
            )
        if sidecar_path.suffix != ".json":
            if config_id:
                add_edge(edges, sidecar_id, config_id, "SUMMARIZES_CONFIG")
            continue
        try:
            sidecar_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            sidecar_payload = {}
        dataset_ids = sorted(collect_dataset_ids(sidecar_payload))
        for dataset_id_value in dataset_ids:
            add_edge(
                edges,
                sidecar_id,
                f"dataset:{dataset_id_value}",
                "SUMMARIZES_DATASET",
                evidence_path=str(sidecar_path),
                evidence=dataset_payload_selector(sidecar_payload, dataset_id_value),
            )
        sidecar_config_id = None
        config_path = sidecar_payload.get("config_path") or sidecar_payload.get(
            "config"
        )
        if config_path:
            config_sidecar_path = Path(str(config_path))
            if config_sidecar_path.exists():
                config_stem = config_sidecar_path.stem
                config = yaml.safe_load(config_sidecar_path.read_text(encoding="utf-8"))
                sidecar_config_id = f"config:{config.get('experiment_id', config_stem)}"
                add_edge(
                    edges,
                    sidecar_id,
                    sidecar_config_id,
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(sidecar_path),
                    evidence="config_path",
                )
        if not sidecar_config_id:
            sidecar_config_id = config_id
            if sidecar_config_id:
                add_edge(
                    edges,
                    sidecar_id,
                    sidecar_config_id,
                    "SUMMARIZES_CONFIG",
                )
        if sidecar_name in {"endpoint_audit", "endpoint_audit_core_methods"}:
            add_endpoint_result_nodes(
                nodes,
                edges,
                report_name=report_name,
                report_id=report_id,
                sidecar_id=sidecar_id,
                sidecar_path=sidecar_path,
                sidecar_payload=sidecar_payload,
                dataset_ids=sorted(set([*report_dataset_ids, *dataset_ids])),
                config_id=sidecar_config_id,
                method_configs_by_label=method_configs_by_label,
            )


def add_manuscript_claim_register(
    nodes: dict[str, dict],
    edges: list[dict],
    *,
    path: Path,
) -> None:
    if not path.exists():
        return
    try:
        register = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    catalog_id = "catalog:manuscript_claim_register"
    claims = register.get("claims", [])
    if not isinstance(claims, list):
        return
    path_index = build_node_path_index(nodes)
    for claim in claims:
        if not isinstance(claim, dict) or not claim.get("claim_id"):
            continue
        claim_key = str(claim["claim_id"])
        claim_id = manuscript_claim_node_id(claim_key)
        claim_text = str(claim.get("claim_text") or claim_key)
        status = claim.get("status")
        add_node(
            nodes,
            claim_id,
            "manuscript_claim",
            claim_id=claim_key,
            status=status,
            claim_type=claim.get("claim_type"),
            claim_text=claim_text,
            scope=claim.get("scope"),
            not_claiming=claim.get("not_claiming"),
            summary=(
                f"Manuscript claim `{claim_key}` with status {status}: " f"{claim_text}"
            ),
        )
        add_edge(
            edges,
            claim_id,
            catalog_id,
            "RECORDED_IN",
            evidence_path=str(path),
            evidence=manuscript_claim_json_selector(claim_key),
        )
        for node_id in claim.get("supporting_node_ids", []) or []:
            add_edge(
                edges,
                claim_id,
                str(node_id),
                "SUPPORTED_BY",
                evidence_path=str(path),
                evidence=manuscript_claim_json_selector(
                    claim_key, "supporting_node_ids", node_id
                ),
            )
        for node_id in claim.get("blocking_node_ids", []) or []:
            add_edge(
                edges,
                claim_id,
                str(node_id),
                "BLOCKED_BY",
                evidence_path=str(path),
                evidence=manuscript_claim_json_selector(
                    claim_key, "blocking_node_ids", node_id
                ),
            )
        for dataset_id in claim.get("dataset_ids", []) or []:
            add_edge(
                edges,
                claim_id,
                f"dataset:{dataset_id}",
                "CONCERNS_DATASET",
                evidence_path=str(path),
                evidence=manuscript_claim_json_selector(
                    claim_key, "dataset_ids", dataset_id
                ),
            )
        for method_id in claim.get("method_ids", []) or []:
            add_edge(
                edges,
                claim_id,
                method_node_id(str(method_id)),
                "CONCERNS_METHOD",
                evidence_path=str(path),
                evidence=manuscript_claim_json_selector(
                    claim_key, "method_ids", method_id
                ),
            )

        requirements = claim.get("requirements", [])
        if not isinstance(requirements, list):
            continue
        for requirement in requirements:
            if not isinstance(requirement, dict) or not requirement.get(
                "requirement_id"
            ):
                continue
            req_key = str(requirement["requirement_id"])
            req_id = claim_requirement_node_id(claim_key, req_key)
            add_node(
                nodes,
                req_id,
                "claim_requirement",
                claim_id=claim_key,
                requirement_id=req_key,
                status=requirement.get("status"),
                artifact_paths=requirement.get("artifact_paths"),
                summary=(
                    f"Requirement `{req_key}` for manuscript claim `{claim_key}` "
                    f"with status {requirement.get('status')}: "
                    f"{requirement.get('description') or ''}".strip()
                ),
                observations=requirement.get("observations") or [],
            )
            add_edge(
                edges,
                claim_id,
                req_id,
                "HAS_REQUIREMENT",
                evidence_path=str(path),
                evidence=claim_requirement_json_selector(claim_key, req_key),
            )
            add_edge(
                edges,
                req_id,
                catalog_id,
                "RECORDED_IN",
                evidence_path=str(path),
                evidence=claim_requirement_json_selector(claim_key, req_key),
            )
            for node_id in requirement.get("supporting_node_ids", []) or []:
                add_edge(
                    edges,
                    req_id,
                    str(node_id),
                    "SUPPORTED_BY",
                    evidence_path=str(path),
                    evidence=claim_requirement_json_selector(
                        claim_key, req_key, "supporting_node_ids", node_id
                    ),
                )
            for artifact_path in requirement.get("artifact_paths", []) or []:
                for node_id in artifact_support_node_ids(
                    nodes, path_index, artifact_path
                ):
                    add_edge(
                        edges,
                        req_id,
                        node_id,
                        "SUPPORTED_BY",
                        evidence_path=str(path),
                        evidence=claim_requirement_json_selector(
                            claim_key, req_key, "artifact_paths", artifact_path
                        ),
                        artifact_path=str(artifact_path),
                        provenance_mode="claim_requirement_artifact_path_resolved",
                    )
            for node_id in requirement.get("blocking_node_ids", []) or []:
                add_edge(
                    edges,
                    req_id,
                    str(node_id),
                    "BLOCKED_BY",
                    evidence_path=str(path),
                    evidence=claim_requirement_json_selector(
                        claim_key, req_key, "blocking_node_ids", node_id
                    ),
                )


def main() -> None:
    args = parse_args()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    add_node(
        nodes,
        "policy:data_policy_registry",
        "policy",
        path="experiments/regression/policies/data_policy_registry.md",
    )
    add_node(
        nodes, "catalog:dataset_candidates", "catalog", path=args.dataset_candidates
    )
    add_node(nodes, "catalog:method_registry", "catalog", path=args.method_registry)
    add_node(
        nodes,
        "catalog:regression_literature_notes",
        "catalog",
        path="experiments/regression/catalogs/literature_notes.md",
        summary="Regression conformal prediction literature notes and method-family decision log.",
    )
    add_node(nodes, "catalog:audit_index", "catalog", path=args.audit_index)
    add_node(nodes, "catalog:knowledge_graph", "catalog", path=args.out)
    add_node(
        nodes,
        "catalog:manuscript_claim_register",
        "catalog",
        path=args.manuscript_claim_register,
        summary="Machine-readable claim register connecting manuscript claims to supporting evidence and blocking caveats.",
    )
    add_node(
        nodes,
        "catalog:manuscript_claim_register_md",
        "catalog",
        path="experiments/regression/catalogs/manuscript_claim_register.md",
        summary="Human-readable rendering of the regression manuscript claim register.",
    )
    add_node(
        nodes,
        "catalog:manuscript_evidence_manifest_schema",
        "catalog",
        path="experiments/regression/catalogs/manuscript_evidence_manifest_schema.json",
        summary="Schema contract for publication-readiness manifests that bridge experiment artifacts to manuscript claims.",
    )
    add_node(
        nodes,
        "catalog:manuscript_bundle_index",
        "catalog",
        path="experiments/regression/catalogs/manuscript_bundle_index.json",
        summary="Machine-readable index of publication-readiness bundles and their manuscript extraction status.",
    )
    add_node(
        nodes,
        "catalog:manuscript_bundle_index_md",
        "catalog",
        path="experiments/regression/catalogs/manuscript_bundle_index.md",
        summary="Human-readable index of publication-readiness bundles and manuscript extraction blockers.",
    )
    add_node(
        nodes,
        "catalog:publication_readiness_protocol",
        "catalog",
        path="experiments/regression/PUBLICATION_READINESS_PROTOCOL.md",
        summary="Protocol defining evidence standards for promoting regression CP artifacts into manuscript claims.",
    )
    manuscript_catalogs = {
        "catalog:manuscript_workspace_readme": "experiments/regression/manuscript/README.md",
        "catalog:manuscript_dataset_table": "experiments/regression/manuscript/dataset_table.md",
        "catalog:manuscript_method_table": "experiments/regression/manuscript/method_table.md",
        "catalog:manuscript_main_results_table": "experiments/regression/manuscript/main_results_table.md",
        "catalog:manuscript_robustness_results_table": "experiments/regression/manuscript/robustness_results_table.md",
        "catalog:manuscript_negative_results_table": "experiments/regression/manuscript/negative_results_table.md",
        "catalog:manuscript_evidence_view": "experiments/regression/manuscript/evidence_view.md",
        "catalog:selection_multiplicity_protocol": "experiments/regression/manuscript/selection_multiplicity_protocol.md",
        "catalog:bounded_support_protocol": "experiments/regression/manuscript/bounded_support_protocol.md",
        "catalog:bounded_support_posthandling_validation": "experiments/regression/manuscript/bounded_support_posthandling_validation.md",
        "catalog:bounded_support_dataset_audit": "experiments/regression/manuscript/bounded_support_dataset_audit.md",
        "catalog:bounded_support_positive_validation_protocol": "experiments/regression/manuscript/bounded_support_positive_validation_protocol.md",
        "catalog:manuscript_paper_readiness_map": "experiments/regression/manuscript/paper_readiness_map.md",
        "catalog:manuscript_bundle_eligibility_matrix": "experiments/regression/manuscript/bundle_eligibility_matrix.md",
        "catalog:manuscript_figure_index": "experiments/regression/manuscript/figure_index.md",
        "catalog:manuscript_figure_specs_readme": "experiments/regression/manuscript/figures/README.md",
        "catalog:post_experiment_publication_program": "experiments/regression/manuscript/post_experiment_publication_program.md",
        "catalog:post_experiment_publication_activation_audit": "experiments/regression/manuscript/post_experiment_publication_activation_audit.md",
    }
    for node_id, path in manuscript_catalogs.items():
        attrs = {"path": path}
        if node_id == "catalog:manuscript_evidence_view":
            attrs["json_path"] = "experiments/regression/manuscript/evidence_view.json"
        elif node_id == "catalog:selection_multiplicity_protocol":
            attrs["json_path"] = (
                "experiments/regression/manuscript/selection_multiplicity_protocol.json"
            )
        elif node_id == "catalog:bounded_support_protocol":
            attrs["json_path"] = (
                "experiments/regression/manuscript/bounded_support_protocol.json"
            )
        elif node_id == "catalog:bounded_support_posthandling_validation":
            attrs["json_path"] = (
                "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
            )
        elif node_id == "catalog:bounded_support_dataset_audit":
            attrs["json_path"] = (
                "experiments/regression/manuscript/bounded_support_dataset_audit.json"
            )
        elif node_id == "catalog:bounded_support_positive_validation_protocol":
            attrs["json_path"] = (
                "experiments/regression/manuscript/"
                "bounded_support_positive_validation_protocol.json"
            )
        elif node_id == "catalog:manuscript_paper_readiness_map":
            attrs["json_path"] = (
                "experiments/regression/manuscript/paper_readiness_map.json"
            )
        elif node_id == "catalog:manuscript_bundle_eligibility_matrix":
            attrs["json_path"] = (
                "experiments/regression/manuscript/bundle_eligibility_matrix.json"
            )
        elif node_id == "catalog:post_experiment_publication_program":
            attrs["json_path"] = (
                "experiments/regression/manuscript/"
                "post_experiment_publication_program.json"
            )
        elif node_id == "catalog:post_experiment_publication_activation_audit":
            attrs["json_path"] = (
                "experiments/regression/manuscript/"
                "post_experiment_publication_activation_audit.json"
            )
        add_node(
            nodes,
            node_id,
            "catalog",
            **attrs,
            summary="Manuscript extraction scaffold controlled by the regression publication-readiness protocol.",
        )
    post_program_json = Path(
        "experiments/regression/manuscript/post_experiment_publication_program.json"
    )
    if post_program_json.exists():
        try:
            post_program = json.loads(post_program_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            post_program = {}
        post_program_catalog_id = "catalog:post_experiment_publication_program"
        for index, reviewer in enumerate(post_program.get("reviewer_perspectives") or []):
            if not isinstance(reviewer, dict) or not reviewer.get("reviewer_id"):
                continue
            reviewer_id = str(reviewer["reviewer_id"])
            node_id = f"publication_reviewer:{slug_fragment(reviewer_id)}"
            add_node(
                nodes,
                node_id,
                "reviewer_perspective",
                reviewer_id=reviewer_id,
                focus=reviewer.get("focus"),
                summary=(
                    f"Post-experiment publication reviewer perspective "
                    f"`{reviewer_id}`: {reviewer.get('focus') or ''}"
                ).strip(),
            )
            add_edge(
                edges,
                post_program_catalog_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_program_json),
                evidence=row_selector("reviewer_perspectives", index, "reviewer_id"),
            )
        for index, deliverable in enumerate(post_program.get("deliverables") or []):
            if not isinstance(deliverable, dict) or not deliverable.get("deliverable_id"):
                continue
            deliverable_id = str(deliverable["deliverable_id"])
            node_id = f"publication_deliverable:{slug_fragment(deliverable_id)}"
            add_node(
                nodes,
                node_id,
                "publication_deliverable",
                deliverable_id=deliverable_id,
                format=deliverable.get("format"),
                description=deliverable.get("description"),
                summary=(
                    f"Deferred publication deliverable `{deliverable_id}` "
                    f"with format {deliverable.get('format')}."
                ),
            )
            add_edge(
                edges,
                post_program_catalog_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_program_json),
                evidence=row_selector("deliverables", index, "deliverable_id"),
            )
        blueprint_paths = (
            ("main_article", "main_article_blueprint"),
            ("supplementary_document", "supplementary_document_blueprint"),
            ("publication_site", "publication_site_blueprint"),
        )
        for surface_id, key in blueprint_paths:
            blueprint = post_program.get(key) or {}
            section_key = "components" if key == "publication_site_blueprint" else "sections"
            for index, section in enumerate(blueprint.get(section_key) or []):
                section_id = str(section)
                node_id = (
                    f"publication_surface:{slug_fragment(surface_id)}:"
                    f"{slug_fragment(section_id)}"
                )
                add_node(
                    nodes,
                    node_id,
                    "publication_surface",
                    surface_id=surface_id,
                    section_id=section_id,
                    status=blueprint.get("status"),
                    summary=(
                        f"Deferred publication surface `{surface_id}` includes "
                        f"`{section_id}` with status {blueprint.get('status')}."
                    ),
                )
                add_edge(
                    edges,
                    post_program_catalog_id,
                    node_id,
                    "SUMMARIZES_CONTROL",
                    evidence_path=str(post_program_json),
                    evidence=f"$.{key}.{section_key}[{index}]",
                )
        completion_definition = post_program.get("experiment_completion_definition") or {}
        for index, check in enumerate(completion_definition.get("closure_checks") or []):
            check_id = str(check)
            node_id = (
                f"publication_activation_check:{index + 1:02d}:"
                f"{slug_fragment(check_id)}"
            )
            add_node(
                nodes,
                node_id,
                "publication_activation_check",
                check_index=index + 1,
                status=completion_definition.get("status"),
                check=check_id,
                summary=(
                    "Post-experiment manuscript activation requires closure "
                    f"check {index + 1}: {check_id}."
                ),
            )
            add_edge(
                edges,
                post_program_catalog_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_program_json),
                evidence=f"$.experiment_completion_definition.closure_checks[{index}]",
            )
        reviewer_design_gate = post_program.get("reviewer_design_gate") or {}
        for index, topic in enumerate(
            reviewer_design_gate.get("required_advice_topics") or []
        ):
            topic_id = str(topic)
            node_id = f"publication_design_requirement:{slug_fragment(topic_id)}"
            add_node(
                nodes,
                node_id,
                "publication_design_requirement",
                topic_id=topic_id,
                summary=(
                    "Reviewer-driven manuscript design must cover advice topic "
                    f"`{topic_id}` before drafting."
                ),
            )
            add_edge(
                edges,
                post_program_catalog_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_program_json),
                evidence=f"$.reviewer_design_gate.required_advice_topics[{index}]",
            )
        visual_audit = post_program.get("visual_table_audit_agent") or {}
        for rule_key, rule_text in sorted(
            (visual_audit.get("agent_contract") or {}).items()
        ):
            rule_id = str(rule_key)
            node_id = f"publication_auditor_contract_rule:{slug_fragment(rule_id)}"
            add_node(
                nodes,
                node_id,
                "publication_auditor_contract_rule",
                agent_role=visual_audit.get("agent_role"),
                rule_id=rule_id,
                rule=str(rule_text),
                summary=(
                    "Visual/table auditor contract rule "
                    f"`{rule_id}`: {rule_text}"
                ),
            )
            add_edge(
                edges,
                post_program_catalog_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_program_json),
                evidence=f"$.visual_table_audit_agent.agent_contract.{rule_id}",
            )
        for index, check in enumerate(visual_audit.get("quality_checks") or []):
            check_id = str(check)
            node_id = f"publication_quality_check:{slug_fragment(check_id)}"
            add_node(
                nodes,
                node_id,
                "publication_quality_check",
                agent_role=visual_audit.get("agent_role"),
                check=check_id,
                summary=(
                    "Visual/table audit quality check required before retaining "
                    f"an artifact: {check_id}."
                ),
            )
            add_edge(
                edges,
                post_program_catalog_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_program_json),
                evidence=f"$.visual_table_audit_agent.quality_checks[{index}]",
            )
        for index, artifact in enumerate(
            visual_audit.get("required_output_artifacts") or []
        ):
            artifact_id = str(artifact)
            node_id = f"publication_audit_artifact:{slug_fragment(artifact_id)}"
            add_node(
                nodes,
                node_id,
                "publication_audit_artifact",
                artifact_id=artifact_id,
                summary=(
                    "Visual/table audit must produce required artifact "
                    f"`{artifact_id}`."
                ),
            )
            add_edge(
                edges,
                post_program_catalog_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_program_json),
                evidence=(
                    "$.visual_table_audit_agent."
                    f"required_output_artifacts[{index}]"
                ),
            )
        publication_triptych = post_program.get("publication_triptych") or {}
        for index, component in enumerate(publication_triptych.get("components") or []):
            component_id = str(component)
            node_id = f"publication_triptych_component:{slug_fragment(component_id)}"
            add_node(
                nodes,
                node_id,
                "publication_triptych_component",
                component_id=component_id,
                status=publication_triptych.get("status"),
                summary=(
                    "Deferred publication triptych component "
                    f"`{component_id}`."
                ),
            )
            add_edge(
                edges,
                post_program_catalog_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_program_json),
                evidence=f"$.publication_triptych.components[{index}]",
            )
    add_node(
        nodes,
        "catalog:target_domain_provenance",
        "catalog",
        path="experiments/regression/catalogs/target_domain_provenance.md",
        json_path="experiments/regression/catalogs/target_domain_provenance.json",
        summary="Source-backed catalog of regression target-domain natural bounds used by bounded-support audits.",
    )
    add_node(
        nodes,
        "catalog:source_registry",
        "catalog",
        path="experiments/regression/catalogs/source_registry.md",
    )
    add_node(
        nodes,
        "catalog:external_source_discovery_watchlist",
        "catalog",
        path="experiments/regression/catalogs/external_source_discovery_watchlist.md",
        json_path="experiments/regression/catalogs/external_source_discovery_watchlist.json",
        summary="Machine-readable watchlist of external regression dataset source families, local audit coverage, and discovery gaps.",
    )
    add_node(
        nodes,
        "catalog:openml_discovery",
        "catalog",
        path="experiments/regression/catalogs/openml_feature_discovery.jsonl",
    )
    add_node(
        nodes,
        "catalog:openml_ranked_candidates",
        "catalog",
        path="experiments/regression/catalogs/openml_ranked_candidates.jsonl",
    )
    add_node(
        nodes,
        "catalog:openml_ranked_candidates_md",
        "catalog",
        path="experiments/regression/catalogs/openml_ranked_candidates.md",
    )
    add_node(
        nodes,
        "catalog:openml_review_decisions",
        "catalog",
        path=args.openml_review_decisions,
    )
    add_node(
        nodes,
        "catalog:internet_dataset_inventory",
        "catalog",
        path="experiments/regression/catalogs/internet_dataset_inventory.jsonl",
    )
    add_node(
        nodes,
        "catalog:internet_dataset_inventory_md",
        "catalog",
        path="experiments/regression/catalogs/internet_dataset_inventory.md",
    )
    add_node(
        nodes,
        "log:data_scientist_diary",
        "log",
        path="experiments/regression/diary/data_scientist_log.md",
    )
    add_node(
        nodes,
        "log:regression_changelog",
        "log",
        path="experiments/regression/CHANGELOG.md",
    )
    add_node(
        nodes,
        "doc:root_readme",
        "catalog",
        path="README.md",
        summary="Current working-repository README; not the final sterile publication README.",
    )
    add_node(
        nodes,
        "catalog:regression_changelog",
        "catalog",
        path="experiments/regression/CHANGELOG.md",
        summary="Regression experiment changelog used as release-note source material.",
    )
    add_node(
        nodes,
        "run_registry:regression_long_runs",
        "run_registry",
        path="experiments/regression/runs/run_registry.md",
    )
    add_node(
        nodes,
        "method_spec:venn_abers_regression",
        "method_spec",
        path="experiments/regression/method_specs/venn_abers_regression.md",
    )
    add_node(
        nodes,
        "method_spec:split_and_cqr_regression",
        "method_spec",
        path="experiments/regression/method_specs/split_and_cqr_regression.md",
    )
    add_node(
        nodes,
        "method_spec:plus_family_regression",
        "method_spec",
        path="experiments/regression/method_specs/plus_family_regression.md",
    )
    add_node(
        nodes,
        "method_spec:tail_specific_split_regression",
        "method_spec",
        path="experiments/regression/method_specs/tail_specific_split_regression.md",
    )
    add_node(
        nodes,
        "method_spec:covariate_shift_regression",
        "method_spec",
        path="experiments/regression/method_specs/covariate_shift_regression.md",
    )
    add_node(
        nodes,
        "method_spec:risk_control_and_boundary_methods",
        "method_spec",
        path="experiments/regression/method_specs/risk_control_and_boundary_methods.md",
    )
    add_node(
        nodes,
        "method_spec:distributional_and_full_conformal_regression",
        "method_spec",
        path="experiments/regression/method_specs/distributional_and_full_conformal_regression.md",
    )
    commit_node = current_commit_node()
    if commit_node:
        commit_id, commit_attrs = commit_node
        add_node(nodes, commit_id, "commit", **commit_attrs)
        add_edge(edges, "catalog:knowledge_graph", commit_id, "RECORDED_AT_COMMIT")
    add_standard_metric_nodes(nodes)
    add_edge(
        edges,
        "catalog:openml_ranked_candidates",
        "catalog:openml_discovery",
        "DERIVED_FROM",
    )
    add_edge(
        edges,
        "catalog:openml_ranked_candidates_md",
        "catalog:openml_ranked_candidates",
        "RENDERS",
    )
    add_edge(
        edges,
        "catalog:openml_review_decisions",
        "catalog:openml_ranked_candidates",
        "REVIEWS",
    )
    add_edge(
        edges,
        "catalog:external_source_discovery_watchlist",
        "catalog:source_registry",
        "EXTENDS",
    )
    add_edge(
        edges,
        "catalog:external_source_discovery_watchlist",
        "catalog:dataset_candidates",
        "REVIEWS",
    )
    add_edge(
        edges,
        "catalog:external_source_discovery_watchlist",
        "catalog:openml_discovery",
        "REVIEWS",
    )
    add_edge(
        edges,
        "catalog:external_source_discovery_watchlist",
        "catalog:openml_ranked_candidates",
        "REVIEWS",
    )
    add_edge(
        edges,
        "catalog:internet_dataset_inventory_md",
        "catalog:internet_dataset_inventory",
        "RENDERS",
    )
    add_edge(
        edges,
        "catalog:internet_dataset_inventory",
        "catalog:source_registry",
        "EXTENDS",
    )
    add_edge(
        edges, "catalog:dataset_candidates", "catalog:source_registry", "CITES_SOURCES"
    )
    add_edge(
        edges,
        "catalog:target_domain_provenance",
        "catalog:source_registry",
        "CITES_SOURCES",
    )
    add_edge(
        edges, "catalog:knowledge_graph", "catalog:dataset_candidates", "CITES_SOURCES"
    )
    add_edge(
        edges, "catalog:knowledge_graph", "catalog:method_registry", "CITES_SOURCES"
    )
    add_edge(
        edges,
        "catalog:knowledge_graph",
        "catalog:target_domain_provenance",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:method_registry",
        "catalog:regression_literature_notes",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:knowledge_graph",
        "catalog:manuscript_claim_register",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:knowledge_graph",
        "catalog:manuscript_evidence_manifest_schema",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:knowledge_graph",
        "catalog:manuscript_bundle_index",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:knowledge_graph",
        "catalog:publication_readiness_protocol",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:knowledge_graph",
        "catalog:post_experiment_publication_program",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:knowledge_graph",
        "catalog:post_experiment_publication_activation_audit",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:publication_readiness_protocol",
        "catalog:manuscript_evidence_manifest_schema",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:publication_readiness_protocol",
        "catalog:manuscript_claim_register",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:manuscript_claim_register_md",
        "catalog:manuscript_claim_register",
        "RENDERS",
    )
    add_edge(
        edges,
        "catalog:manuscript_bundle_index_md",
        "catalog:manuscript_bundle_index",
        "RENDERS",
    )
    for node_id in manuscript_catalogs:
        add_edge(edges, node_id, "catalog:manuscript_bundle_index", "DERIVED_FROM")
        add_edge(
            edges, node_id, "catalog:publication_readiness_protocol", "CITES_SOURCES"
        )
    add_edge(
        edges,
        "catalog:post_experiment_publication_program",
        "catalog:manuscript_paper_readiness_map",
        "DERIVED_FROM",
    )
    manuscript_bundle_index_path = Path(
        "experiments/regression/catalogs/manuscript_bundle_index.json"
    )
    if manuscript_bundle_index_path.exists():
        try:
            manuscript_bundle_index = json.loads(
                manuscript_bundle_index_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            manuscript_bundle_index = {}
        for bundle in manuscript_bundle_index.get("bundles", []) or []:
            if not isinstance(bundle, dict):
                continue
            manifest_path = bundle.get("manifest_path")
            if not manifest_path:
                continue
            report_name = Path(str(manifest_path)).parent.name
            manifest_id = f"manifest:{report_name}:publication_readiness"
            add_edge(
                edges,
                "catalog:manuscript_bundle_index",
                manifest_id,
                "INDEXES_MANIFEST",
                evidence_path=str(manuscript_bundle_index_path),
            )
    add_edge(
        edges,
        "catalog:manuscript_dataset_table",
        "catalog:source_registry",
        "CITES_SOURCES",
    )
    add_edge(
        edges,
        "catalog:manuscript_method_table",
        "catalog:method_registry",
        "CITES_SOURCES",
    )
    add_edge(edges, "catalog:audit_index", "catalog:dataset_candidates", "REVIEWS")
    add_edge(
        edges, "catalog:method_registry", "policy:data_policy_registry", "COMPLEMENTS"
    )
    add_edge(edges, "log:data_scientist_diary", "catalog:dataset_candidates", "NOTES")
    add_edge(
        edges,
        "log:regression_changelog",
        "catalog:knowledge_graph",
        "SUMMARIZES_CHANGES_TO",
    )
    add_edge(edges, "log:regression_changelog", "catalog:dataset_candidates", "NOTES")
    add_edge(
        edges,
        "run_registry:regression_long_runs",
        "catalog:dataset_candidates",
        "RUNS_DATASETS_FROM",
    )
    add_edge(
        edges,
        "method:ivapd_regression",
        "method_spec:venn_abers_regression",
        "SPECIFIED_BY",
    )
    add_edge(
        edges,
        "method:generalized_venn_abers_quantile",
        "method_spec:venn_abers_regression",
        "SPECIFIED_BY",
    )
    add_edge(
        edges,
        "method:ivar_regression_unbounded",
        "method_spec:venn_abers_regression",
        "SPECIFIED_BY",
    )
    add_edge(
        edges,
        "method:venn_abers_quantile",
        "method_spec:venn_abers_regression",
        "SPECIFIED_BY",
    )
    add_edge(
        edges,
        "method:venn_abers_split_fallback",
        "method_spec:venn_abers_regression",
        "SPECIFIED_BY",
    )
    add_edge(
        edges,
        "method:venn_abers_quantile_grid",
        "method_spec:venn_abers_regression",
        "SPECIFIED_BY",
    )
    for base_method in (
        "split_abs",
        "mondrian_abs",
        "shrink_gamma",
        "normalized_abs",
        "cqr",
        "cqr_model_matched",
    ):
        add_edge(
            edges,
            f"method:{base_method}",
            "method_spec:split_and_cqr_regression",
            "SPECIFIED_BY",
        )
    for gamma in ("0.00", "0.10", "0.25", "0.50", "0.75", "0.90", "1.00"):
        variant_id = f"method:shrink_{gamma}"
        add_node(
            nodes,
            variant_id,
            "method",
            method_id=f"shrink_{gamma}",
            base_method_id="shrink_gamma",
            summary=f"Shrinkage conformal variant with gamma={gamma}.",
        )
        add_edge(edges, variant_id, "method:shrink_gamma", "VARIANT_OF_METHOD")
        add_edge(
            edges, variant_id, "method_spec:split_and_cqr_regression", "SPECIFIED_BY"
        )
    for plus_method in (
        "jackknife_plus",
        "jackknife_minmax",
        "jackknife_plus_after_bootstrap",
        "cv_plus",
        "cv_minmax",
        "cv_plus_grouped",
        "cv_minmax_grouped",
    ):
        add_edge(
            edges,
            f"method:{plus_method}",
            "method_spec:plus_family_regression",
            "SPECIFIED_BY",
        )
    for tail_method in (
        "split_tail_0.25",
        "split_tail_0.50",
        "split_tail_0.75",
        "split_tail_grid_shortest",
    ):
        add_edge(
            edges,
            f"method:{tail_method}",
            "method_spec:tail_specific_split_regression",
            "SPECIFIED_BY",
        )
    add_edge(
        edges,
        "method:weighted_abs_covariate_shift",
        "method_spec:covariate_shift_regression",
        "SPECIFIED_BY",
    )
    add_edge(
        edges,
        "method:conformal_risk_control",
        "method_spec:risk_control_and_boundary_methods",
        "SPECIFIED_BY",
    )
    add_edge(
        edges,
        "method:venn_abers_classification",
        "method_spec:risk_control_and_boundary_methods",
        "SPECIFIED_BY",
    )
    for distributional_method in (
        "full_conformal_regression",
        "rank_one_out_conformal",
        "distributional_conformal_prediction",
        "conformal_predictive_system",
        "tail_allocation_shortest_interval",
    ):
        add_edge(
            edges,
            f"method:{distributional_method}",
            "method_spec:distributional_and_full_conformal_regression",
            "SPECIFIED_BY",
        )
    add_node(
        nodes,
        "report:venn_abers_quantile_bridge_benchmark",
        "method_report",
        path="experiments/regression/reports/venn_abers_quantile_bridge_benchmark/benchmark.md",
        json_path="experiments/regression/reports/venn_abers_quantile_bridge_benchmark/benchmark.json",
    )
    add_edge(
        edges,
        "report:venn_abers_quantile_bridge_benchmark",
        "method:venn_abers_quantile",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_quantile_bridge_benchmark",
        "method:venn_abers_quantile_grid",
        "USES_REFERENCE",
    )
    add_edge(
        edges,
        "report:venn_abers_quantile_bridge_benchmark",
        "method_spec:venn_abers_regression",
        "EVIDENCES",
    )
    add_node(
        nodes,
        "report:ivapd_threshold_grid_benchmark",
        "method_report",
        path="experiments/regression/reports/ivapd_threshold_grid_benchmark/benchmark.md",
        json_path="experiments/regression/reports/ivapd_threshold_grid_benchmark/benchmark.json",
    )
    add_edge(
        edges,
        "report:ivapd_threshold_grid_benchmark",
        "method:ivapd_regression",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:ivapd_threshold_grid_benchmark",
        "module:cpfi.regression.venn_abers",
        "USES_MODULE",
    )
    add_edge(
        edges,
        "report:ivapd_threshold_grid_benchmark",
        "method_spec:venn_abers_regression",
        "EVIDENCES",
    )
    add_node(
        nodes,
        "report:venn_abers_real_data_diagnostic",
        "method_report",
        path="experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.md",
        json_path="experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json",
    )
    add_edge(
        edges,
        "report:venn_abers_real_data_diagnostic",
        "method:venn_abers_quantile",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_real_data_diagnostic",
        "method:venn_abers_quantile_grid",
        "USES_REFERENCE",
    )
    add_edge(
        edges,
        "report:venn_abers_real_data_diagnostic",
        "method:ivapd_regression",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_real_data_diagnostic",
        "method_spec:venn_abers_regression",
        "EVIDENCES",
    )
    add_edge(
        edges,
        "report:venn_abers_real_data_diagnostic",
        "config:regression_venn_abers_real_data_diagnostic_v0",
        "SUMMARIZES_CONFIG",
    )
    add_edge(
        edges,
        "report:venn_abers_real_data_diagnostic",
        "dataset:uci_student_performance",
        "SUMMARIZES_DATASET",
    )
    add_edge(
        edges,
        "report:venn_abers_real_data_diagnostic",
        "dataset:uci_auto_mpg",
        "SUMMARIZES_DATASET",
    )
    add_node(
        nodes,
        "report:venn_abers_fairness_panel_diagnostic",
        "method_report",
        path="experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.md",
        json_path="experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.json",
    )
    add_edge(
        edges,
        "report:venn_abers_fairness_panel_diagnostic",
        "method:venn_abers_quantile",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_fairness_panel_diagnostic",
        "method:venn_abers_split_fallback",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_fairness_panel_diagnostic",
        "method:venn_abers_quantile_grid",
        "USES_REFERENCE",
    )
    add_edge(
        edges,
        "report:venn_abers_fairness_panel_diagnostic",
        "method:ivapd_regression",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_fairness_panel_diagnostic",
        "method_spec:venn_abers_regression",
        "EVIDENCES",
    )
    add_edge(
        edges,
        "report:venn_abers_fairness_panel_diagnostic",
        "config:regression_venn_abers_fairness_panel_diagnostic_v0",
        "SUMMARIZES_CONFIG",
    )
    for dataset_id in (
        "openml_cps_85_wages",
        "openml_analcatdata_chlamydia",
        "aif360_lawschool_gpa",
        "fairlearn_acs_income_wy",
    ):
        add_edge(
            edges,
            "report:venn_abers_fairness_panel_diagnostic",
            f"dataset:{dataset_id}",
            "SUMMARIZES_DATASET",
        )
    add_node(
        nodes,
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "method_report",
        path="experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.md",
        json_path="experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json",
    )
    add_edge(
        edges,
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "method:venn_abers_quantile",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "method:venn_abers_split_fallback",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "method:venn_abers_quantile_grid",
        "USES_REFERENCE",
    )
    add_edge(
        edges,
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "method:ivapd_regression",
        "EVALUATES_METHOD",
    )
    add_edge(
        edges,
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "method_spec:venn_abers_regression",
        "EVIDENCES",
    )
    add_edge(
        edges,
        "report:venn_abers_biomarker_clinical_panel_diagnostic",
        "config:regression_venn_abers_biomarker_clinical_panel_diagnostic_v0",
        "SUMMARIZES_CONFIG",
    )
    for dataset_id in ("openml_cholesterol_chol", "openml_plasma_retinol"):
        add_edge(
            edges,
            "report:venn_abers_biomarker_clinical_panel_diagnostic",
            f"dataset:{dataset_id}",
            "SUMMARIZES_DATASET",
        )
    add_node(
        nodes,
        "module:cpfi.regression.venn_abers",
        "module",
        path="cpfi/regression/venn_abers.py",
    )
    add_edge(
        edges,
        "module:cpfi.regression.venn_abers",
        "method:ivapd_regression",
        "IMPLEMENTS_PROTOTYPE",
    )
    add_edge(
        edges,
        "module:cpfi.regression.venn_abers",
        "method_spec:venn_abers_regression",
        "IMPLEMENTS_SPEC",
    )
    add_node(
        nodes,
        "graph:system_ontology",
        "graph",
        path="experiments/regression/graphs/system_ontology.mmd",
    )
    add_node(
        nodes,
        "graph:data_flow",
        "graph",
        path="experiments/regression/graphs/data_flow.mmd",
    )
    add_node(
        nodes,
        "graph:control_flow",
        "graph",
        path="experiments/regression/graphs/control_flow.mmd",
    )
    add_node(
        nodes,
        "graph:dependency_graph",
        "graph",
        path="experiments/regression/graphs/dependency_graph.mmd",
    )
    for graph_id in (
        "system_ontology",
        "data_flow",
        "control_flow",
        "dependency_graph",
    ):
        add_edge(
            edges, f"graph:{graph_id}", "catalog:knowledge_graph", "DOCUMENTS_GRAPH"
        )
    methodology_report_id = "report:methodology_sanity_audit_20260627"
    methodology_report_path = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/sanity_audit.md"
    )
    methodology_report_json = methodology_report_path.with_suffix(".json")
    if methodology_report_path.exists() or methodology_report_json.exists():
        add_node(
            nodes,
            methodology_report_id,
            "report",
            path=(
                str(methodology_report_path)
                if methodology_report_path.exists()
                else None
            ),
            json_path=(
                str(methodology_report_json)
                if methodology_report_json.exists()
                else None
            ),
            summary="Regression methodology sanity audit covering backlog, leakage, and claim guardrail checks.",
        )
    duplicate_backlog_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "duplicate_split_caveat_backlog.json"
    )
    duplicate_backlog_md = duplicate_backlog_json.with_suffix(".md")
    if duplicate_backlog_json.exists():
        duplicate_backlog_id = "report:duplicate_split_caveat_backlog"
        add_node(
            nodes,
            duplicate_backlog_id,
            "report",
            path=str(duplicate_backlog_md) if duplicate_backlog_md.exists() else None,
            json_path=str(duplicate_backlog_json),
            summary="Machine-readable backlog for duplicate-content split caveats requiring duplicate-aware sensitivity.",
        )
        add_edge(edges, duplicate_backlog_id, methodology_report_id, "SUPPORTS_REPORT")
        try:
            duplicate_backlog = json.loads(
                duplicate_backlog_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            duplicate_backlog = {}
        for row_index, row in enumerate(duplicate_backlog.get("rows", []) or []):
            dataset_id = row.get("dataset_id")
            if dataset_id:
                add_edge(
                    edges,
                    duplicate_backlog_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(duplicate_backlog_json),
                    evidence=row_selector("rows", row_index, "dataset_id"),
                )
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    duplicate_backlog_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                    evidence_path=str(duplicate_backlog_json),
                    evidence=row_selector("rows", row_index, "report_id"),
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges,
                    duplicate_backlog_id,
                    config_id,
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(duplicate_backlog_json),
                    evidence=row_selector("rows", row_index, "config_path"),
                )
    paired_duplicate_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "paired_duplicate_sensitivity_audit.json"
    )
    paired_duplicate_audit_md = paired_duplicate_audit_json.with_suffix(".md")
    if paired_duplicate_audit_json.exists():
        paired_duplicate_audit_id = "report:paired_duplicate_sensitivity_audit"
        add_node(
            nodes,
            paired_duplicate_audit_id,
            "report",
            path=(
                str(paired_duplicate_audit_md)
                if paired_duplicate_audit_md.exists()
                else None
            ),
            json_path=str(paired_duplicate_audit_json),
            summary="Paired raw-vs-dedup duplicate sensitivity audit over matched model and conformal-method grid rows.",
        )
        add_edge(
            edges, paired_duplicate_audit_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        if duplicate_backlog_json.exists():
            add_edge(
                edges,
                paired_duplicate_audit_id,
                "report:duplicate_split_caveat_backlog",
                "SUPPORTS_REPORT",
            )
        try:
            paired_audit = json.loads(
                paired_duplicate_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            paired_audit = {}
        for item_index, item in enumerate(paired_audit.get("datasets", []) or []):
            for dataset_key in ("raw_dataset_id", "dedup_dataset_id"):
                dataset_id = item.get(dataset_key)
                if dataset_id:
                    add_edge(
                        edges,
                        paired_duplicate_audit_id,
                        f"dataset:{dataset_id}",
                        "SUMMARIZES_DATASET",
                        evidence_path=str(paired_duplicate_audit_json),
                        evidence=row_selector("datasets", item_index, dataset_key),
                    )
            report_id = item.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    paired_duplicate_audit_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                    evidence_path=str(paired_duplicate_audit_json),
                    evidence=row_selector("datasets", item_index, "report_id"),
                )
            config_path = item.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges,
                    paired_duplicate_audit_id,
                    config_id,
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(paired_duplicate_audit_json),
                    evidence=row_selector("datasets", item_index, "config_path"),
                )

    cross_run_integrity_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "cross_run_integrity_audit.json"
    )
    cross_run_integrity_md = cross_run_integrity_json.with_suffix(".md")
    if cross_run_integrity_json.exists():
        cross_run_integrity_id = "report:cross_run_integrity_audit"
        add_node(
            nodes,
            cross_run_integrity_id,
            "report",
            path=(
                str(cross_run_integrity_md) if cross_run_integrity_md.exists() else None
            ),
            json_path=str(cross_run_integrity_json),
            summary="Cross-run scientific integrity matrix for leakage, split, endpoint, sidecar, and claim-guardrail status.",
        )
        add_edge(
            edges, cross_run_integrity_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        try:
            cross_run_integrity = json.loads(
                cross_run_integrity_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            cross_run_integrity = {}
        for row_index, row in enumerate(cross_run_integrity.get("rows", []) or []):
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    cross_run_integrity_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                    evidence_path=str(cross_run_integrity_json),
                    evidence=row_selector("rows", row_index, "report_id"),
                )
                for sidecar_name in (
                    "split_profile",
                    "endpoint_audit",
                    "feature_leakage_audit",
                ):
                    sidecar = row.get(sidecar_name) or {}
                    if sidecar.get("present"):
                        add_edge(
                            edges,
                            cross_run_integrity_id,
                            f"{report_id}:{sidecar_name}",
                            "SUPPORTS_REPORT",
                            evidence_path=str(cross_run_integrity_json),
                            evidence=row_selector("rows", row_index, sidecar_name),
                        )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    cross_run_integrity_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(cross_run_integrity_json),
                    evidence=row_selector("rows", row_index, "dataset_ids"),
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges,
                    cross_run_integrity_id,
                    config_id,
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(cross_run_integrity_json),
                    evidence=row_selector("rows", row_index, "config_path"),
                )

    experiment_accounting_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "experiment_accounting_audit.json"
    )
    experiment_accounting_md = experiment_accounting_json.with_suffix(".md")
    if experiment_accounting_json.exists():
        experiment_accounting_id = "report:experiment_accounting_audit"
        add_node(
            nodes,
            experiment_accounting_id,
            "report",
            path=(
                str(experiment_accounting_md)
                if experiment_accounting_md.exists()
                else None
            ),
            json_path=str(experiment_accounting_json),
            summary="Experiment row-accounting audit reconciling raw ledgers, canonical rows, publication scope, manuscript scope, and Venn-Abers grid rows.",
        )
        add_edge(
            edges, experiment_accounting_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        for source_id, source_path, selector in [
            (
                "report:cross_run_integrity_audit",
                cross_run_integrity_json,
                "$.source_accounting.cross_run_completed_rows",
            ),
            (
                "report:publication_methodology_audit",
                Path(
                    "experiments/regression/reports/methodology_sanity_audit_20260627/"
                    "publication_methodology_audit.json"
                ),
                "$.source_accounting.publication_completed_rows",
            ),
            (
                "report:selection_multiplicity_protocol",
                Path(
                    "experiments/regression/manuscript/"
                    "selection_multiplicity_protocol.json"
                ),
                "$.source_accounting.selection_completed_rows_scanned",
            ),
            (
                "report:bounded_support_posthandling_validation",
                Path(
                    "experiments/regression/manuscript/"
                    "bounded_support_posthandling_validation.json"
                ),
                "$.source_accounting.bounded_support_selected_completed_rows",
            ),
            (
                "report:venn_abers_grid_expansion_plan",
                Path(
                    "experiments/regression/reports/methodology_sanity_audit_20260627/"
                    "venn_abers_grid_expansion_plan.json"
                ),
                "$.source_accounting.venn_grid_rows_completed",
            ),
            (
                "report:venn_abers_grid_ivapd_validation_protocol",
                Path(
                    "experiments/regression/reports/methodology_sanity_audit_20260627/"
                    "venn_abers_grid_ivapd_validation_protocol.json"
                ),
                "$.source_accounting.venn_ivapd_grid_reference_rows_scored",
            ),
        ]:
            if source_path.exists():
                add_edge(
                    edges,
                    experiment_accounting_id,
                    source_id,
                    "DERIVED_FROM",
                    evidence_path=str(experiment_accounting_json),
                    evidence=selector,
                )

    method_performance_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_performance_synthesis.json"
    )
    method_performance_md = method_performance_json.with_suffix(".md")
    if method_performance_json.exists():
        method_performance_id = "report:method_performance_synthesis"
        add_node(
            nodes,
            method_performance_id,
            "report",
            path=str(method_performance_md) if method_performance_md.exists() else None,
            json_path=str(method_performance_json),
            summary="Descriptive method-performance synthesis over the audited publication surface; records method-level evidence without selecting a final winner.",
        )
        add_edge(edges, method_performance_id, methodology_report_id, "SUPPORTS_REPORT")
        add_edge(
            edges,
            method_performance_id,
            "report:cross_run_integrity_audit",
            "DERIVED_FROM",
            evidence_path=str(method_performance_json),
            evidence="$.source_artifacts.cross_run_integrity",
        )
        try:
            method_performance = json.loads(
                method_performance_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            method_performance = {}
        for row in method_performance.get("method_rows") or []:
            method_id = str(row.get("cp_method") or "").strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_performance_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_performance_json),
                evidence=json_array_selector(
                    "cp_method", method_id, root="$.method_rows"
                ),
            )
            if method_id.startswith("cqr_gb_"):
                add_edge(
                    edges,
                    method_graph_id,
                    "method:cqr",
                    "VARIANT_OF_METHOD",
                    evidence_path=str(method_performance_json),
                    evidence=json_array_selector(
                        "cp_method", method_id, root="$.method_rows"
                    ),
                )
                add_edge(
                    edges,
                    method_graph_id,
                    "method_spec:split_and_cqr_regression",
                    "SPECIFIED_BY",
                    evidence_path=str(method_performance_json),
                    evidence=json_array_selector(
                        "cp_method", method_id, root="$.method_rows"
                    ),
                )

    method_selection_candidate_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_candidate_audit.json"
    )
    method_selection_candidate_md = method_selection_candidate_json.with_suffix(".md")
    if method_selection_candidate_json.exists():
        method_selection_candidate_id = "report:method_selection_candidate_audit"
        add_node(
            nodes,
            method_selection_candidate_id,
            "report",
            path=(
                str(method_selection_candidate_md)
                if method_selection_candidate_md.exists()
                else None
            ),
            json_path=str(method_selection_candidate_json),
            summary="Candidate shortlist and paired method-comparison audit that preserves the no-final-selection claim boundary.",
        )
        add_edge(
            edges,
            method_selection_candidate_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, selector in [
            (
                "report:method_performance_synthesis",
                "$.source_artifacts.method_performance_synthesis",
            ),
            (
                "report:selection_multiplicity_protocol",
                "$.source_artifacts.selection_multiplicity_protocol",
            ),
            (
                "report:final_selection_claim_boundary_audit",
                "$.source_artifacts.final_selection_claim_boundary",
            ),
            (
                "report:venn_abers_validation_readiness_audit",
                "$.source_artifacts.venn_abers_validation_readiness",
            ),
        ]:
            add_edge(
                edges,
                method_selection_candidate_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(method_selection_candidate_json),
                evidence=selector,
            )
        try:
            method_selection_candidate = json.loads(
                method_selection_candidate_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            method_selection_candidate = {}
        for row in method_selection_candidate.get("shortlist_methods") or []:
            method_id = str(row.get("cp_method") or "").strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_candidate_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_candidate_json),
                evidence=json_array_selector(
                    "cp_method", method_id, root="$.shortlist_methods"
                ),
            )
        for row in method_selection_candidate.get("excluded_methods") or []:
            method_id = str(row.get("cp_method") or "").strip()
            if not method_id or not method_id.startswith("venn_abers"):
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_candidate_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_candidate_json),
                evidence=json_array_selector(
                    "cp_method", method_id, root="$.excluded_methods"
                ),
            )

    method_selection_robustness_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_robustness_audit.json"
    )
    method_selection_robustness_md = method_selection_robustness_json.with_suffix(".md")
    if method_selection_robustness_json.exists():
        method_selection_robustness_id = "report:method_selection_robustness_audit"
        add_node(
            nodes,
            method_selection_robustness_id,
            "report",
            path=(
                str(method_selection_robustness_md)
                if method_selection_robustness_md.exists()
                else None
            ),
            json_path=str(method_selection_robustness_json),
            summary="Candidate method-selection stability audit using common-cell, leave-one-group, and bootstrap diagnostics without final winner claims.",
        )
        add_edge(
            edges,
            method_selection_robustness_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, selector in [
            (
                "report:method_performance_synthesis",
                "$.source_artifacts.method_performance_synthesis",
            ),
            (
                "report:method_selection_candidate_audit",
                "$.source_artifacts.method_selection_candidate_audit",
            ),
            (
                "report:selection_multiplicity_protocol",
                "$.source_artifacts.selection_multiplicity_protocol",
            ),
            (
                "report:final_selection_claim_boundary_audit",
                "$.source_artifacts.final_selection_claim_boundary",
            ),
        ]:
            add_edge(
                edges,
                method_selection_robustness_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(method_selection_robustness_json),
                evidence=selector,
            )
        try:
            method_selection_robustness = json.loads(
                method_selection_robustness_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            method_selection_robustness = {}
        robustness_summary = method_selection_robustness.get("summary") or {}
        for method_id in robustness_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_robustness_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_robustness_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )

    method_selection_alpha_expansion_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_alpha_expansion_plan.json"
    )
    method_selection_alpha_expansion_md = (
        method_selection_alpha_expansion_json.with_suffix(".md")
    )
    if method_selection_alpha_expansion_json.exists():
        method_selection_alpha_expansion_id = (
            "report:method_selection_alpha_expansion_plan"
        )
        add_node(
            nodes,
            method_selection_alpha_expansion_id,
            "report",
            path=(
                str(method_selection_alpha_expansion_md)
                if method_selection_alpha_expansion_md.exists()
                else None
            ),
            json_path=str(method_selection_alpha_expansion_json),
            summary="Alpha-support expansion work queue for method-selection robustness; records planned dataset-alpha-method tasks without final winner claims.",
        )
        add_edge(
            edges,
            method_selection_alpha_expansion_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, selector in [
            (
                "report:method_performance_synthesis",
                "$.source_artifacts.method_performance_synthesis",
            ),
            (
                "report:method_selection_candidate_audit",
                "$.source_artifacts.method_selection_candidate_audit",
            ),
            (
                "report:method_selection_robustness_audit",
                "$.source_artifacts.method_selection_robustness_audit",
            ),
            (
                "report:cross_run_integrity_audit",
                "$.source_artifacts.cross_run_integrity",
            ),
        ]:
            add_edge(
                edges,
                method_selection_alpha_expansion_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(method_selection_alpha_expansion_json),
                evidence=selector,
            )
        try:
            method_selection_alpha_expansion = json.loads(
                method_selection_alpha_expansion_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            method_selection_alpha_expansion = {}
        alpha_expansion_summary = (
            method_selection_alpha_expansion.get("summary") or {}
        )
        for method_id in alpha_expansion_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_alpha_expansion_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_alpha_expansion_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        alpha_task_rows = (
            method_selection_alpha_expansion.get("next_batch_dataset_alpha_tasks")
            or method_selection_alpha_expansion.get("task_pool")
            or []
        )
        alpha_task_selector = (
            "next_batch_dataset_alpha_tasks"
            if method_selection_alpha_expansion.get("next_batch_dataset_alpha_tasks")
            else "task_pool"
        )
        for row_index, row in enumerate(alpha_task_rows):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    method_selection_alpha_expansion_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(method_selection_alpha_expansion_json),
                    evidence=row_selector(
                        alpha_task_selector, row_index, "dataset_id"
                    ),
                )
            for source_index, source in enumerate(row.get("source_configs") or []):
                config_id = source.get("config_id")
                if config_id:
                    add_edge(
                        edges,
                        method_selection_alpha_expansion_id,
                        str(config_id),
                        "SUMMARIZES_CONFIG",
                        evidence_path=str(method_selection_alpha_expansion_json),
                        evidence=(
                            f"{alpha_task_selector}"
                            f"[{row_index}].source_configs[{source_index}].config_id"
                        ),
                    )

    method_selection_alpha_expansion_batch_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_alpha_expansion_batch.json"
    )
    method_selection_alpha_expansion_batch_md = (
        method_selection_alpha_expansion_batch_json.with_suffix(".md")
    )
    if method_selection_alpha_expansion_batch_json.exists():
        method_selection_alpha_expansion_batch_id = (
            "report:method_selection_alpha_expansion_batch"
        )
        add_node(
            nodes,
            method_selection_alpha_expansion_batch_id,
            "report",
            path=(
                str(method_selection_alpha_expansion_batch_md)
                if method_selection_alpha_expansion_batch_md.exists()
                else None
            ),
            json_path=str(method_selection_alpha_expansion_batch_json),
            summary="Runnable alpha-support expansion batch generated from the method-selection alpha expansion plan; records resumable configs without final winner claims.",
        )
        add_edge(
            edges,
            method_selection_alpha_expansion_batch_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        add_edge(
            edges,
            method_selection_alpha_expansion_batch_id,
            "report:method_selection_alpha_expansion_plan",
            "DERIVED_FROM",
            evidence_path=str(method_selection_alpha_expansion_batch_json),
            evidence="$.source_artifacts.method_selection_alpha_expansion_plan",
        )
        try:
            method_selection_alpha_expansion_batch = json.loads(
                method_selection_alpha_expansion_batch_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            method_selection_alpha_expansion_batch = {}
        alpha_expansion_batch_summary = (
            method_selection_alpha_expansion_batch.get("summary") or {}
        )
        for method_id in alpha_expansion_batch_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_alpha_expansion_batch_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_alpha_expansion_batch_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for row_index, row in enumerate(
            method_selection_alpha_expansion_batch.get("generated_configs") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    method_selection_alpha_expansion_batch_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(method_selection_alpha_expansion_batch_json),
                    evidence=row_selector("generated_configs", row_index, "dataset_id"),
                )
            experiment_id = str(row.get("experiment_id") or "").strip()
            if experiment_id:
                add_edge(
                    edges,
                    method_selection_alpha_expansion_batch_id,
                    f"config:{experiment_id}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(method_selection_alpha_expansion_batch_json),
                    evidence=row_selector(
                        "generated_configs", row_index, "experiment_id"
                    ),
                )
            source_config_id = str(row.get("source_config_id") or "").strip()
            if source_config_id:
                add_edge(
                    edges,
                    method_selection_alpha_expansion_batch_id,
                    source_config_id,
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(method_selection_alpha_expansion_batch_json),
                    evidence=row_selector(
                        "generated_configs", row_index, "source_config_id"
                    ),
                )

    method_selection_post_validation_batch_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_post_selection_validation_batch.json"
    )
    method_selection_post_validation_batch_md = (
        method_selection_post_validation_batch_json.with_suffix(".md")
    )
    if method_selection_post_validation_batch_json.exists():
        method_selection_post_validation_batch_id = (
            "report:method_selection_post_selection_validation_batch"
        )
        add_node(
            nodes,
            method_selection_post_validation_batch_id,
            "report",
            path=(
                str(method_selection_post_validation_batch_md)
                if method_selection_post_validation_batch_md.exists()
                else None
            ),
            json_path=str(method_selection_post_validation_batch_json),
            summary="Independent post-selection validation batch for the CQR, CV+, and Mondrian_abs shortlist; records resumable configs without final winner claims.",
        )
        add_edge(
            edges,
            method_selection_post_validation_batch_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        try:
            method_selection_post_validation_batch = json.loads(
                method_selection_post_validation_batch_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            method_selection_post_validation_batch = {}
        source_artifacts = (
            method_selection_post_validation_batch.get("source_artifacts") or {}
        )
        for source_key, source_report_id in (
            (
                "method_selection_alpha_expansion_batch",
                "report:method_selection_alpha_expansion_batch",
            ),
            (
                "method_selection_candidate_audit",
                "report:method_selection_candidate_audit",
            ),
            (
                "method_selection_robustness_audit",
                "report:method_selection_robustness_audit",
            ),
            (
                "method_selection_alpha_expansion_plan",
                "report:method_selection_alpha_expansion_plan",
            ),
            (
                "selection_multiplicity_protocol",
                "report:selection_multiplicity_protocol",
            ),
        ):
            if source_artifacts.get(source_key):
                add_edge(
                    edges,
                    method_selection_post_validation_batch_id,
                    source_report_id,
                    "DERIVED_FROM",
                    evidence_path=str(method_selection_post_validation_batch_json),
                    evidence=f"$.source_artifacts.{source_key}",
                )
        post_validation_summary = (
            method_selection_post_validation_batch.get("summary") or {}
        )
        for method_id in post_validation_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_post_validation_batch_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_post_validation_batch_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for row_index, row in enumerate(
            method_selection_post_validation_batch.get("generated_configs") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    method_selection_post_validation_batch_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(method_selection_post_validation_batch_json),
                    evidence=row_selector("generated_configs", row_index, "dataset_id"),
                )
            experiment_id = str(row.get("experiment_id") or "").strip()
            if experiment_id:
                add_edge(
                    edges,
                    method_selection_post_validation_batch_id,
                    f"config:{experiment_id}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(method_selection_post_validation_batch_json),
                    evidence=row_selector(
                        "generated_configs", row_index, "experiment_id"
                    ),
                )
            source_config = str(
                row.get("source_alpha_expansion_experiment_id") or ""
            ).strip()
            if source_config:
                add_edge(
                    edges,
                    method_selection_post_validation_batch_id,
                    f"config:{source_config}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(method_selection_post_validation_batch_json),
                    evidence=row_selector(
                        "generated_configs",
                        row_index,
                        "source_alpha_expansion_experiment_id",
                    ),
                )

    method_selection_post_validation_results_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_post_selection_validation_results.json"
    )
    method_selection_alpha_expansion_execution_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_alpha_expansion_execution_audit.json"
    )
    method_selection_inferential_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_selection_inferential_audit.json"
    )
    main_result_candidate_bundle_plan_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "main_result_candidate_bundle_plan.json"
    )
    main_result_candidate_bundle_results_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "main_result_candidate_bundle_results.json"
    )
    main_result_candidate_post_run_closure_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "main_result_candidate_post_run_closure_audit.json"
    )
    method_selection_post_validation_results_md = (
        method_selection_post_validation_results_json.with_suffix(".md")
    )
    if method_selection_post_validation_results_json.exists():
        method_selection_post_validation_results_id = (
            "report:method_selection_post_selection_validation_results"
        )
        add_node(
            nodes,
            method_selection_post_validation_results_id,
            "report",
            path=(
                str(method_selection_post_validation_results_md)
                if method_selection_post_validation_results_md.exists()
                else None
            ),
            json_path=str(method_selection_post_validation_results_json),
            summary="Completed post-selection validation result audit for the CQR, CV+, and Mondrian_abs shortlist; summarizes matched cells without final winner claims.",
        )
        add_edge(
            edges,
            method_selection_post_validation_results_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        try:
            method_selection_post_validation_results = json.loads(
                method_selection_post_validation_results_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            method_selection_post_validation_results = {}
        result_sources = (
            method_selection_post_validation_results.get("source_artifacts") or {}
        )
        if result_sources.get("method_selection_post_selection_validation_batch"):
            add_edge(
                edges,
                method_selection_post_validation_results_id,
                "report:method_selection_post_selection_validation_batch",
                "DERIVED_FROM",
                evidence_path=str(method_selection_post_validation_results_json),
                evidence="$.source_artifacts.method_selection_post_selection_validation_batch",
            )
        result_summary = method_selection_post_validation_results.get("summary") or {}
        for method_id in result_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_post_validation_results_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_post_validation_results_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for row_index, row in enumerate(
            method_selection_post_validation_results.get("dataset_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    method_selection_post_validation_results_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(method_selection_post_validation_results_json),
                    evidence=row_selector("dataset_rows", row_index, "dataset_id"),
                )
            experiment_id = str(row.get("experiment_id") or "").strip()
            if experiment_id:
                add_edge(
                    edges,
                    method_selection_post_validation_results_id,
                    f"config:{experiment_id}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(method_selection_post_validation_results_json),
                    evidence=row_selector("dataset_rows", row_index, "experiment_id"),
                )

    method_selection_alpha_expansion_execution_md = (
        method_selection_alpha_expansion_execution_json.with_suffix(".md")
    )
    if method_selection_alpha_expansion_execution_json.exists():
        method_selection_alpha_expansion_execution_id = (
            "report:method_selection_alpha_expansion_execution_audit"
        )
        add_node(
            nodes,
            method_selection_alpha_expansion_execution_id,
            "report",
            path=(
                str(method_selection_alpha_expansion_execution_md)
                if method_selection_alpha_expansion_execution_md.exists()
                else None
            ),
            json_path=str(method_selection_alpha_expansion_execution_json),
            summary="Execution-closure audit for method-selection alpha expansion; reconciles completed ledgers, refreshed alpha-support plan, and post-selection validation without final winner claims.",
        )
        add_edge(
            edges,
            method_selection_alpha_expansion_execution_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        try:
            method_selection_alpha_expansion_execution = json.loads(
                method_selection_alpha_expansion_execution_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            method_selection_alpha_expansion_execution = {}
        execution_sources = (
            method_selection_alpha_expansion_execution.get("source_artifacts") or {}
        )
        for source_key, source_report_id in (
            (
                "method_selection_alpha_expansion_plan",
                "report:method_selection_alpha_expansion_plan",
            ),
            (
                "method_selection_alpha_expansion_batch",
                "report:method_selection_alpha_expansion_batch",
            ),
            (
                "method_selection_post_selection_validation_results",
                "report:method_selection_post_selection_validation_results",
            ),
        ):
            if execution_sources.get(source_key):
                add_edge(
                    edges,
                    method_selection_alpha_expansion_execution_id,
                    source_report_id,
                    "DERIVED_FROM",
                    evidence_path=str(method_selection_alpha_expansion_execution_json),
                    evidence=f"$.source_artifacts.{source_key}",
                )
        execution_methods = {
            str(method_id).strip()
            for row in method_selection_alpha_expansion_execution.get("ledger_rows")
            or []
            for method_id in row.get("observed_completed_methods") or []
            if str(method_id).strip()
        }
        for method_id in sorted(execution_methods):
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_alpha_expansion_execution_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_alpha_expansion_execution_json),
                evidence=(
                    "$.ledger_rows[*].observed_completed_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for row_index, row in enumerate(
            method_selection_alpha_expansion_execution.get("ledger_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    method_selection_alpha_expansion_execution_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(method_selection_alpha_expansion_execution_json),
                    evidence=row_selector("ledger_rows", row_index, "dataset_id"),
                )
            experiment_id = str(row.get("experiment_id") or "").strip()
            if experiment_id:
                add_edge(
                    edges,
                    method_selection_alpha_expansion_execution_id,
                    f"config:{experiment_id}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(method_selection_alpha_expansion_execution_json),
                    evidence=row_selector("ledger_rows", row_index, "experiment_id"),
                )
            ledger_path = str(row.get("ledger") or "").strip()
            if ledger_path:
                add_edge(
                    edges,
                    method_selection_alpha_expansion_execution_id,
                    "report:method_selection_alpha_expansion_batch",
                    "DERIVED_FROM",
                    evidence_path=str(method_selection_alpha_expansion_execution_json),
                    evidence=row_selector("ledger_rows", row_index, "ledger"),
                )

    method_selection_inferential_md = (
        method_selection_inferential_json.with_suffix(".md")
    )
    if method_selection_inferential_json.exists():
        method_selection_inferential_id = (
            "report:method_selection_inferential_audit"
        )
        add_node(
            nodes,
            method_selection_inferential_id,
            "report",
            path=(
                str(method_selection_inferential_md)
                if method_selection_inferential_md.exists()
                else None
            ),
            json_path=str(method_selection_inferential_json),
            summary="Inferential no-promotion method-selection audit quantifying uncertainty around the diagnostic CQR preference.",
        )
        add_edge(
            edges,
            method_selection_inferential_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        try:
            method_selection_inferential = json.loads(
                method_selection_inferential_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            method_selection_inferential = {}
        inferential_sources = (
            method_selection_inferential.get("source_artifacts") or {}
        )
        for source_key, source_report_id in (
            ("method_performance_synthesis", "report:method_performance_synthesis"),
            (
                "method_selection_candidate_audit",
                "report:method_selection_candidate_audit",
            ),
            (
                "method_selection_robustness_audit",
                "report:method_selection_robustness_audit",
            ),
            (
                "method_selection_post_selection_validation_results",
                "report:method_selection_post_selection_validation_results",
            ),
            (
                "main_result_candidate_bundle_results",
                "report:main_result_candidate_bundle_results",
            ),
            ("selection_multiplicity_protocol", "report:selection_multiplicity_protocol"),
            (
                "final_selection_claim_boundary",
                "report:final_selection_claim_boundary_audit",
            ),
        ):
            if inferential_sources.get(source_key):
                add_edge(
                    edges,
                    method_selection_inferential_id,
                    source_report_id,
                    "DERIVED_FROM",
                    evidence_path=str(method_selection_inferential_json),
                    evidence=f"$.source_artifacts.{source_key}",
                )
        inferential_summary = method_selection_inferential.get("summary") or {}
        for method_id in inferential_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                method_selection_inferential_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(method_selection_inferential_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for gate_key in (
            "final_method_model_selection_gate",
            "multiplicity_selection_record",
        ):
            add_edge(
                edges,
                claim_requirement_node_id(
                    "final_selection_and_fairness_claims_blocked",
                    gate_key,
                ),
                method_selection_inferential_id,
                "SUPPORTED_BY",
                evidence_path=str(method_selection_inferential_json),
                evidence="$.summary",
                provenance_mode="method_selection_inferential_no_claim_support",
            )

    main_result_candidate_bundle_plan_md = (
        main_result_candidate_bundle_plan_json.with_suffix(".md")
    )
    if main_result_candidate_bundle_plan_json.exists():
        main_result_candidate_bundle_plan_id = (
            "report:main_result_candidate_bundle_plan"
        )
        add_node(
            nodes,
            main_result_candidate_bundle_plan_id,
            "report",
            path=(
                str(main_result_candidate_bundle_plan_md)
                if main_result_candidate_bundle_plan_md.exists()
                else None
            ),
            json_path=str(main_result_candidate_bundle_plan_json),
            summary="Executable fresh-seed candidate bundle plan for future main-result rows without promoting final claims.",
        )
        add_edge(
            edges,
            main_result_candidate_bundle_plan_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        try:
            main_result_candidate_bundle_plan = json.loads(
                main_result_candidate_bundle_plan_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            main_result_candidate_bundle_plan = {}
        for source_id, source_key in (
            (
                "report:method_selection_post_selection_validation_results",
                "method_selection_post_selection_validation_results",
            ),
            (
                "report:method_selection_post_selection_validation_batch",
                "method_selection_post_selection_validation_batch",
            ),
            (
                "report:dataset_specific_final_gate_audit",
                "dataset_specific_final_gate_audit",
            ),
            (
                "report:selection_multiplicity_evidence_record",
                "selection_multiplicity_evidence_record",
            ),
            ("report:manuscript_readiness_map", "paper_readiness_map"),
        ):
            add_edge(
                edges,
                main_result_candidate_bundle_plan_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(main_result_candidate_bundle_plan_json),
                evidence=f"$.source_artifacts.{source_key}",
            )
        plan_summary = main_result_candidate_bundle_plan.get("summary") or {}
        for method_id in plan_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                main_result_candidate_bundle_plan_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(main_result_candidate_bundle_plan_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for row_index, row in enumerate(
            main_result_candidate_bundle_plan.get("candidate_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    main_result_candidate_bundle_plan_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(main_result_candidate_bundle_plan_json),
                    evidence=row_selector("candidate_rows", row_index, "dataset_id"),
                )
            experiment_id = str(row.get("experiment_id") or "").strip()
            if experiment_id:
                add_edge(
                    edges,
                    main_result_candidate_bundle_plan_id,
                    f"config:{experiment_id}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(main_result_candidate_bundle_plan_json),
                    evidence=row_selector("candidate_rows", row_index, "experiment_id"),
                )
            source_experiment_id = str(
                row.get("source_validation_experiment_id") or ""
            ).strip()
            if source_experiment_id:
                add_edge(
                    edges,
                    main_result_candidate_bundle_plan_id,
                    f"config:{source_experiment_id}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(main_result_candidate_bundle_plan_json),
                    evidence=row_selector(
                        "candidate_rows",
                        row_index,
                        "source_validation_experiment_id",
                    ),
                )

    main_result_candidate_bundle_results_md = (
        main_result_candidate_bundle_results_json.with_suffix(".md")
    )
    if main_result_candidate_bundle_results_json.exists():
        main_result_candidate_bundle_results_id = (
            "report:main_result_candidate_bundle_results"
        )
        add_node(
            nodes,
            main_result_candidate_bundle_results_id,
            "report",
            path=(
                str(main_result_candidate_bundle_results_md)
                if main_result_candidate_bundle_results_md.exists()
                else None
            ),
            json_path=str(main_result_candidate_bundle_results_json),
            summary="Executed fresh-seed main-result candidate bundle result summary with diagnostic rankings and pathology flags, without final promotion claims.",
        )
        add_edge(
            edges,
            main_result_candidate_bundle_results_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        add_edge(
            edges,
            main_result_candidate_bundle_results_id,
            "report:main_result_candidate_bundle_plan",
            "DERIVED_FROM",
            evidence_path=str(main_result_candidate_bundle_results_json),
            evidence="$.source_artifacts.main_result_candidate_bundle_plan",
        )
        try:
            main_result_candidate_bundle_results = json.loads(
                main_result_candidate_bundle_results_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            main_result_candidate_bundle_results = {}
        result_summary = main_result_candidate_bundle_results.get("summary") or {}
        for method_id in result_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                main_result_candidate_bundle_results_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(main_result_candidate_bundle_results_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for row_index, row in enumerate(
            main_result_candidate_bundle_results.get("dataset_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    main_result_candidate_bundle_results_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(main_result_candidate_bundle_results_json),
                    evidence=row_selector("dataset_rows", row_index, "dataset_id"),
                )
            config_path = Path(str(row.get("config_path") or ""))
            if config_path.exists():
                try:
                    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                except yaml.YAMLError:
                    config = {}
                experiment_id = str(config.get("experiment_id") or "").strip()
                if experiment_id:
                    add_edge(
                        edges,
                        main_result_candidate_bundle_results_id,
                        f"config:{experiment_id}",
                        "SUMMARIZES_CONFIG",
                        evidence_path=str(main_result_candidate_bundle_results_json),
                        evidence=row_selector(
                            "dataset_rows", row_index, "config_path"
                        ),
                    )

    main_result_candidate_post_run_closure_md = (
        main_result_candidate_post_run_closure_json.with_suffix(".md")
    )
    if main_result_candidate_post_run_closure_json.exists():
        main_result_candidate_post_run_closure_id = (
            "report:main_result_candidate_post_run_closure_audit"
        )
        add_node(
            nodes,
            main_result_candidate_post_run_closure_id,
            "report",
            path=(
                str(main_result_candidate_post_run_closure_md)
                if main_result_candidate_post_run_closure_md.exists()
                else None
            ),
            json_path=str(main_result_candidate_post_run_closure_json),
            summary="Post-run closure audit for executed main-result candidate bundles, tracking completed ledgers, pilot summaries, split profiles, missing sidecars, and blocked promotion gates.",
        )
        add_edge(
            edges,
            main_result_candidate_post_run_closure_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, source_key in (
            (
                "report:main_result_candidate_bundle_plan",
                "main_result_candidate_bundle_plan",
            ),
            (
                "report:main_result_candidate_bundle_results",
                "main_result_candidate_bundle_results",
            ),
            ("report:manuscript_readiness_map", "paper_readiness_map"),
            ("catalog:knowledge_graph", "knowledge_graph"),
            ("catalog:manuscript_bundle_index", "manuscript_bundle_index"),
        ):
            add_edge(
                edges,
                main_result_candidate_post_run_closure_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(main_result_candidate_post_run_closure_json),
                evidence=f"$.source_artifacts.{source_key}",
            )
        try:
            main_result_candidate_post_run_closure = json.loads(
                main_result_candidate_post_run_closure_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            main_result_candidate_post_run_closure = {}
        for row_index, row in enumerate(
            main_result_candidate_post_run_closure.get("dataset_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    main_result_candidate_post_run_closure_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(main_result_candidate_post_run_closure_json),
                    evidence=row_selector("dataset_rows", row_index, "dataset_id"),
                )
            config_path = Path(str(row.get("config_path") or ""))
            if config_path.exists():
                try:
                    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                except yaml.YAMLError:
                    config = {}
                experiment_id = str(config.get("experiment_id") or "").strip()
                if experiment_id:
                    add_edge(
                        edges,
                        main_result_candidate_post_run_closure_id,
                        f"config:{experiment_id}",
                        "SUMMARIZES_CONFIG",
                        evidence_path=str(main_result_candidate_post_run_closure_json),
                        evidence=row_selector(
                            "dataset_rows", row_index, "config_path"
                        ),
                    )

    retrospective_controls_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "retrospective_methodology_controls.json"
    )
    retrospective_controls_md = retrospective_controls_json.with_suffix(".md")
    if retrospective_controls_json.exists():
        retrospective_controls_id = "report:retrospective_methodology_controls"
        add_node(
            nodes,
            retrospective_controls_id,
            "report",
            path=(
                str(retrospective_controls_md)
                if retrospective_controls_md.exists()
                else None
            ),
            json_path=str(retrospective_controls_json),
            summary="Retrospective scientific-control dashboard summarizing leakage, split, endpoint, metadata, runner, and claim-boundary controls.",
        )
        add_edge(
            edges, retrospective_controls_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        if cross_run_integrity_json.exists():
            add_edge(
                edges,
                retrospective_controls_id,
                "report:cross_run_integrity_audit",
                "DERIVED_FROM",
            )
        try:
            retrospective_controls = json.loads(
                retrospective_controls_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            retrospective_controls = {}
        for item in retrospective_controls.get("controls", []) or []:
            control_id = item.get("control_id")
            if not control_id:
                continue
            node_id = f"methodology_control:{control_id}"
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=str(control_id),
                status=item.get("status"),
                severity=item.get("severity"),
                summary=(
                    f"Retrospective methodology control `{control_id}` "
                    f"with status {item.get('status')}."
                ),
            )
            add_edge(edges, retrospective_controls_id, node_id, "SUMMARIZES_CONTROL")

    remediation_backlog_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "integrity_remediation_backlog.json"
    )
    retrospective_quality_gate_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "retrospective_quality_gate.json"
    )
    manuscript_manifest_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "manuscript_manifest_completeness_audit.json"
    )
    dataset_specific_final_gate_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "dataset_specific_final_gate_audit.json"
    )
    dataset_final_gate_remediation_plan_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "dataset_final_gate_remediation_plan.json"
    )
    dataset_final_gate_post_selection_bridge_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "dataset_final_gate_post_selection_validation_bridge.json"
    )
    dataset_final_gate_post_selection_bridge_results_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "dataset_final_gate_post_selection_validation_bridge_results.json"
    )
    manuscript_readiness_map_json = Path(
        "experiments/regression/manuscript/paper_readiness_map.json"
    )
    paper_gate_closure_map_json = Path(
        "experiments/regression/manuscript/paper_gate_closure_map.json"
    )
    paper_gate_execution_plan_json = Path(
        "experiments/regression/manuscript/paper_gate_closure_execution_plan.json"
    )
    paper_gate_protocol_design_json = Path(
        "experiments/regression/manuscript/paper_gate_protocol_design_bundle.json"
    )
    fairness_sampling_weight_policy_json = Path(
        "experiments/regression/manuscript/fairness_sampling_weight_policy.json"
    )
    fairness_group_diagnostic_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "fairness_group_diagnostic_audit.json"
    )
    fairness_group_multiplicity_scope_json = Path(
        "experiments/regression/manuscript/fairness_group_multiplicity_scope.json"
    )
    goal_completion_audit_json = Path(
        "experiments/regression/manuscript/goal_completion_audit.json"
    )
    post_experiment_publication_activation_json = Path(
        "experiments/regression/manuscript/"
        "post_experiment_publication_activation_audit.json"
    )
    publication_preparation_packets_json = Path(
        "experiments/regression/manuscript/publication_preparation_packets.json"
    )
    reviewer_design_brief_json = Path(
        "experiments/regression/manuscript/reviewer_design_brief.json"
    )
    visual_table_audit_plan_json = Path(
        "experiments/regression/manuscript/visual_table_audit_plan.json"
    )
    visual_table_audit_report_json = Path(
        "experiments/regression/manuscript/visual_table_audit_report.json"
    )
    visual_table_inventory_json = Path(
        "experiments/regression/manuscript/visual_table_inventory.json"
    )
    visual_table_iteration_register_json = Path(
        "experiments/regression/manuscript/visual_table_iteration_register.json"
    )
    kg_navigation_usability_audit_json = Path(
        "experiments/regression/manuscript/kg_navigation_usability_audit.json"
    )
    visual_table_render_candidate_audit_json = Path(
        "experiments/regression/manuscript/"
        "visual_table_render_candidate_audit.json"
    )
    visual_table_render_candidate_inventory_json = Path(
        "experiments/regression/manuscript/"
        "visual_table_render_candidate_inventory.json"
    )
    visual_table_layout_quality_audit_json = Path(
        "experiments/regression/manuscript/visual_table_layout_quality_audit.json"
    )
    publication_retention_readiness_audit_json = Path(
        "experiments/regression/manuscript/"
        "publication_retention_readiness_audit.json"
    )
    final_publication_visual_auditor_readiness_json = Path(
        "experiments/regression/manuscript/"
        "final_publication_visual_auditor_readiness.json"
    )
    article_supplement_retention_recommendation_matrix_json = Path(
        "experiments/regression/manuscript/"
        "article_supplement_retention_recommendation_matrix.json"
    )
    article_supplement_blueprint_alignment_json = Path(
        "experiments/regression/manuscript/"
        "article_supplement_blueprint_alignment.json"
    )
    publication_release_gap_register_json = Path(
        "experiments/regression/manuscript/"
        "publication_release_gap_register.json"
    )
    individual_experiment_report_blueprint_json = Path(
        "experiments/regression/manuscript/"
        "individual_experiment_report_blueprint.json"
    )
    claim_safe_result_extraction_matrix_json = Path(
        "experiments/regression/manuscript/"
        "claim_safe_result_extraction_matrix.json"
    )
    manuscript_section_evidence_packet_json = Path(
        "experiments/regression/manuscript/"
        "manuscript_section_evidence_packet.json"
    )
    section_claim_boundary_audit_json = Path(
        "experiments/regression/manuscript/section_claim_boundary_audit.json"
    )
    article_supplement_kg_navigation_index_json = Path(
        "experiments/regression/manuscript/"
        "article_supplement_kg_navigation_index.json"
    )
    publication_phase_progress_reconciliation_json = Path(
        "experiments/regression/manuscript/"
        "publication_phase_progress_reconciliation_audit.json"
    )
    scientific_neutrality_interpretation_lock_json = Path(
        "experiments/regression/manuscript/"
        "scientific_neutrality_interpretation_lock.json"
    )
    final_publication_output_authorization_protocol_json = Path(
        "experiments/regression/manuscript/"
        "final_publication_output_authorization_protocol.json"
    )
    publication_authoring_decision_record_json = Path(
        "experiments/regression/manuscript/"
        "publication_authoring_decision_record.json"
    )
    publication_claim_evidence_verification_matrix_json = Path(
        "experiments/regression/manuscript/"
        "publication_claim_evidence_verification_matrix.json"
    )
    publication_exemplar_review_json = Path(
        "experiments/regression/manuscript/publication_exemplar_review.json"
    )
    reader_method_primer_citation_map_json = Path(
        "experiments/regression/manuscript/"
        "reader_method_primer_citation_map.json"
    )
    publication_citation_registry_json = Path(
        "experiments/regression/manuscript/publication_citation_registry.json"
    )
    reader_primer_section_alignment_json = Path(
        "experiments/regression/manuscript/reader_primer_section_alignment.json"
    )
    manuscript_claim_citation_readiness_audit_json = Path(
        "experiments/regression/manuscript/"
        "manuscript_claim_citation_readiness_audit.json"
    )
    neutral_publication_release_cut_decision_json = Path(
        "experiments/regression/manuscript/"
        "neutral_publication_release_cut_decision.json"
    )
    private_latex_html_review_outputs_manifest_json = Path(
        "experiments/regression/manuscript/"
        "private_latex_html_review_outputs_manifest.json"
    )
    private_latex_html_review_output_audit_json = Path(
        "experiments/regression/manuscript/private_latex_html_review_output_audit.json"
    )
    private_sterile_publication_package_manifest_json = Path(
        "experiments/regression/manuscript/"
        "private_sterile_publication_package_manifest.json"
    )
    private_publication_repository_remote_audit_json = Path(
        "experiments/regression/manuscript/"
        "private_publication_repository_remote_audit.json"
    )
    individual_experiment_report_draft_json = Path(
        "experiments/regression/manuscript/individual_experiment_report_draft.json"
    )
    main_article_draft_json = Path(
        "experiments/regression/manuscript/main_article_draft.json"
    )
    supplementary_document_draft_json = Path(
        "experiments/regression/manuscript/supplementary_document_draft.json"
    )
    sterile_repository_readme_draft_json = Path(
        "experiments/regression/manuscript/sterile_repository_readme_draft.json"
    )
    sterile_repository_staging_manifest_json = Path(
        "experiments/regression/manuscript/"
        "sterile_repository_staging_manifest.json"
    )
    neutral_result_ledger_json = Path(
        "experiments/regression/manuscript/neutral_result_ledger.json"
    )
    article_supplement_kg_triptych_decision_json = Path(
        "experiments/regression/manuscript/"
        "article_supplement_kg_triptych_decision.json"
    )
    selection_multiplicity_protocol_json = Path(
        "experiments/regression/manuscript/selection_multiplicity_protocol.json"
    )
    selection_multiplicity_evidence_record_json = Path(
        "experiments/regression/manuscript/"
        "selection_multiplicity_evidence_record.json"
    )
    bounded_support_protocol_json = Path(
        "experiments/regression/manuscript/bounded_support_protocol.json"
    )
    target_domain_provenance_json = Path(
        "experiments/regression/catalogs/target_domain_provenance.json"
    )
    bounded_support_posthandling_json = Path(
        "experiments/regression/manuscript/bounded_support_posthandling_validation.json"
    )
    bounded_support_dataset_audit_json = Path(
        "experiments/regression/manuscript/bounded_support_dataset_audit.json"
    )
    bounded_support_endpoint_closure_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "bounded_support_endpoint_closure_audit.json"
    )
    bounded_support_positive_validation_json = Path(
        "experiments/regression/manuscript/"
        "bounded_support_positive_validation_protocol.json"
    )
    fairness_population_readiness_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "fairness_population_readiness_audit.json"
    )
    graph_artifact_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "graph_artifact_readiness_audit.json"
    )
    final_selection_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "final_selection_claim_boundary_audit.json"
    )
    venn_abers_validation_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_validation_readiness_audit.json"
    )
    venn_abers_grid_ivapd_protocol_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_grid_ivapd_validation_protocol.json"
    )
    venn_abers_grid_expansion_plan_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_grid_expansion_plan.json"
    )
    venn_abers_grid_failure_modes_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_grid_failure_mode_decomposition.json"
    )
    venn_abers_claim_gate_matrix_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_claim_gate_matrix.json"
    )
    venn_abers_negative_disposition_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_negative_evidence_disposition_audit.json"
    )
    venn_abers_grid_expansion_batch_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "venn_abers_grid_expansion_batch.json"
    )
    publication_methodology_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "publication_methodology_audit.json"
    )
    neutral_reporting_language_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "neutral_reporting_language_audit.json"
    )
    neutral_experiment_closure_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "neutral_experiment_closure_audit.json"
    )
    method_literature_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "method_literature_coverage_audit.json"
    )
    duplicate_closure_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "duplicate_sensitivity_closure_audit.json"
    )
    duplicate_quarantine_audit_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "duplicate_content_quarantine_audit.json"
    )
    knowledge_graph_quality_json = Path(
        "experiments/regression/reports/knowledge_graph_quality/quality_summary.json"
    )
    kg_publication_quality_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "kg_publication_quality_audit.json"
    )
    scientific_review_register_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "scientific_review_finding_register.json"
    )
    manuscript_manifest_audit_md = manuscript_manifest_audit_json.with_suffix(".md")
    if manuscript_manifest_audit_json.exists():
        manuscript_manifest_audit_id = "report:manuscript_manifest_completeness_audit"
        add_node(
            nodes,
            manuscript_manifest_audit_id,
            "report",
            path=(
                str(manuscript_manifest_audit_md)
                if manuscript_manifest_audit_md.exists()
                else None
            ),
            json_path=str(manuscript_manifest_audit_json),
            summary="Audit of manuscript-facing publication-readiness manifest completeness and bundle-index alignment.",
        )
        add_edge(
            edges,
            manuscript_manifest_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        manuscript_bundle_index_id = "catalog:manuscript_bundle_index"
        if manuscript_bundle_index_id in nodes:
            add_edge(
                edges,
                manuscript_manifest_audit_id,
                manuscript_bundle_index_id,
                "DERIVED_FROM",
            )
        schema_id = "catalog:manuscript_evidence_manifest_schema"
        if schema_id in nodes:
            add_edge(
                edges,
                manuscript_manifest_audit_id,
                schema_id,
                "USES_SCHEMA",
            )
    dataset_specific_final_gate_audit_md = (
        dataset_specific_final_gate_audit_json.with_suffix(".md")
    )
    if dataset_specific_final_gate_audit_json.exists():
        dataset_specific_final_gate_audit_id = (
            "report:dataset_specific_final_gate_audit"
        )
        add_node(
            nodes,
            dataset_specific_final_gate_audit_id,
            "report",
            path=(
                str(dataset_specific_final_gate_audit_md)
                if dataset_specific_final_gate_audit_md.exists()
                else None
            ),
            json_path=str(dataset_specific_final_gate_audit_json),
            summary="Audit decomposing dataset-specific final-result gate readiness across manifested robustness bundles without promoting a final dataset.",
        )
        add_edge(
            edges,
            dataset_specific_final_gate_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, source_key in (
            ("catalog:manuscript_bundle_index", "manuscript_bundle_index"),
            ("catalog:manuscript_bundle_eligibility_matrix", "bundle_eligibility_matrix"),
            (
                "report:manuscript_manifest_completeness_audit",
                "manuscript_manifest_completeness_audit",
            ),
            ("report:bounded_support_dataset_audit", "bounded_support_dataset_audit"),
            (
                "report:fairness_population_readiness_audit",
                "fairness_population_readiness_audit",
            ),
            (
                "report:final_selection_claim_boundary_audit",
                "final_selection_claim_boundary_audit",
            ),
            ("report:manuscript_readiness_map", "paper_readiness_map"),
        ):
            add_edge(
                edges,
                dataset_specific_final_gate_audit_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(dataset_specific_final_gate_audit_json),
                evidence=f"$.sources.{source_key}",
            )
        try:
            dataset_specific_final_gate_audit = json.loads(
                dataset_specific_final_gate_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            dataset_specific_final_gate_audit = {}
        for row_index, row in enumerate(
            dataset_specific_final_gate_audit.get("dataset_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    dataset_specific_final_gate_audit_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(dataset_specific_final_gate_audit_json),
                    evidence=row_selector("dataset_rows", row_index, "dataset_id"),
                )
        for row_index, row in enumerate(
            dataset_specific_final_gate_audit.get("bundle_rows") or []
        ):
            manifest_path = row.get("manifest_path")
            if manifest_path:
                manifest_id = f"manifest:{Path(str(manifest_path)).parent.name}:publication_readiness"
                add_edge(
                    edges,
                    dataset_specific_final_gate_audit_id,
                    manifest_id,
                    "SUMMARIZES_MANIFEST",
                    evidence_path=str(dataset_specific_final_gate_audit_json),
                    evidence=row_selector("bundle_rows", row_index, "manifest_path"),
                )
    dataset_final_gate_remediation_plan_md = (
        dataset_final_gate_remediation_plan_json.with_suffix(".md")
    )
    dataset_final_gate_post_selection_bridge_md = (
        dataset_final_gate_post_selection_bridge_json.with_suffix(".md")
    )
    if dataset_final_gate_post_selection_bridge_json.exists():
        dataset_final_gate_post_selection_bridge_id = (
            "report:dataset_final_gate_post_selection_validation_bridge"
        )
        add_node(
            nodes,
            dataset_final_gate_post_selection_bridge_id,
            "report",
            path=(
                str(dataset_final_gate_post_selection_bridge_md)
                if dataset_final_gate_post_selection_bridge_md.exists()
                else None
            ),
            json_path=str(dataset_final_gate_post_selection_bridge_json),
            summary="UCI Wine post-selection validation bridge work queue linking the dataset final-gate remediation plan to an executable validation config without final claims.",
        )
        add_edge(
            edges,
            dataset_final_gate_post_selection_bridge_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        try:
            dataset_final_gate_post_selection_bridge = json.loads(
                dataset_final_gate_post_selection_bridge_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            dataset_final_gate_post_selection_bridge = {}
        bridge_sources = (
            dataset_final_gate_post_selection_bridge.get("source_artifacts") or {}
        )
        for source_key, source_report_id in (
            (
                "dataset_final_gate_remediation_plan",
                "report:dataset_final_gate_remediation_plan",
            ),
            (
                "source_model_family_sweep_report",
                "report:model_family_sweep_uci_wine_quality_duplicate_sensitivity",
            ),
            (
                "source_feature_leakage_audit",
                "report:model_family_sweep_uci_wine_quality_duplicate_sensitivity:feature_leakage_audit",
            ),
        ):
            if bridge_sources.get(source_key):
                add_edge(
                    edges,
                    dataset_final_gate_post_selection_bridge_id,
                    source_report_id,
                    "DERIVED_FROM",
                    evidence_path=str(dataset_final_gate_post_selection_bridge_json),
                    evidence=f"$.source_artifacts.{source_key}",
                )
        bridge_summary = dataset_final_gate_post_selection_bridge.get("summary") or {}
        for method_id in bridge_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                dataset_final_gate_post_selection_bridge_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(dataset_final_gate_post_selection_bridge_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for row_index, row in enumerate(
            dataset_final_gate_post_selection_bridge.get("generated_configs") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    dataset_final_gate_post_selection_bridge_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(dataset_final_gate_post_selection_bridge_json),
                    evidence=row_selector("generated_configs", row_index, "dataset_id"),
                )
            experiment_id = str(row.get("experiment_id") or "").strip()
            if experiment_id:
                add_edge(
                    edges,
                    dataset_final_gate_post_selection_bridge_id,
                    f"config:{experiment_id}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(dataset_final_gate_post_selection_bridge_json),
                    evidence=row_selector(
                        "generated_configs", row_index, "experiment_id"
                    ),
                )
            source_config = str(
                row.get("source_model_family_sweep_experiment_id") or ""
            ).strip()
            if source_config:
                add_edge(
                    edges,
                    dataset_final_gate_post_selection_bridge_id,
                    f"config:{source_config}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(dataset_final_gate_post_selection_bridge_json),
                    evidence=row_selector(
                        "generated_configs",
                        row_index,
                        "source_model_family_sweep_experiment_id",
                    ),
                )
        for gate_id in (
            "dataset_specific_final_gates",
            "final_method_model_selection_gate",
        ):
            add_edge(
                edges,
                f"paper_gate:{gate_id}",
                dataset_final_gate_post_selection_bridge_id,
                "DERIVED_FROM",
                evidence_path=str(dataset_final_gate_post_selection_bridge_json),
                evidence="$.summary.claim_status",
            )
    dataset_final_gate_post_selection_bridge_results_md = (
        dataset_final_gate_post_selection_bridge_results_json.with_suffix(".md")
    )
    if dataset_final_gate_post_selection_bridge_results_json.exists():
        dataset_final_gate_post_selection_bridge_results_id = (
            "report:dataset_final_gate_post_selection_validation_bridge_results"
        )
        add_node(
            nodes,
            dataset_final_gate_post_selection_bridge_results_id,
            "report",
            path=(
                str(dataset_final_gate_post_selection_bridge_results_md)
                if dataset_final_gate_post_selection_bridge_results_md.exists()
                else None
            ),
            json_path=str(dataset_final_gate_post_selection_bridge_results_json),
            summary="Executed UCI Wine post-selection validation bridge result audit summarizing completed CQR, CV+, and Mondrian_abs rows without final claims.",
        )
        add_edge(
            edges,
            dataset_final_gate_post_selection_bridge_results_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        try:
            dataset_final_gate_post_selection_bridge_results = json.loads(
                dataset_final_gate_post_selection_bridge_results_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            dataset_final_gate_post_selection_bridge_results = {}
        bridge_result_sources = (
            dataset_final_gate_post_selection_bridge_results.get("source_artifacts")
            or {}
        )
        if bridge_result_sources.get(
            "dataset_final_gate_post_selection_validation_bridge"
        ):
            add_edge(
                edges,
                dataset_final_gate_post_selection_bridge_results_id,
                "report:dataset_final_gate_post_selection_validation_bridge",
                "DERIVED_FROM",
                evidence_path=str(dataset_final_gate_post_selection_bridge_results_json),
                evidence="$.source_artifacts.dataset_final_gate_post_selection_validation_bridge",
            )
        bridge_result_summary = (
            dataset_final_gate_post_selection_bridge_results.get("summary") or {}
        )
        for method_id in bridge_result_summary.get("candidate_methods") or []:
            method_id = str(method_id).strip()
            if not method_id:
                continue
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                dataset_final_gate_post_selection_bridge_results_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(dataset_final_gate_post_selection_bridge_results_json),
                evidence=(
                    "$.summary.candidate_methods[?(@ == "
                    f"{json.dumps(method_id, sort_keys=True)})]"
                ),
            )
        for row_index, row in enumerate(
            dataset_final_gate_post_selection_bridge_results.get("dataset_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    dataset_final_gate_post_selection_bridge_results_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(dataset_final_gate_post_selection_bridge_results_json),
                    evidence=row_selector("dataset_rows", row_index, "dataset_id"),
                )
            experiment_id = str(row.get("experiment_id") or "").strip()
            if experiment_id:
                add_edge(
                    edges,
                    dataset_final_gate_post_selection_bridge_results_id,
                    f"config:{experiment_id}",
                    "SUMMARIZES_CONFIG",
                    evidence_path=str(dataset_final_gate_post_selection_bridge_results_json),
                    evidence=row_selector("dataset_rows", row_index, "experiment_id"),
                )
        for gate_id in (
            "dataset_specific_final_gates",
            "final_method_model_selection_gate",
        ):
            add_edge(
                edges,
                f"paper_gate:{gate_id}",
                dataset_final_gate_post_selection_bridge_results_id,
                "DERIVED_FROM",
                evidence_path=str(dataset_final_gate_post_selection_bridge_results_json),
                evidence="$.summary.claim_status",
            )
    if dataset_final_gate_remediation_plan_json.exists():
        dataset_final_gate_remediation_plan_id = (
            "report:dataset_final_gate_remediation_plan"
        )
        try:
            dataset_final_gate_remediation_plan = json.loads(
                dataset_final_gate_remediation_plan_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            dataset_final_gate_remediation_plan = {}
        remediation_summary = (
            dataset_final_gate_remediation_plan.get("summary")
            if isinstance(dataset_final_gate_remediation_plan, dict)
            else {}
        )
        if not isinstance(remediation_summary, dict):
            remediation_summary = {}
        remediation_summary_text = (
            "Actionable remediation plan for closing dataset-specific final gates "
            "without promoting final claims."
        )
        endpoint_blocked_datasets = remediation_summary.get(
            "bounded_support_endpoint_blocked_or_incomplete_dataset_count"
        )
        global_no_claim_datasets = remediation_summary.get(
            "bounded_support_global_no_claim_dataset_count"
        )
        endpoint_policy_closed_datasets = remediation_summary.get(
            "bounded_support_endpoint_policy_closed_dataset_count"
        )
        endpoint_local_remediation_datasets = remediation_summary.get(
            "bounded_support_endpoint_requiring_local_remediation_dataset_count"
        )
        executable_actions = remediation_summary.get("executable_action_count")
        if all(
            value is not None
            for value in (
                endpoint_blocked_datasets,
                global_no_claim_datasets,
                endpoint_policy_closed_datasets,
                endpoint_local_remediation_datasets,
                executable_actions,
            )
        ):
            remediation_summary_text = (
                f"{remediation_summary_text} Bounded-support remediation split: "
                f"{endpoint_blocked_datasets} dataset(s) with endpoint "
                f"blocked/incomplete bundles, {endpoint_policy_closed_datasets} "
                "dataset(s) with endpoint-policy closure, "
                f"{endpoint_local_remediation_datasets} dataset(s) requiring local "
                f"endpoint remediation, {global_no_claim_datasets} dataset(s) "
                f"under the global no-claim boundary, and {executable_actions} "
                "executable action records."
            )
        add_node(
            nodes,
            dataset_final_gate_remediation_plan_id,
            "report",
            path=(
                str(dataset_final_gate_remediation_plan_md)
                if dataset_final_gate_remediation_plan_md.exists()
                else None
            ),
            json_path=str(dataset_final_gate_remediation_plan_json),
            summary=remediation_summary_text,
        )
        add_edge(
            edges,
            dataset_final_gate_remediation_plan_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, source_key in (
            (
                "report:dataset_specific_final_gate_audit",
                "dataset_specific_final_gate_audit",
            ),
            (
                "report:method_selection_post_selection_validation_results",
                "method_selection_post_selection_validation_results",
            ),
            (
                "report:dataset_final_gate_post_selection_validation_bridge",
                "dataset_final_gate_post_selection_validation_bridge",
            ),
            (
                "report:dataset_final_gate_post_selection_validation_bridge_results",
                "dataset_final_gate_post_selection_validation_bridge_results",
            ),
            (
                "report:main_result_candidate_bundle_plan",
                "main_result_candidate_bundle_plan",
            ),
            (
                "report:main_result_candidate_bundle_results",
                "main_result_candidate_bundle_results",
            ),
            (
                "report:main_result_candidate_post_run_closure_audit",
                "main_result_candidate_post_run_closure_audit",
            ),
            ("report:bounded_support_dataset_audit", "bounded_support_dataset_audit"),
            (
                "report:bounded_support_endpoint_closure_audit",
                "bounded_support_endpoint_closure_audit",
            ),
            ("report:manuscript_readiness_map", "paper_readiness_map"),
        ):
            add_edge(
                edges,
                dataset_final_gate_remediation_plan_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(dataset_final_gate_remediation_plan_json),
                evidence=f"$.sources.{source_key}",
            )
        for row_index, row in enumerate(
            dataset_final_gate_remediation_plan.get("dataset_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    dataset_final_gate_remediation_plan_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(dataset_final_gate_remediation_plan_json),
                    evidence=row_selector("dataset_rows", row_index, "dataset_id"),
                )
            for gate_id in row.get("blocked_gate_ids") or []:
                gate_graph_id = f"paper_gate:{gate_id}"
                add_edge(
                    edges,
                    gate_graph_id,
                    dataset_final_gate_remediation_plan_id,
                    "DERIVED_FROM",
                    evidence_path=str(dataset_final_gate_remediation_plan_json),
                    evidence=row_selector(
                        "dataset_rows", row_index, "blocked_gate_ids"
                    ),
                )
    selection_multiplicity_protocol_md = (
        selection_multiplicity_protocol_json.with_suffix(".md")
    )
    if selection_multiplicity_protocol_json.exists():
        selection_multiplicity_protocol_id = "report:selection_multiplicity_protocol"
        add_node(
            nodes,
            selection_multiplicity_protocol_id,
            "report",
            path=(
                str(selection_multiplicity_protocol_md)
                if selection_multiplicity_protocol_md.exists()
                else None
            ),
            json_path=str(selection_multiplicity_protocol_json),
            summary="Protocol defining paper-facing model/method selection, multiplicity accounting, tie-break, and no-winner rules without selecting a final method.",
        )
        add_edge(
            edges,
            selection_multiplicity_protocol_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:selection_multiplicity_protocol",
            "catalog:publication_readiness_protocol",
            "catalog:manuscript_evidence_manifest_schema",
            "catalog:manuscript_bundle_index",
            "catalog:manuscript_evidence_view",
            "report:publication_methodology_audit",
            "report:final_selection_claim_boundary_audit",
        ):
            add_edge(
                edges,
                selection_multiplicity_protocol_id,
                source_id,
                "DERIVED_FROM",
            )
        try:
            selection_multiplicity_payload = json.loads(
                selection_multiplicity_protocol_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            selection_multiplicity_payload = {}
        summarized_manifest_ids: set[str] = set()
        for scope in selection_multiplicity_payload.get("ranking_scopes", []) or []:
            if not isinstance(scope, dict):
                continue
            manifest_path = scope.get("manifest_path")
            if not manifest_path:
                continue
            report_name = Path(str(manifest_path)).parent.name
            manifest_id = f"manifest:{report_name}:publication_readiness"
            summarized_manifest_ids.add(manifest_id)
            add_edge(
                edges,
                selection_multiplicity_protocol_id,
                manifest_id,
                "SUMMARIZES_MANIFEST",
                evidence_path=str(selection_multiplicity_protocol_json),
                evidence=json_array_selector(
                    "manifest_path",
                    manifest_path,
                    root="$.ranking_scopes",
                ),
                provenance_mode="selection_multiplicity_ranking_scope_manifest",
            )
        manuscript_bundle_index_path = Path(
            "experiments/regression/catalogs/manuscript_bundle_index.json"
        )
        if manuscript_bundle_index_path.exists():
            try:
                manuscript_bundle_index = json.loads(
                    manuscript_bundle_index_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError:
                manuscript_bundle_index = {}
            for bundle_index, bundle in enumerate(
                manuscript_bundle_index.get("bundles", []) or []
            ):
                if not isinstance(bundle, dict) or not bundle.get("manifest_path"):
                    continue
                manifest_path = str(bundle["manifest_path"])
                report_name = Path(manifest_path).parent.name
                manifest_id = f"manifest:{report_name}:publication_readiness"
                if manifest_id in summarized_manifest_ids:
                    continue
                summarized_manifest_ids.add(manifest_id)
                add_edge(
                    edges,
                    selection_multiplicity_protocol_id,
                    manifest_id,
                    "SUMMARIZES_MANIFEST",
                    evidence_path=str(manuscript_bundle_index_path),
                    evidence=row_selector("bundles", bundle_index, "manifest_path"),
                    provenance_mode="selection_multiplicity_bundle_index_manifest",
                )
    selection_multiplicity_evidence_record_md = (
        selection_multiplicity_evidence_record_json.with_suffix(".md")
    )
    if selection_multiplicity_evidence_record_json.exists():
        selection_multiplicity_evidence_record_id = (
            "report:selection_multiplicity_evidence_record"
        )
        try:
            selection_multiplicity_evidence_record = json.loads(
                selection_multiplicity_evidence_record_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            selection_multiplicity_evidence_record = {}
        evidence_summary = (
            selection_multiplicity_evidence_record.get("summary") or {}
        )
        add_node(
            nodes,
            selection_multiplicity_evidence_record_id,
            "report",
            path=(
                str(selection_multiplicity_evidence_record_md)
                if selection_multiplicity_evidence_record_md.exists()
                else None
            ),
            json_path=str(selection_multiplicity_evidence_record_json),
            summary=(
                "Paper-facing selection/multiplicity evidence record binding "
                "post-selection validation to the no-final-selection claim "
                f"boundary; diagnostic primary is "
                f"{evidence_summary.get('diagnostic_primary_method')}."
            ),
        )
        add_edge(
            edges,
            selection_multiplicity_evidence_record_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, source_key in (
            ("catalog:manuscript_evidence_manifest_schema", "manifest_schema"),
            (
                "report:selection_multiplicity_protocol",
                "selection_multiplicity_protocol",
            ),
            ("report:manuscript_readiness_map", "paper_readiness_map"),
            (
                "report:method_selection_candidate_audit",
                "method_selection_candidate_audit",
            ),
            (
                "report:method_selection_robustness_audit",
                "method_selection_robustness_audit",
            ),
            (
                "report:method_selection_post_selection_validation_results",
                "method_selection_post_selection_validation_results",
            ),
            (
                "report:final_selection_claim_boundary_audit",
                "final_selection_claim_boundary_audit",
            ),
            ("report:publication_methodology_audit", "publication_methodology_audit"),
        ):
            add_edge(
                edges,
                selection_multiplicity_evidence_record_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(selection_multiplicity_evidence_record_json),
                evidence=f"$.sources.{source_key}",
            )
        evidence_payload = (
            selection_multiplicity_evidence_record.get(
                "selection_multiplicity_evidence"
            )
            or {}
        )
        selection_records = evidence_payload.get("selection_records") or []
        candidate_methods = []
        for method_id in evidence_summary.get("diagnostic_winner_counts") or {}:
            candidate_methods.append(str(method_id))
        for record in selection_records:
            for method_id in record.get("candidate_methods") or []:
                method_id = str(method_id).strip()
                if method_id and method_id not in candidate_methods:
                    candidate_methods.append(method_id)
        for method_id in candidate_methods:
            method_graph_id = f"method:{method_id}"
            add_node(
                nodes,
                method_graph_id,
                "method",
                name=method_id,
                summary=f"Regression conformal method or configured method variant {method_id}.",
            )
            add_edge(
                edges,
                selection_multiplicity_evidence_record_id,
                method_graph_id,
                "EVALUATES_METHOD",
                evidence_path=str(selection_multiplicity_evidence_record_json),
                evidence=(
                    "$.selection_multiplicity_evidence.selection_records[0]"
                    f".candidate_methods[?(@ == {json.dumps(method_id)})]"
                ),
            )
        ranking_scope = (
            (evidence_payload.get("field_record") or {}).get("ranking_scope") or {}
        )
        for dataset_id in ranking_scope.get("datasets") or []:
            dataset_id = str(dataset_id).strip()
            if not dataset_id:
                continue
            add_edge(
                edges,
                selection_multiplicity_evidence_record_id,
                f"dataset:{dataset_id}",
                "SUMMARIZES_DATASET",
                evidence_path=str(selection_multiplicity_evidence_record_json),
                evidence=(
                    "$.selection_multiplicity_evidence.field_record."
                    "ranking_scope.datasets"
                    f"[?(@ == {json.dumps(dataset_id)})]"
                ),
            )
        for record in selection_records:
            for gate_id in record.get("blocking_gate_ids") or []:
                gate_id = str(gate_id).strip()
                if not gate_id:
                    continue
                add_edge(
                    edges,
                    selection_multiplicity_evidence_record_id,
                    f"paper_gate:{slug_fragment(gate_id)}",
                    "SUMMARIZES_CONTROL",
                    evidence_path=str(selection_multiplicity_evidence_record_json),
                    evidence=(
                        "$.selection_multiplicity_evidence.selection_records[0]"
                        f".blocking_gate_ids[?(@ == {json.dumps(gate_id)})]"
                    ),
                    provenance_mode="selection_multiplicity_blocking_gate_trace",
                )
    bounded_support_protocol_md = bounded_support_protocol_json.with_suffix(".md")
    if bounded_support_protocol_json.exists():
        bounded_support_protocol_id = "report:bounded_support_protocol"
        add_node(
            nodes,
            bounded_support_protocol_id,
            "report",
            path=(
                str(bounded_support_protocol_md)
                if bounded_support_protocol_md.exists()
                else None
            ),
            json_path=str(bounded_support_protocol_json),
            summary="Protocol defining target-domain and bounded-support evidence requirements without validating bounded support.",
        )
        add_edge(
            edges,
            bounded_support_protocol_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:bounded_support_protocol",
            "catalog:publication_readiness_protocol",
            "catalog:manuscript_evidence_manifest_schema",
            "catalog:manuscript_evidence_view",
            "report:publication_methodology_audit",
            "report:final_selection_claim_boundary_audit",
        ):
            add_edge(
                edges,
                bounded_support_protocol_id,
                source_id,
                "DERIVED_FROM",
            )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:endpoint_bounded_support_gate",
            bounded_support_protocol_id,
            "SUPPORTED_BY",
            evidence_path=str(bounded_support_protocol_json),
            evidence="$.summary",
        )
    target_domain_provenance_md = target_domain_provenance_json.with_suffix(".md")
    if target_domain_provenance_json.exists():
        target_domain_provenance_id = "report:target_domain_provenance"
        add_node(
            nodes,
            target_domain_provenance_id,
            "report",
            path=(
                str(target_domain_provenance_md)
                if target_domain_provenance_md.exists()
                else None
            ),
            json_path=str(target_domain_provenance_json),
            summary="Source-backed target-domain natural-bound provenance catalog for manuscript bounded-support audits.",
        )
        add_edge(
            edges,
            target_domain_provenance_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:target_domain_provenance",
            "catalog:source_registry",
            "catalog:bounded_support_protocol",
            "report:bounded_support_protocol",
        ):
            add_edge(
                edges,
                target_domain_provenance_id,
                source_id,
                "DERIVED_FROM",
            )
        try:
            target_domain_provenance = json.loads(
                target_domain_provenance_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            target_domain_provenance = {}
        for row in target_domain_provenance.get("rows", []) or []:
            dataset_id = row.get("dataset_id")
            if dataset_id:
                add_edge(
                    edges,
                    target_domain_provenance_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
    bounded_support_posthandling_md = bounded_support_posthandling_json.with_suffix(
        ".md"
    )
    if bounded_support_posthandling_json.exists():
        bounded_support_posthandling_id = (
            "report:bounded_support_posthandling_validation"
        )
        add_node(
            nodes,
            bounded_support_posthandling_id,
            "report",
            path=(
                str(bounded_support_posthandling_md)
                if bounded_support_posthandling_md.exists()
                else None
            ),
            json_path=str(bounded_support_posthandling_json),
            summary="Scoped bounded-support post-handling validation report with raw, clipped, and abstention policy metrics.",
        )
        add_edge(
            edges,
            bounded_support_posthandling_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:bounded_support_posthandling_validation",
            "catalog:target_domain_provenance",
            "report:target_domain_provenance",
            "catalog:bounded_support_protocol",
            "report:bounded_support_protocol",
        ):
            add_edge(
                edges,
                bounded_support_posthandling_id,
                source_id,
                "DERIVED_FROM",
            )
        try:
            bounded_support_posthandling = json.loads(
                bounded_support_posthandling_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            bounded_support_posthandling = {}
        for row in bounded_support_posthandling.get("rows", []) or []:
            dataset_id = row.get("dataset_id")
            if dataset_id:
                add_edge(
                    edges,
                    bounded_support_posthandling_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
    bounded_support_dataset_audit_md = bounded_support_dataset_audit_json.with_suffix(
        ".md"
    )
    if bounded_support_dataset_audit_json.exists():
        try:
            bounded_support_dataset = json.loads(
                bounded_support_dataset_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            bounded_support_dataset = {}
        bounded_support_dataset_summary = (
            bounded_support_dataset.get("summary")
            if isinstance(bounded_support_dataset, dict)
            else {}
        )
        if not isinstance(bounded_support_dataset_summary, dict):
            bounded_support_dataset_summary = {}
        endpoint_clean = bounded_support_dataset_summary.get(
            "endpoint_support_clean_bundle_count"
        )
        endpoint_not_applicable = bounded_support_dataset_summary.get(
            "endpoint_support_not_applicable_bundle_count"
        )
        endpoint_blocked = bounded_support_dataset_summary.get(
            "endpoint_support_blocked_or_incomplete_bundle_count"
        )
        bounded_ready = bounded_support_dataset_summary.get(
            "bounded_support_ready_bundle_count"
        )
        bounded_support_summary_text = (
            "Dataset-level bounded-support audit classifying manuscript bundle "
            "target domains, endpoint-domain blockers, and the no-claim "
            "boundary without validating bounded support."
        )
        if all(
            value is not None
            for value in (
                endpoint_clean,
                endpoint_not_applicable,
                endpoint_blocked,
                bounded_ready,
            )
        ):
            bounded_support_summary_text = (
                f"{bounded_support_summary_text} Endpoint support split: "
                f"{endpoint_clean} clean, {endpoint_not_applicable} not applicable, "
                f"{endpoint_blocked} blocked or incomplete; bounded-support-ready "
                f"bundles: {bounded_ready}."
            )
        bounded_support_dataset_audit_id = "report:bounded_support_dataset_audit"
        add_node(
            nodes,
            bounded_support_dataset_audit_id,
            "report",
            path=(
                str(bounded_support_dataset_audit_md)
                if bounded_support_dataset_audit_md.exists()
                else None
            ),
            json_path=str(bounded_support_dataset_audit_json),
            summary=bounded_support_summary_text,
        )
        add_edge(
            edges,
            bounded_support_dataset_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:bounded_support_dataset_audit",
            "catalog:bounded_support_protocol",
            "report:bounded_support_protocol",
            "catalog:target_domain_provenance",
            "report:target_domain_provenance",
            "catalog:bounded_support_posthandling_validation",
            "report:bounded_support_posthandling_validation",
            "catalog:manuscript_bundle_index",
            "catalog:manuscript_evidence_view",
            "report:final_selection_claim_boundary_audit",
        ):
            add_edge(
                edges,
                bounded_support_dataset_audit_id,
                source_id,
                "DERIVED_FROM",
            )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:endpoint_bounded_support_gate",
            bounded_support_dataset_audit_id,
            "SUPPORTED_BY",
            evidence_path=str(bounded_support_dataset_audit_json),
            evidence="$.summary",
        )
        for row in bounded_support_dataset.get("rows", []) or []:
            dataset_id = row.get("dataset_id")
            if dataset_id:
                add_edge(
                    edges,
                    bounded_support_dataset_audit_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            paired_dataset_id = row.get("paired_dataset_id")
            if paired_dataset_id:
                add_edge(
                    edges,
                    bounded_support_dataset_audit_id,
                    f"dataset:{paired_dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            endpoint_report_id = (row.get("endpoint_audit") or {}).get("report_id")
            if endpoint_report_id:
                add_edge(
                    edges,
                    bounded_support_dataset_audit_id,
                    str(endpoint_report_id),
                    "DERIVED_FROM",
                )
    bounded_support_endpoint_closure_md = (
        bounded_support_endpoint_closure_json.with_suffix(".md")
    )
    if bounded_support_endpoint_closure_json.exists():
        try:
            bounded_support_endpoint_closure = json.loads(
                bounded_support_endpoint_closure_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            bounded_support_endpoint_closure = {}
        closure_summary = bounded_support_endpoint_closure.get("summary") or {}
        closed_policy = closure_summary.get("closed_policy_bundle_count")
        open_backfill = closure_summary.get(
            "open_endpoint_count_backfill_bundle_count"
        )
        claim_ready = closure_summary.get(
            "bounded_support_validity_claim_ready_bundle_count"
        )
        closure_summary_text = (
            "Endpoint-domain closure audit separating measured raw endpoint "
            "excursions, clean/not-applicable endpoint hygiene, and count "
            "backfill gaps without promoting bounded-support validity."
        )
        if all(
            value is not None for value in (closed_policy, open_backfill, claim_ready)
        ):
            closure_summary_text = (
                f"{closure_summary_text} Current split: {closed_policy} closed "
                f"policy bundle(s), {open_backfill} endpoint-count backfill "
                f"bundle(s), and {claim_ready} bounded-support claim-ready "
                "bundle(s)."
            )
        bounded_support_endpoint_closure_id = (
            "report:bounded_support_endpoint_closure_audit"
        )
        add_node(
            nodes,
            bounded_support_endpoint_closure_id,
            "report",
            path=(
                str(bounded_support_endpoint_closure_md)
                if bounded_support_endpoint_closure_md.exists()
                else None
            ),
            json_path=str(bounded_support_endpoint_closure_json),
            summary=closure_summary_text,
        )
        add_edge(
            edges,
            bounded_support_endpoint_closure_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, source_key in (
            ("report:bounded_support_protocol", "bounded_support_protocol"),
            ("report:target_domain_provenance", "target_domain_provenance"),
            (
                "report:bounded_support_posthandling_validation",
                "bounded_support_posthandling_validation",
            ),
            ("report:bounded_support_dataset_audit", "bounded_support_dataset_audit"),
            ("report:manuscript_readiness_map", "paper_readiness_map"),
        ):
            add_edge(
                edges,
                bounded_support_endpoint_closure_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(bounded_support_endpoint_closure_json),
                evidence=f"$.sources.{source_key}",
            )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:endpoint_bounded_support_gate",
            bounded_support_endpoint_closure_id,
            "SUPPORTED_BY",
            evidence_path=str(bounded_support_endpoint_closure_json),
            evidence="$.summary",
        )
        add_edge(
            edges,
            "paper_gate:endpoint_bounded_support_gate",
            bounded_support_endpoint_closure_id,
            "DERIVED_FROM",
            artifact_path=str(bounded_support_endpoint_closure_json),
            evidence_path=str(manuscript_readiness_map_json),
            evidence=(
                "$.blocked_gates[?(@.gate_id == "
                '"endpoint_bounded_support_gate")].source_artifacts'
                f"[?(@ == {json.dumps(str(bounded_support_endpoint_closure_json))})]"
            ),
            provenance_mode="paper_gate_source_artifact_path_resolved",
        )
        for row_index, row in enumerate(
            bounded_support_endpoint_closure.get("dataset_rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if not dataset_id:
                continue
            add_edge(
                edges,
                bounded_support_endpoint_closure_id,
                f"dataset:{dataset_id}",
                "SUMMARIZES_DATASET",
                evidence_path=str(bounded_support_endpoint_closure_json),
                evidence=row_selector("dataset_rows", row_index, "dataset_id"),
            )
        for row_index, row in enumerate(
            bounded_support_endpoint_closure.get("rows") or []
        ):
            endpoint_report_id = str(row.get("endpoint_report_id") or "").strip()
            if endpoint_report_id:
                add_edge(
                    edges,
                    bounded_support_endpoint_closure_id,
                    endpoint_report_id,
                    "DERIVED_FROM",
                    evidence_path=str(bounded_support_endpoint_closure_json),
                    evidence=row_selector("rows", row_index, "endpoint_report_id"),
                )
    bounded_support_positive_validation_md = (
        bounded_support_positive_validation_json.with_suffix(".md")
    )
    if bounded_support_positive_validation_json.exists():
        try:
            bounded_support_positive_validation = json.loads(
                bounded_support_positive_validation_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            bounded_support_positive_validation = {}
        positive_summary = bounded_support_positive_validation.get("summary") or {}
        selected = positive_summary.get("selected_bundle_count")
        claim_ready = positive_summary.get("positive_claim_ready_bundle_count")
        acceptance_failed = positive_summary.get("positive_acceptance_failed_count")
        interval_missing = positive_summary.get(
            "interval_score_metrics_missing_bundle_count"
        )
        positive_summary_text = (
            "Bounded-support positive-validity protocol result preserving "
            "no-claim evidence instead of promoting bounded-support validity."
        )
        if all(
            value is not None
            for value in (selected, claim_ready, acceptance_failed, interval_missing)
        ):
            positive_summary_text = (
                f"{positive_summary_text} Current split: {selected} selected "
                f"bundle(s), {claim_ready} claim-ready bundle(s), "
                f"{acceptance_failed} failed positive acceptance criterion/criteria, "
                f"and {interval_missing} bundle(s) with missing interval-score "
                "metrics."
            )
        bounded_support_positive_validation_id = (
            "report:bounded_support_positive_validation_protocol"
        )
        add_node(
            nodes,
            bounded_support_positive_validation_id,
            "report",
            path=(
                str(bounded_support_positive_validation_md)
                if bounded_support_positive_validation_md.exists()
                else None
            ),
            json_path=str(bounded_support_positive_validation_json),
            summary=positive_summary_text,
        )
        add_edge(
            edges,
            bounded_support_positive_validation_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id, source_key in (
            ("catalog:bounded_support_positive_validation_protocol", "self"),
            ("report:bounded_support_protocol", "bounded_support_protocol"),
            ("report:bounded_support_dataset_audit", "bounded_support_dataset_audit"),
            (
                "report:bounded_support_posthandling_validation",
                "bounded_support_posthandling_validation",
            ),
            (
                "report:bounded_support_endpoint_closure_audit",
                "bounded_support_endpoint_closure",
            ),
            ("report:manuscript_readiness_map", "paper_readiness_map"),
        ):
            evidence = "$.summary" if source_key == "self" else f"$.sources.{source_key}"
            add_edge(
                edges,
                bounded_support_positive_validation_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(bounded_support_positive_validation_json),
                evidence=evidence,
            )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:endpoint_bounded_support_gate",
            bounded_support_positive_validation_id,
            "SUPPORTED_BY",
            evidence_path=str(bounded_support_positive_validation_json),
            evidence="$.summary",
        )
        add_edge(
            edges,
            "paper_gate:endpoint_bounded_support_gate",
            bounded_support_positive_validation_id,
            "DERIVED_FROM",
            artifact_path=str(bounded_support_positive_validation_json),
            evidence_path=str(manuscript_readiness_map_json),
            evidence=(
                "$.blocked_gates[?(@.gate_id == "
                '"endpoint_bounded_support_gate")].source_artifacts'
                f"[?(@ == {json.dumps(str(bounded_support_positive_validation_json))})]"
            ),
            provenance_mode="paper_gate_source_artifact_path_resolved",
        )
        for row_index, row in enumerate(
            bounded_support_positive_validation.get("rows") or []
        ):
            dataset_id = str(row.get("dataset_id") or "").strip()
            if dataset_id:
                add_edge(
                    edges,
                    bounded_support_positive_validation_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(bounded_support_positive_validation_json),
                    evidence=row_selector("rows", row_index, "dataset_id"),
                )
    fairness_population_readiness_md = fairness_population_readiness_json.with_suffix(
        ".md"
    )
    if fairness_population_readiness_json.exists():
        fairness_population_readiness_id = "report:fairness_population_readiness_audit"
        add_node(
            nodes,
            fairness_population_readiness_id,
            "report",
            path=(
                str(fairness_population_readiness_md)
                if fairness_population_readiness_md.exists()
                else None
            ),
            json_path=str(fairness_population_readiness_json),
            summary="Audit separating diagnostic group-stratified coverage from population, protected-class, legal, policy, clinical, or causal fairness claims.",
        )
        add_edge(
            edges,
            fairness_population_readiness_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:manuscript_claim_register",
            "catalog:manuscript_bundle_index",
            "catalog:manuscript_evidence_view",
            "catalog:publication_readiness_protocol",
            "report:final_selection_claim_boundary_audit",
        ):
            add_edge(
                edges,
                fairness_population_readiness_id,
                source_id,
                "DERIVED_FROM",
            )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:fairness_population_inference_gate",
            fairness_population_readiness_id,
            "SUPPORTED_BY",
            evidence_path=str(fairness_population_readiness_json),
            evidence="$.summary",
        )
        try:
            fairness_population_payload = json.loads(
                fairness_population_readiness_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            fairness_population_payload = {}
        for row_index, row in enumerate(
            fairness_population_payload.get("rows", []) or []
        ):
            if not isinstance(row, dict):
                continue
            dataset_id = row.get("dataset_id")
            if dataset_id:
                add_edge(
                    edges,
                    fairness_population_readiness_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(fairness_population_readiness_json),
                    evidence=row_selector("rows", row_index, "dataset_id"),
                )
    manuscript_readiness_map_md = manuscript_readiness_map_json.with_suffix(".md")
    if manuscript_readiness_map_json.exists():
        manuscript_readiness_map_id = "report:manuscript_readiness_map"
        add_node(
            nodes,
            manuscript_readiness_map_id,
            "report",
            path=(
                str(manuscript_readiness_map_md)
                if manuscript_readiness_map_md.exists()
                else None
            ),
            json_path=str(manuscript_readiness_map_json),
            summary="Paper-readiness map summarizing blocked final-claim gates, manuscript surfaces, and closure actions.",
        )
        add_edge(
            edges,
            manuscript_readiness_map_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:manuscript_paper_readiness_map",
            "catalog:selection_multiplicity_protocol",
            "report:selection_multiplicity_protocol",
            "catalog:bounded_support_protocol",
            "report:bounded_support_protocol",
            "catalog:bounded_support_dataset_audit",
            "report:bounded_support_dataset_audit",
            "catalog:target_domain_provenance",
            "report:target_domain_provenance",
            "catalog:bounded_support_posthandling_validation",
            "report:bounded_support_posthandling_validation",
            "catalog:bounded_support_positive_validation_protocol",
            "report:bounded_support_positive_validation_protocol",
            "catalog:publication_readiness_protocol",
            "catalog:post_experiment_publication_program",
            "catalog:manuscript_bundle_index",
            "catalog:manuscript_evidence_view",
            "report:method_selection_inferential_audit",
            "report:main_result_candidate_bundle_results",
            "report:main_result_candidate_post_run_closure_audit",
            "report:publication_methodology_audit",
            "report:final_selection_claim_boundary_audit",
            "report:fairness_population_readiness_audit",
            "report:venn_abers_validation_readiness_audit",
            "report:venn_abers_claim_gate_matrix",
        ):
            add_edge(
                edges,
                manuscript_readiness_map_id,
                source_id,
                "DERIVED_FROM",
            )
        try:
            readiness_map = json.loads(
                manuscript_readiness_map_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            readiness_map = {}
        path_index = build_node_path_index(nodes)
        for gate in readiness_map.get("blocked_gates", []) or []:
            if not isinstance(gate, dict) or not gate.get("gate_id"):
                continue
            gate_key = str(gate["gate_id"])
            gate_node_id = f"paper_gate:{slug_fragment(gate_key)}"
            add_node(
                nodes,
                gate_node_id,
                "paper_gate",
                gate_id=gate_key,
                status=gate.get("status"),
                paper_risk=gate.get("paper_risk"),
                closure_standard=gate.get("closure_standard"),
                next_actions=gate.get("next_actions"),
                source_artifacts=gate.get("source_artifacts"),
                summary=(
                    f"Paper gate `{gate_key}` has status {gate.get('status')}: "
                    f"{gate.get('paper_risk') or ''}"
                ).strip(),
            )
            add_edge(
                edges,
                manuscript_readiness_map_id,
                gate_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(manuscript_readiness_map_json),
                evidence=paper_gate_json_selector(gate_key),
                provenance_mode="paper_gate_summary_selector",
            )
            add_edge(
                edges,
                claim_requirement_node_id(
                    "final_selection_and_fairness_claims_blocked",
                    gate_key,
                ),
                gate_node_id,
                "BLOCKED_BY",
                evidence_path=str(manuscript_readiness_map_json),
                evidence=paper_gate_json_selector(gate_key),
                provenance_mode="paper_gate_claim_requirement_trace",
            )
            for artifact_path in gate.get("source_artifacts", []) or []:
                for source_node_id in artifact_support_node_ids(
                    nodes, path_index, artifact_path
                ):
                    add_edge(
                        edges,
                        gate_node_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(manuscript_readiness_map_json),
                        evidence=paper_gate_json_selector(
                            gate_key,
                            "source_artifacts",
                            artifact_path,
                        ),
                        artifact_path=str(artifact_path),
                        provenance_mode="paper_gate_source_artifact_path_resolved",
                    )
    paper_gate_closure_map_md = paper_gate_closure_map_json.with_suffix(".md")
    if paper_gate_closure_map_json.exists():
        paper_gate_closure_map_id = "report:paper_gate_closure_map"
        add_node(
            nodes,
            paper_gate_closure_map_id,
            "report",
            path=(
                str(paper_gate_closure_map_md)
                if paper_gate_closure_map_md.exists()
                else None
            ),
            json_path=str(paper_gate_closure_map_json),
            summary=(
                "Paper-gate closure map separating positive final-claim gates "
                "from scoped diagnostic, negative, and no-claim manuscript paths."
            ),
        )
        add_edge(
            edges,
            paper_gate_closure_map_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        add_edge(
            edges,
            paper_gate_closure_map_id,
            "report:manuscript_readiness_map",
            "DERIVED_FROM",
        )
        try:
            closure_map = json.loads(
                paper_gate_closure_map_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            closure_map = {}
        for gate in closure_map.get("gate_rows", []) or []:
            if not isinstance(gate, dict) or not gate.get("gate_id"):
                continue
            gate_key = str(gate["gate_id"])
            control_id = f"methodology_control:paper_gate_closure:{slug_fragment(gate_key)}"
            add_node(
                nodes,
                control_id,
                "methodology_control",
                gate_id=gate_key,
                gate_class=gate.get("gate_class"),
                current_status=gate.get("current_status"),
                closure_mode=gate.get("closure_mode"),
                positive_claim_ready=gate.get("positive_claim_ready"),
                scoped_or_negative_path_ready=gate.get(
                    "scoped_or_negative_path_ready"
                ),
                local_execution_gap_remaining=gate.get(
                    "local_execution_gap_remaining"
                ),
                paper_allowed_language=gate.get("paper_allowed_language"),
                paper_disallowed_language=gate.get("paper_disallowed_language"),
                summary=(
                    f"Paper gate closure disposition for `{gate_key}`: "
                    f"positive claim ready={gate.get('positive_claim_ready')}, "
                    f"scoped/negative path ready="
                    f"{gate.get('scoped_or_negative_path_ready')}."
                ),
            )
            add_edge(
                edges,
                paper_gate_closure_map_id,
                control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(paper_gate_closure_map_json),
                evidence=paper_gate_closure_json_selector(gate_key),
                provenance_mode="paper_gate_closure_row_selector",
            )
            paper_gate_id = f"paper_gate:{slug_fragment(gate_key)}"
            if paper_gate_id in nodes:
                add_edge(
                    edges,
                    paper_gate_closure_map_id,
                    paper_gate_id,
                    "SUMMARIZES_CONTROL",
                    evidence_path=str(paper_gate_closure_map_json),
                    evidence=paper_gate_closure_json_selector(gate_key),
                    provenance_mode="paper_gate_closure_to_readiness_gate",
                )
            for artifact_path in gate.get("source_artifacts", []) or []:
                for source_node_id in artifact_support_node_ids(
                    nodes, path_index, artifact_path
                ):
                    add_edge(
                        edges,
                        paper_gate_closure_map_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(paper_gate_closure_map_json),
                        evidence=paper_gate_closure_json_selector(
                            gate_key,
                            "source_artifacts",
                            artifact_path,
                        ),
                        artifact_path=str(artifact_path),
                        provenance_mode="paper_gate_closure_source_artifact",
                    )
    paper_gate_execution_plan_md = paper_gate_execution_plan_json.with_suffix(".md")
    if paper_gate_execution_plan_json.exists():
        paper_gate_execution_plan_id = "report:paper_gate_closure_execution_plan"
        add_node(
            nodes,
            paper_gate_execution_plan_id,
            "report",
            path=(
                str(paper_gate_execution_plan_md)
                if paper_gate_execution_plan_md.exists()
                else None
            ),
            json_path=str(paper_gate_execution_plan_json),
            summary=(
                "Execution plan mapping blocked positive paper gates to "
                "protocol, empirical, refresh, and claim-control actions."
            ),
        )
        add_edge(
            edges,
            paper_gate_execution_plan_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "report:paper_gate_closure_map",
            "report:manuscript_readiness_map",
        ):
            if source_id in nodes:
                add_edge(
                    edges,
                    paper_gate_execution_plan_id,
                    source_id,
                    "DERIVED_FROM",
                )
        try:
            paper_gate_execution_plan = json.loads(
                paper_gate_execution_plan_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            paper_gate_execution_plan = {}
        path_index = build_node_path_index(nodes)
        for action in paper_gate_execution_plan.get("action_rows", []) or []:
            if not isinstance(action, dict) or not action.get("action_id"):
                continue
            action_id = str(action["action_id"])
            gate_key = str(action.get("gate_id") or "")
            control_id = (
                "methodology_control:paper_gate_execution:"
                f"{slug_fragment(action_id)}"
            )
            add_node(
                nodes,
                control_id,
                "methodology_control",
                action_id=action_id,
                gate_id=gate_key,
                action_class=action.get("action_class"),
                stage=action.get("stage"),
                status=action.get("status"),
                can_execute_now=action.get("can_execute_now"),
                blocked_dependency_gate_ids=action.get(
                    "blocked_dependency_gate_ids"
                ),
                depends_on_action_ids=action.get("depends_on_action_ids"),
                claim_effect=action.get("claim_effect"),
                summary=(
                    f"Paper-gate execution action `{action_id}` has status "
                    f"{action.get('status')}."
                ),
            )
            add_edge(
                edges,
                paper_gate_execution_plan_id,
                control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(paper_gate_execution_plan_json),
                evidence=paper_gate_execution_action_json_selector(action_id),
                provenance_mode="paper_gate_execution_action_selector",
            )
            paper_gate_id = f"paper_gate:{slug_fragment(gate_key)}"
            if paper_gate_id in nodes:
                add_edge(
                    edges,
                    paper_gate_execution_plan_id,
                    paper_gate_id,
                    "SUMMARIZES_CONTROL",
                    evidence_path=str(paper_gate_execution_plan_json),
                    evidence=paper_gate_execution_action_json_selector(action_id),
                    provenance_mode="paper_gate_execution_to_readiness_gate",
                )
            for artifact_path in action.get("source_artifacts", []) or []:
                for source_node_id in artifact_support_node_ids(
                    nodes, path_index, artifact_path
                ):
                    if nodes.get(source_node_id, {}).get("type") not in {
                        "audit",
                        "catalog",
                        "report",
                    }:
                        continue
                    add_edge(
                        edges,
                        paper_gate_execution_plan_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(paper_gate_execution_plan_json),
                        evidence=paper_gate_execution_action_json_selector(
                            action_id,
                            "source_artifacts",
                            artifact_path,
                        ),
                        artifact_path=str(artifact_path),
                        provenance_mode="paper_gate_execution_source_artifact",
                    )
    paper_gate_protocol_design_md = paper_gate_protocol_design_json.with_suffix(".md")
    if paper_gate_protocol_design_json.exists():
        paper_gate_protocol_design_id = "report:paper_gate_protocol_design_bundle"
        add_node(
            nodes,
            paper_gate_protocol_design_id,
            "report",
            path=(
                str(paper_gate_protocol_design_md)
                if paper_gate_protocol_design_md.exists()
                else None
            ),
            json_path=str(paper_gate_protocol_design_json),
            summary=(
                "Protocol-design bundle completing the first executable "
                "claim-contract actions for blocked paper gates without "
                "promoting positive claims."
            ),
        )
        add_edge(
            edges,
            paper_gate_protocol_design_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "report:paper_gate_closure_map",
            "report:manuscript_readiness_map",
            "report:paper_gate_closure_execution_plan",
            "report:selection_multiplicity_protocol",
            "report:bounded_support_protocol",
            "report:fairness_population_readiness_audit",
            "report:venn_abers_validation_readiness_audit",
            "report:venn_abers_grid_ivapd_validation_protocol",
            "report:method_performance_synthesis",
        ):
            if source_id in nodes:
                add_edge(
                    edges,
                    paper_gate_protocol_design_id,
                    source_id,
                    "DERIVED_FROM",
                )
        try:
            paper_gate_protocol_design = json.loads(
                paper_gate_protocol_design_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            paper_gate_protocol_design = {}
        for row in paper_gate_protocol_design.get("protocol_design_rows", []) or []:
            if not isinstance(row, dict) or not row.get("action_id"):
                continue
            action_id = str(row["action_id"])
            gate_key = str(row.get("gate_id") or "")
            protocol_control_id = (
                "methodology_control:paper_gate_protocol_design:"
                f"{slug_fragment(action_id)}"
            )
            add_node(
                nodes,
                protocol_control_id,
                "methodology_control",
                action_id=action_id,
                gate_id=gate_key,
                protocol_id=row.get("protocol_id"),
                status=row.get("status"),
                claim_effect=row.get("claim_effect"),
                downstream_action_ids=row.get("downstream_action_ids"),
                summary=(
                    f"Paper-gate protocol design `{row.get('protocol_id')}` "
                    f"completes action `{action_id}` without positive claim "
                    "promotion."
                ),
            )
            add_edge(
                edges,
                paper_gate_protocol_design_id,
                protocol_control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(paper_gate_protocol_design_json),
                evidence=paper_gate_protocol_design_json_selector(action_id),
                provenance_mode="paper_gate_protocol_design_selector",
            )
            execution_control_id = (
                "methodology_control:paper_gate_execution:"
                f"{slug_fragment(action_id)}"
            )
            if execution_control_id in nodes:
                add_edge(
                    edges,
                    paper_gate_protocol_design_id,
                    execution_control_id,
                    "SUMMARIZES_CONTROL",
                    evidence_path=str(paper_gate_protocol_design_json),
                    evidence=paper_gate_protocol_design_json_selector(
                        action_id,
                        "status",
                        "protocol_design_complete",
                    ),
                    provenance_mode="paper_gate_protocol_design_summarizes_completed_action",
                )
            paper_gate_id = f"paper_gate:{slug_fragment(gate_key)}"
            if paper_gate_id in nodes:
                add_edge(
                    edges,
                    paper_gate_protocol_design_id,
                    paper_gate_id,
                    "SUMMARIZES_CONTROL",
                    evidence_path=str(paper_gate_protocol_design_json),
                    evidence=paper_gate_protocol_design_json_selector(action_id),
                    provenance_mode="paper_gate_protocol_design_to_gate",
                )
    fairness_sampling_weight_policy_md = fairness_sampling_weight_policy_json.with_suffix(
        ".md"
    )
    if fairness_sampling_weight_policy_json.exists():
        fairness_sampling_weight_policy_id = "report:fairness_sampling_weight_policy"
        add_node(
            nodes,
            fairness_sampling_weight_policy_id,
            "report",
            path=(
                str(fairness_sampling_weight_policy_md)
                if fairness_sampling_weight_policy_md.exists()
                else None
            ),
            json_path=str(fairness_sampling_weight_policy_json),
            summary=(
                "Fairness sampling/weighting policy contract declaring current "
                "diagnostic-only unweighted estimands and future population-claim "
                "requirements without promoting fairness claims."
            ),
        )
        add_edge(
            edges,
            fairness_sampling_weight_policy_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:manuscript_bundle_index",
            "report:paper_gate_protocol_design_bundle",
            "report:fairness_population_readiness_audit",
            "report:paper_gate_closure_execution_plan",
        ):
            if source_id in nodes:
                add_edge(
                    edges,
                    fairness_sampling_weight_policy_id,
                    source_id,
                    "DERIVED_FROM",
                )
        execution_control_id = (
            "methodology_control:paper_gate_execution:"
            "fairness_population_inference_gate_define_sampling_weight_policy"
        )
        if execution_control_id in nodes:
            add_edge(
                edges,
                fairness_sampling_weight_policy_id,
                execution_control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_sampling_weight_policy_json),
                evidence=fairness_sampling_weight_policy_json_selector(
                    None,
                    "summary.action_status",
                    "protocol_design_complete",
                ),
                provenance_mode="fairness_sampling_policy_completed_action",
            )
        fairness_gate_id = "paper_gate:fairness_population_inference_gate"
        if fairness_gate_id in nodes:
            add_edge(
                edges,
                fairness_sampling_weight_policy_id,
                fairness_gate_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_sampling_weight_policy_json),
                evidence=fairness_sampling_weight_policy_json_selector(
                    None, "summary.gate_id", "fairness_population_inference_gate"
                ),
                provenance_mode="fairness_sampling_policy_to_gate",
            )
            add_edge(
                edges,
                fairness_gate_id,
                fairness_sampling_weight_policy_id,
                "DERIVED_FROM",
                artifact_path=str(fairness_sampling_weight_policy_json),
                evidence_path=str(manuscript_readiness_map_json),
                evidence=paper_gate_json_selector(
                    "fairness_population_inference_gate",
                    "source_artifacts",
                    str(fairness_sampling_weight_policy_json),
                ),
                provenance_mode="paper_gate_source_artifact_path_resolved",
            )
        try:
            fairness_sampling_weight_policy = json.loads(
                fairness_sampling_weight_policy_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            fairness_sampling_weight_policy = {}
        for row in fairness_sampling_weight_policy.get("bundle_policy_rows", []) or []:
            if not isinstance(row, dict) or not row.get("bundle_id"):
                continue
            bundle_id = str(row["bundle_id"])
            dataset_id = str(row.get("dataset_id") or "")
            control_id = (
                "methodology_control:fairness_sampling_weight_policy:"
                f"{slug_fragment(bundle_id)}"
            )
            add_node(
                nodes,
                control_id,
                "methodology_control",
                bundle_id=bundle_id,
                dataset_id=dataset_id,
                diagnostic_group=row.get("diagnostic_group"),
                policy_id=row.get("policy_id"),
                policy_status=row.get("policy_status"),
                current_estimand_policy=row.get("current_estimand_policy"),
                dataset_policy_class=row.get("dataset_policy_class"),
                weighted_estimand_applied=row.get("weighted_estimand_applied"),
                claim_effect=row.get("claim_effect"),
                summary=(
                    f"Fairness sampling policy for bundle `{bundle_id}`: "
                    f"{row.get('current_estimand_policy')} with claim effect "
                    f"{row.get('claim_effect')}."
                ),
            )
            add_edge(
                edges,
                fairness_sampling_weight_policy_id,
                control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_sampling_weight_policy_json),
                evidence=fairness_sampling_weight_policy_json_selector(bundle_id),
                provenance_mode="fairness_sampling_policy_row_selector",
            )
            if dataset_id:
                add_edge(
                    edges,
                    fairness_sampling_weight_policy_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(fairness_sampling_weight_policy_json),
                    evidence=fairness_sampling_weight_policy_json_selector(
                        bundle_id, "dataset_id", dataset_id
                    ),
                    provenance_mode="fairness_sampling_policy_dataset",
                )
    fairness_group_diagnostic_md = fairness_group_diagnostic_json.with_suffix(".md")
    if fairness_group_diagnostic_json.exists():
        fairness_group_diagnostic_id = "report:fairness_group_diagnostic_audit"
        add_node(
            nodes,
            fairness_group_diagnostic_id,
            "report",
            path=(
                str(fairness_group_diagnostic_md)
                if fairness_group_diagnostic_md.exists()
                else None
            ),
            json_path=str(fairness_group_diagnostic_json),
            summary=(
                "Diagnostic fairness-group audit recording group counts, "
                "missingness, coverage and width group gaps, and uncertainty "
                "without promoting population fairness claims."
            ),
        )
        add_edge(
            edges,
            fairness_group_diagnostic_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "catalog:manuscript_bundle_index",
            "report:fairness_sampling_weight_policy",
            "report:fairness_population_readiness_audit",
            "report:paper_gate_closure_execution_plan",
        ):
            if source_id in nodes:
                add_edge(
                    edges,
                    fairness_group_diagnostic_id,
                    source_id,
                    "DERIVED_FROM",
                )
        execution_control_id = (
            "methodology_control:paper_gate_execution:"
            "fairness_population_inference_gate_compute_group_counts_missingness_and_gaps"
        )
        if execution_control_id in nodes:
            add_edge(
                edges,
                fairness_group_diagnostic_id,
                execution_control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_group_diagnostic_json),
                evidence=fairness_group_diagnostic_json_selector(
                    None,
                    "summary.action_status",
                    "empirical_execution_complete",
                ),
                provenance_mode="fairness_group_diagnostic_completed_action",
            )
        fairness_gate_id = "paper_gate:fairness_population_inference_gate"
        if fairness_gate_id in nodes:
            add_edge(
                edges,
                fairness_group_diagnostic_id,
                fairness_gate_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_group_diagnostic_json),
                evidence=fairness_group_diagnostic_json_selector(
                    None, "summary.gate_id", "fairness_population_inference_gate"
                ),
                provenance_mode="fairness_group_diagnostic_to_gate",
            )
        try:
            fairness_group_diagnostic = json.loads(
                fairness_group_diagnostic_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            fairness_group_diagnostic = {}
        for row in fairness_group_diagnostic.get("rows", []) or []:
            if not isinstance(row, dict) or not row.get("bundle_id"):
                continue
            bundle_id = str(row["bundle_id"])
            dataset_id = str(row.get("dataset_id") or "")
            control_id = (
                "methodology_control:fairness_group_diagnostic:"
                f"{slug_fragment(bundle_id)}"
            )
            add_node(
                nodes,
                control_id,
                "methodology_control",
                bundle_id=bundle_id,
                dataset_id=dataset_id,
                diagnostic_group=row.get("diagnostic_group"),
                min_group_count=row.get("min_group_count"),
                group_count=row.get("group_count"),
                group_counts_recorded=row.get("group_counts_recorded"),
                missingness_by_group_audited=row.get(
                    "missingness_by_group_audited"
                ),
                coverage_by_group_recorded=row.get("coverage_by_group_recorded"),
                width_by_group_recorded=row.get("width_by_group_recorded"),
                group_gap_uncertainty_recorded=row.get(
                    "group_gap_uncertainty_recorded"
                ),
                claim_effect=row.get("claim_effect"),
                summary=(
                    f"Fairness group diagnostic audit for bundle `{bundle_id}` "
                    f"records min group n {row.get('min_group_count')} and "
                    f"gap uncertainty `{row.get('group_gap_uncertainty_recorded')}`."
                ),
            )
            add_edge(
                edges,
                fairness_group_diagnostic_id,
                control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_group_diagnostic_json),
                evidence=fairness_group_diagnostic_json_selector(bundle_id),
                provenance_mode="fairness_group_diagnostic_row_selector",
            )
            if dataset_id:
                add_edge(
                    edges,
                    fairness_group_diagnostic_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(fairness_group_diagnostic_json),
                    evidence=fairness_group_diagnostic_json_selector(
                        bundle_id, "dataset_id", dataset_id
                    ),
                    provenance_mode="fairness_group_diagnostic_dataset",
                )
    fairness_group_multiplicity_scope_md = (
        fairness_group_multiplicity_scope_json.with_suffix(".md")
    )
    if fairness_group_multiplicity_scope_json.exists():
        fairness_group_multiplicity_scope_id = (
            "report:fairness_group_multiplicity_scope"
        )
        add_node(
            nodes,
            fairness_group_multiplicity_scope_id,
            "report",
            path=(
                str(fairness_group_multiplicity_scope_md)
                if fairness_group_multiplicity_scope_md.exists()
                else None
            ),
            json_path=str(fairness_group_multiplicity_scope_json),
            summary=(
                "Diagnostic group-comparison multiplicity scope declaring "
                "exploratory family boundaries and claim-register citation "
                "without promoting fairness claims."
            ),
        )
        add_edge(
            edges,
            fairness_group_multiplicity_scope_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "report:fairness_group_diagnostic_audit",
            "report:fairness_sampling_weight_policy",
            "catalog:manuscript_claim_register",
            "catalog:manuscript_claim_register_md",
            "report:paper_gate_closure_execution_plan",
        ):
            if source_id in nodes:
                add_edge(
                    edges,
                    fairness_group_multiplicity_scope_id,
                    source_id,
                    "DERIVED_FROM",
                )
        execution_control_id = (
            "methodology_control:paper_gate_execution:"
            "fairness_population_inference_gate_"
            "declare_group_comparison_multiplicity_scope"
        )
        if execution_control_id in nodes:
            add_edge(
                edges,
                fairness_group_multiplicity_scope_id,
                execution_control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_group_multiplicity_scope_json),
                evidence=fairness_group_multiplicity_scope_json_selector(
                    None,
                    "summary.action_status",
                    "multiplicity_control_complete",
                ),
                provenance_mode="fairness_group_multiplicity_completed_action",
            )
        fairness_gate_id = "paper_gate:fairness_population_inference_gate"
        if fairness_gate_id in nodes:
            add_edge(
                edges,
                fairness_group_multiplicity_scope_id,
                fairness_gate_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_group_multiplicity_scope_json),
                evidence=fairness_group_multiplicity_scope_json_selector(
                    None, "summary.gate_id", "fairness_population_inference_gate"
                ),
                provenance_mode="fairness_group_multiplicity_to_gate",
            )
        claim_requirement_id = (
            "claim_requirement:final_selection_and_fairness_claims_blocked:"
            "fairness_population_inference_gate"
        )
        if claim_requirement_id in nodes:
            add_edge(
                edges,
                claim_requirement_id,
                fairness_group_multiplicity_scope_id,
                "SUPPORTED_BY",
                evidence_path=str(Path(args.manuscript_claim_register)),
                evidence=claim_requirement_json_selector(
                    "final_selection_and_fairness_claims_blocked",
                    "fairness_population_inference_gate",
                    "supporting_node_ids",
                    "report:fairness_group_multiplicity_scope",
                ),
                provenance_mode="claim_requirement_artifact_path_resolved",
            )
        try:
            fairness_group_multiplicity_scope = json.loads(
                fairness_group_multiplicity_scope_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            fairness_group_multiplicity_scope = {}
        for row in fairness_group_multiplicity_scope.get("rows", []) or []:
            if not isinstance(row, dict) or not row.get("bundle_id"):
                continue
            bundle_id = str(row["bundle_id"])
            dataset_id = str(row.get("dataset_id") or "")
            control_id = (
                "methodology_control:fairness_group_multiplicity_scope:"
                f"{slug_fragment(bundle_id)}"
            )
            add_node(
                nodes,
                control_id,
                "methodology_control",
                bundle_id=bundle_id,
                dataset_id=dataset_id,
                diagnostic_group=row.get("diagnostic_group"),
                comparison_family_id=row.get("comparison_family_id"),
                pairwise_group_comparison_count=row.get(
                    "pairwise_group_comparison_count"
                ),
                multiplicity_policy=row.get("multiplicity_policy"),
                claim_effect=row.get("claim_effect"),
                summary=(
                    f"Fairness group multiplicity scope for bundle `{bundle_id}` "
                    f"declares family `{row.get('comparison_family_id')}` with "
                    f"claim effect {row.get('claim_effect')}."
                ),
            )
            add_edge(
                edges,
                fairness_group_multiplicity_scope_id,
                control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(fairness_group_multiplicity_scope_json),
                evidence=fairness_group_multiplicity_scope_json_selector(bundle_id),
                provenance_mode="fairness_group_multiplicity_row_selector",
            )
            if dataset_id:
                add_edge(
                    edges,
                    fairness_group_multiplicity_scope_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(fairness_group_multiplicity_scope_json),
                    evidence=fairness_group_multiplicity_scope_json_selector(
                        bundle_id, "dataset_id", dataset_id
                    ),
                    provenance_mode="fairness_group_multiplicity_dataset",
                )
    post_experiment_publication_activation_md = (
        post_experiment_publication_activation_json.with_suffix(".md")
    )
    if post_experiment_publication_activation_json.exists():
        activation_audit_id = "report:post_experiment_publication_activation_audit"
        add_node(
            nodes,
            activation_audit_id,
            "report",
            path=(
                str(post_experiment_publication_activation_md)
                if post_experiment_publication_activation_md.exists()
                else None
            ),
            json_path=str(post_experiment_publication_activation_json),
            summary=(
                "Stop/go audit for neutral post-experiment publication preparation, "
                "preserving final manuscript, retained-visual, and sterile-repository "
                "claim boundaries."
            ),
        )
        add_edge(edges, activation_audit_id, methodology_report_id, "SUPPORTS_REPORT")
        for source_id, source_key in (
            (
                "catalog:post_experiment_publication_program",
                "post_experiment_publication_program",
            ),
            ("report:goal_completion_audit", "goal_completion_audit"),
            ("report:manuscript_readiness_map", "paper_readiness_map"),
            ("report:paper_gate_closure_map", "paper_gate_closure_map"),
            (
                "report:paper_gate_closure_execution_plan",
                "paper_gate_closure_execution_plan",
            ),
            ("report:publication_methodology_audit", "publication_methodology_audit"),
            ("report:experiment_accounting_audit", "experiment_accounting_audit"),
            (
                "report:knowledge_graph_quality_summary",
                "knowledge_graph_quality_summary",
            ),
            ("report:kg_publication_quality_audit", "kg_publication_quality_audit"),
            (
                "report:scientific_review_finding_register",
                "scientific_review_finding_register",
            ),
            (
                "catalog:manuscript_bundle_eligibility_matrix",
                "manuscript_bundle_eligibility",
            ),
        ):
            add_edge(
                edges,
                activation_audit_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(post_experiment_publication_activation_json),
                evidence=f"$.sources.{source_key}",
            )
        add_edge(
            edges,
            "catalog:post_experiment_publication_activation_audit",
            activation_audit_id,
            "RENDERS",
            evidence_path=str(post_experiment_publication_activation_json),
            evidence="$.summary",
        )
        try:
            activation_audit = json.loads(
                post_experiment_publication_activation_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            activation_audit = {}
        for check_index, check in enumerate(
            activation_audit.get("activation_checks") or []
        ):
            check_id = str(check.get("check_id") or "").strip()
            if not check_id:
                continue
            node_id = (
                "methodology_control:post_experiment_publication_activation:"
                f"{slug_fragment(check_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=check_id,
                status=check.get("status"),
                blocks_activation=check.get("blocks_activation"),
                required_for=check.get("required_for"),
                blocker=check.get("blocker"),
                summary=(
                    "Post-experiment publication activation check "
                    f"`{check_id}` has status {check.get('status')}."
                ),
            )
            add_edge(
                edges,
                activation_audit_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(post_experiment_publication_activation_json),
                evidence=row_selector("activation_checks", check_index, "check_id"),
            )

    publication_preparation_packets_md = (
        publication_preparation_packets_json.with_suffix(".md")
    )
    if publication_preparation_packets_json.exists():
        publication_preparation_id = "report:publication_preparation_packets"
        add_node(
            nodes,
            publication_preparation_id,
            "report",
            path=(
                str(publication_preparation_packets_md)
                if publication_preparation_packets_md.exists()
                else None
            ),
            json_path=str(publication_preparation_packets_json),
            summary=(
                "Neutral pre-prose publication preparation packets for reviewer "
                "design and visual/table inventory planning; final prose, retained "
                "visual selection, sterile release, and positive claims remain gated."
            ),
        )
        add_edge(edges, publication_preparation_id, methodology_report_id, "SUPPORTS_REPORT")
        for source_id, selector in (
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_experiment_publication_program",
            ),
            (
                "report:post_experiment_publication_activation_audit",
                "$.sources.post_experiment_publication_activation",
            ),
            ("report:goal_completion_audit", "$.sources.goal_completion"),
            ("report:paper_gate_closure_map", "$.sources.paper_gate_closure_map"),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language",
            ),
            ("report:neutral_experiment_closure_audit", "$.sources.neutral_closure"),
            ("report:method_performance_synthesis", "$.visual_table_inventory_plan"),
            (
                "report:method_selection_inferential_audit",
                "$.visual_table_inventory_plan",
            ),
            (
                "report:venn_abers_grid_failure_mode_decomposition",
                "$.visual_table_inventory_plan",
            ),
            (
                "report:bounded_support_endpoint_closure_audit",
                "$.visual_table_inventory_plan",
            ),
            (
                "report:fairness_group_diagnostic_audit",
                "$.visual_table_inventory_plan",
            ),
            (
                "report:duplicate_sensitivity_closure_audit",
                "$.visual_table_inventory_plan",
            ),
            ("report:kg_publication_quality_audit", "$.sources.kg_publication"),
        ):
            add_edge(
                edges,
                publication_preparation_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(publication_preparation_packets_json),
                evidence=selector,
            )
        try:
            preparation_payload = json.loads(
                publication_preparation_packets_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            preparation_payload = {}
        for packet_index, packet in enumerate(
            preparation_payload.get("reviewer_packets") or []
        ):
            reviewer_id = str(packet.get("reviewer_id") or "").strip()
            if not reviewer_id:
                continue
            reviewer_node_id = f"publication_reviewer:{slug_fragment(reviewer_id)}"
            if reviewer_node_id not in nodes:
                add_node(
                    nodes,
                    reviewer_node_id,
                    "reviewer_perspective",
                    reviewer_id=reviewer_id,
                    summary=f"Publication reviewer perspective `{reviewer_id}`.",
                )
            add_edge(
                edges,
                publication_preparation_id,
                reviewer_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_preparation_packets_json),
                evidence=row_selector("reviewer_packets", packet_index, "reviewer_id"),
            )
        for family_index, family in enumerate(
            preparation_payload.get("visual_table_inventory_plan") or []
        ):
            family_id = str(family.get("artifact_family_id") or "").strip()
            if not family_id:
                continue
            node_id = (
                "methodology_control:publication_preparation_visual_inventory:"
                f"{slug_fragment(family_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=family_id,
                status=family.get("inventory_status"),
                artifact_type=family.get("artifact_type"),
                final_retain_decision=family.get("final_retain_decision"),
                target_surfaces=family.get("target_surfaces"),
                claim_boundary=family.get("claim_boundary"),
                summary=(
                    "Publication preparation visual/table inventory family "
                    f"`{family_id}` remains candidate-only with retain decision "
                    f"{family.get('final_retain_decision')}."
                ),
            )
            add_edge(
                edges,
                publication_preparation_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_preparation_packets_json),
                evidence=row_selector(
                    "visual_table_inventory_plan",
                    family_index,
                    "artifact_family_id",
                ),
            )

    reviewer_design_brief_md = reviewer_design_brief_json.with_suffix(".md")
    if reviewer_design_brief_json.exists():
        reviewer_design_id = "report:reviewer_design_reconciliation"
        add_node(
            nodes,
            reviewer_design_id,
            "report",
            path=(
                str(reviewer_design_brief_md)
                if reviewer_design_brief_md.exists()
                else None
            ),
            json_path=str(reviewer_design_brief_json),
            summary=(
                "Neutral pre-prose reviewer design brief and reconciliation "
                "matrix; reviewer advice, content placement, and site decisions "
                "remain design-only with final prose, retained visuals, release, "
                "and positive claims blocked."
            ),
        )
        add_edge(edges, reviewer_design_id, methodology_report_id, "SUPPORTS_REPORT")
        for source_id, selector in (
            (
                "report:publication_preparation_packets",
                "$.sources.publication_preparation_packets",
            ),
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_experiment_publication_program",
            ),
            (
                "report:post_experiment_publication_activation_audit",
                "$.sources.post_experiment_publication_activation",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language",
            ),
            ("report:goal_completion_audit", "$.sources.goal_completion"),
            ("report:paper_gate_closure_map", "$.sources.paper_gate_closure_map"),
        ):
            add_edge(
                edges,
                reviewer_design_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(reviewer_design_brief_json),
                evidence=selector,
            )
        try:
            reviewer_design_payload = json.loads(
                reviewer_design_brief_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            reviewer_design_payload = {}
        for advice_index, advice in enumerate(
            reviewer_design_payload.get("reviewer_advice_records") or []
        ):
            recommendation_id = str(advice.get("recommendation_id") or "").strip()
            if not recommendation_id:
                continue
            node_id = (
                "methodology_control:reviewer_design_advice:"
                f"{slug_fragment(recommendation_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=recommendation_id,
                reviewer_id=advice.get("reviewer_id"),
                advice_topic=advice.get("advice_topic"),
                target_surface=advice.get("target_surface"),
                decision=advice.get("accept_reject_defer_decision"),
                decision_scope=advice.get("decision_scope"),
                blocked_gate_dependency=advice.get("blocked_gate_dependency"),
                mapped_artifact=advice.get("mapped_artifact"),
                visual_family_ids=advice.get("visual_family_ids"),
                claim_boundary=advice.get("claim_boundary"),
                summary=(
                    "Reviewer design advice "
                    f"`{recommendation_id}` is "
                    f"{advice.get('accept_reject_defer_decision')} for "
                    "pre-prose design only."
                ),
            )
            add_edge(
                edges,
                reviewer_design_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(reviewer_design_brief_json),
                evidence=row_selector(
                    "reviewer_advice_records", advice_index, "recommendation_id"
                ),
            )
        for content_index, content in enumerate(
            reviewer_design_payload.get("article_supplement_content_matrix") or []
        ):
            content_id = str(content.get("content_area_id") or "").strip()
            if not content_id:
                continue
            node_id = (
                "methodology_control:reviewer_design_content_matrix:"
                f"{slug_fragment(content_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=content_id,
                artifact_type=content.get("artifact_type"),
                candidate_surface=content.get("candidate_surface"),
                gate_dependency=content.get("gate_dependency"),
                placement_status=content.get("placement_status"),
                final_placement_decision=content.get("final_placement_decision"),
                retained_visual_or_table_decision=content.get(
                    "retained_visual_or_table_decision"
                ),
                visual_audit_status=content.get("visual_audit_status"),
                claim_boundary=content.get("claim_boundary"),
                summary=(
                    "Reviewer design content-matrix row "
                    f"`{content_id}` remains candidate-only with final placement "
                    f"{content.get('final_placement_decision')}."
                ),
            )
            add_edge(
                edges,
                reviewer_design_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(reviewer_design_brief_json),
                evidence=row_selector(
                    "article_supplement_content_matrix",
                    content_index,
                    "content_area_id",
                ),
            )
        site_record = reviewer_design_payload.get("publication_site_decision_record")
        if isinstance(site_record, dict) and site_record.get("record_id"):
            site_node_id = "methodology_control:reviewer_design_publication_site_decision"
            add_node(
                nodes,
                site_node_id,
                "methodology_control",
                name=site_record.get("record_id"),
                status=site_record.get("status"),
                site_decision_status=site_record.get("site_decision_status"),
                site_deployment_authorized=site_record.get(
                    "site_deployment_authorized"
                ),
                sterile_repository_required_before_deployment=site_record.get(
                    "sterile_repository_required_before_deployment"
                ),
                claim_boundary=site_record.get("claim_boundary"),
                summary=(
                    "Publication-site decision remains a deferred design record; "
                    "deployment is not authorized before release gates pass."
                ),
            )
            add_edge(
                edges,
                reviewer_design_id,
                site_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(reviewer_design_brief_json),
                evidence="$.publication_site_decision_record.record_id",
            )

    visual_table_audit_plan_md = visual_table_audit_plan_json.with_suffix(".md")
    if visual_table_audit_plan_json.exists():
        visual_audit_id = "report:publication_visual_table_audit_plan"
        triptych_id = "report:article_supplement_kg_triptych_decision"
        add_node(
            nodes,
            visual_audit_id,
            "report",
            path=(
                str(visual_table_audit_plan_md)
                if visual_table_audit_plan_md.exists()
                else None
            ),
            json_path=str(visual_table_audit_plan_json),
            summary=(
                "Neutral pre-prose visual/table audit plan; candidate artifacts, "
                "quality checks, and triptych components remain planned with no "
                "retained visuals, final prose, site deployment, or positive "
                "claims authorized."
            ),
        )
        add_edge(edges, visual_audit_id, methodology_report_id, "SUPPORTS_REPORT")
        for source_id, selector in (
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_experiment_publication_program",
            ),
            (
                "report:reviewer_design_reconciliation",
                "$.sources.reviewer_design_brief",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language",
            ),
            ("report:knowledge_graph_quality_summary", "$.sources.kg_quality"),
            (
                "report:kg_publication_quality_audit",
                "$.sources.kg_publication_quality",
            ),
        ):
            add_edge(
                edges,
                visual_audit_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(visual_table_audit_plan_json),
                evidence=selector,
            )
        try:
            visual_audit_payload = json.loads(
                visual_table_audit_plan_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            visual_audit_payload = {}
        for item_index, item in enumerate(
            visual_audit_payload.get("candidate_audit_rows") or []
        ):
            content_id = str(item.get("content_area_id") or "").strip()
            if not content_id:
                continue
            item_node_id = (
                "methodology_control:publication_visual_audit_item:"
                f"{slug_fragment(content_id)}"
            )
            add_node(
                nodes,
                item_node_id,
                "methodology_control",
                name=content_id,
                artifact_type=item.get("artifact_type"),
                candidate_surface=item.get("candidate_surface"),
                audit_status=item.get("audit_status"),
                auditor_decision=item.get("auditor_decision"),
                decision_scope=item.get("decision_scope"),
                final_retention_authorized=item.get("final_retention_authorized"),
                final_placement_decision=item.get("final_placement_decision"),
                retained_visual_or_table_decision=item.get(
                    "retained_visual_or_table_decision"
                ),
                gate_dependency=item.get("gate_dependency"),
                claim_boundary=item.get("claim_boundary"),
                summary=(
                    "Publication visual/table audit item "
                    f"`{content_id}` remains planned-not-started with no final "
                    "retention authorized."
                ),
            )
            add_edge(
                edges,
                visual_audit_id,
                item_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(visual_table_audit_plan_json),
                evidence=row_selector(
                    "candidate_audit_rows", item_index, "content_area_id"
                ),
            )
        quality_checks = (
            (visual_audit_payload.get("visual_table_audit_contract") or {}).get(
                "quality_checks"
            )
            or []
        )
        for check_index, check_name in enumerate(quality_checks):
            check_text = str(check_name).strip()
            if not check_text:
                continue
            check_node_id = (
                "methodology_control:publication_visual_quality_check:"
                f"{slug_fragment(check_text)}"
            )
            add_node(
                nodes,
                check_node_id,
                "methodology_control",
                name=check_text,
                decision_scope="visual_table_audit_planning_only",
                summary=(
                    "Publication visual/table quality check required before "
                    "any retained artifact decision."
                ),
            )
            add_edge(
                edges,
                visual_audit_id,
                check_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(visual_table_audit_plan_json),
                evidence=(
                    "$.visual_table_audit_contract.quality_checks"
                    f"[{check_index}]"
                ),
            )
        triptych_md = article_supplement_kg_triptych_decision_json.with_suffix(".md")
        if article_supplement_kg_triptych_decision_json.exists():
            add_node(
                nodes,
                triptych_id,
                "report",
                path=str(triptych_md) if triptych_md.exists() else None,
                json_path=str(article_supplement_kg_triptych_decision_json),
                summary=(
                    "Candidate article/supplement/KG triptych decision; KG "
                    "citation, site deployment, final prose, and release remain "
                    "blocked."
                ),
            )
            add_edge(edges, triptych_id, methodology_report_id, "SUPPORTS_REPORT")
            add_edge(
                edges,
                triptych_id,
                visual_audit_id,
                "DERIVED_FROM",
                evidence_path=str(article_supplement_kg_triptych_decision_json),
                evidence="$.sources",
            )
            triptych_payload = (
                visual_audit_payload.get("article_supplement_kg_triptych_decision")
                or {}
            )
            for component_index, component in enumerate(
                triptych_payload.get("components") or []
            ):
                component_id = str(component.get("component_id") or "").strip()
                if not component_id:
                    continue
                component_node_id = (
                    "methodology_control:article_supplement_kg_triptych_component:"
                    f"{slug_fragment(component_id)}"
                )
                add_node(
                    nodes,
                    component_node_id,
                    "methodology_control",
                    name=component_id,
                    target_surface=component.get("target_surface"),
                    decision_status=component.get("decision_status"),
                    gate_dependency=component.get("gate_dependency"),
                    final_release_authorized=component.get(
                        "final_release_authorized"
                    ),
                    citable_component_authorized=component.get(
                        "citable_component_authorized"
                    ),
                    claim_boundary=component.get("claim_boundary"),
                    summary=(
                        "Triptych component "
                        f"`{component_id}` remains candidate-only with final "
                        "release and citable status unauthorized."
                    ),
                )
                add_edge(
                    edges,
                    triptych_id,
                    component_node_id,
                    "SUMMARIZES_CONTROL",
                    evidence_path=str(
                        article_supplement_kg_triptych_decision_json
                    ),
                    evidence=row_selector(
                        "components", component_index, "component_id"
                    ),
                )

    visual_table_audit_report_md = visual_table_audit_report_json.with_suffix(".md")
    if visual_table_audit_report_json.exists():
        report_id = "report:publication_visual_table_audit_report"
        add_node(
            nodes,
            report_id,
            "report",
            path=(
                str(visual_table_audit_report_md)
                if visual_table_audit_report_md.exists()
                else None
            ),
            json_path=str(visual_table_audit_report_json),
            summary=(
                "Pre-retention visual/table audit report; candidate artifacts "
                "receive source-traceability, claim-boundary, placement, and "
                "iteration feedback while final retention, KG citation, site "
                "deployment, final prose, and positive claims remain blocked."
            ),
        )
        add_edge(edges, report_id, methodology_report_id, "SUPPORTS_REPORT")
        for source_id, selector in (
            (
                "report:publication_visual_table_audit_plan",
                "$.sources.visual_table_audit_plan",
            ),
            (
                "report:reviewer_design_reconciliation",
                "$.sources.article_supplement_content_matrix",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language",
            ),
            ("report:knowledge_graph_quality_summary", "$.sources.kg_quality"),
            (
                "report:kg_publication_quality_audit",
                "$.sources.kg_publication_quality",
            ),
        ):
            add_edge(
                edges,
                report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(visual_table_audit_report_json),
                evidence=selector,
            )
        try:
            visual_table_audit_payload = json.loads(
                visual_table_audit_report_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            visual_table_audit_payload = {}
        for audit_index, audit_row in enumerate(
            visual_table_audit_payload.get("audit_rows") or []
        ):
            content_id = str(audit_row.get("content_area_id") or "").strip()
            if not content_id:
                continue
            node_id = (
                "methodology_control:publication_visual_table_audit_execution:"
                f"{slug_fragment(content_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=content_id,
                artifact_type=audit_row.get("artifact_type"),
                candidate_surface=audit_row.get("candidate_surface"),
                pre_retention_audit_status=audit_row.get(
                    "pre_retention_audit_status"
                ),
                pre_retention_auditor_decision=audit_row.get(
                    "pre_retention_auditor_decision"
                ),
                source_traceability_status=audit_row.get(
                    "source_traceability_status"
                ),
                layout_overlap_check_status=audit_row.get(
                    "layout_overlap_check_status"
                ),
                iteration_required=audit_row.get("iteration_required"),
                final_retention_authorized=audit_row.get(
                    "final_retention_authorized"
                ),
                final_placement_decision=audit_row.get("final_placement_decision"),
                retained_visual_or_table_decision=audit_row.get(
                    "retained_visual_or_table_decision"
                ),
                decision_scope=audit_row.get("decision_scope"),
                gate_dependency=audit_row.get("gate_dependency"),
                claim_boundary=audit_row.get("claim_boundary"),
                summary=(
                    "Pre-retention visual/table audit row "
                    f"`{content_id}` has decision "
                    f"`{audit_row.get('pre_retention_auditor_decision')}` with "
                    "no final retention authorized."
                ),
            )
            add_edge(
                edges,
                report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(visual_table_audit_report_json),
                evidence=row_selector("audit_rows", audit_index, "content_area_id"),
            )
        for sidecar_id, sidecar_path, sidecar_summary in (
            (
                "report:visual_table_inventory",
                visual_table_inventory_json,
                "Inventory of visual/table candidates with no retained artifacts.",
            ),
            (
                "report:visual_table_iteration_register",
                visual_table_iteration_register_json,
                "Iteration register for rendering and re-auditing visual/table candidates.",
            ),
            (
                "report:kg_navigation_usability_audit",
                kg_navigation_usability_audit_json,
                "KG navigation usability audit with citation and deployment still blocked.",
            ),
        ):
            if not sidecar_path.exists():
                continue
            add_node(
                nodes,
                sidecar_id,
                "report",
                json_path=str(sidecar_path),
                summary=sidecar_summary,
            )
            add_edge(edges, sidecar_id, methodology_report_id, "SUPPORTS_REPORT")
            add_edge(
                edges,
                sidecar_id,
                report_id,
                "DERIVED_FROM",
                evidence_path=str(sidecar_path),
                evidence="$.sources",
            )

    visual_table_render_candidate_audit_md = (
        visual_table_render_candidate_audit_json.with_suffix(".md")
    )
    if visual_table_render_candidate_audit_json.exists():
        render_report_id = "report:publication_visual_table_render_candidate_audit"
        add_node(
            nodes,
            render_report_id,
            "report",
            path=(
                str(visual_table_render_candidate_audit_md)
                if visual_table_render_candidate_audit_md.exists()
                else None
            ),
            json_path=str(visual_table_render_candidate_audit_json),
            summary=(
                "Draft visual/table render candidate audit; concrete Markdown/SVG "
                "artifacts are created for layout measurement while final retention, "
                "final prose, KG citation, site deployment, and positive claims "
                "remain unauthorized."
            ),
        )
        add_edge(edges, render_report_id, methodology_report_id, "SUPPORTS_REPORT")
        for source_id, selector in (
            (
                "report:publication_visual_table_audit_report",
                "$.sources.pre_retention_visual_table_audit_report",
            ),
            (
                "report:visual_table_inventory",
                "$.sources.pre_retention_visual_table_audit_report",
            ),
            (
                "report:visual_table_iteration_register",
                "$.sources.pre_retention_visual_table_audit_report",
            ),
        ):
            add_edge(
                edges,
                render_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(visual_table_render_candidate_audit_json),
                evidence=selector,
            )
        try:
            render_payload = json.loads(
                visual_table_render_candidate_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            render_payload = {}
        for row_index, row in enumerate(
            render_payload.get("render_candidate_rows") or []
        ):
            content_id = str(row.get("content_area_id") or "").strip()
            if not content_id:
                continue
            node_id = (
                "methodology_control:publication_visual_table_render_candidate:"
                f"{slug_fragment(content_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=content_id,
                artifact_type=row.get("artifact_type"),
                render_kind=row.get("render_kind"),
                draft_render_status=row.get("draft_render_status"),
                primary_rendered_artifact_path=row.get(
                    "primary_rendered_artifact_path"
                ),
                layout_quality_status=row.get("layout_quality_status"),
                caption_quality_status=row.get("caption_quality_status"),
                source_traceability_status=row.get("source_traceability_status"),
                svg_static_text_overlap_detected=row.get(
                    "svg_static_text_overlap_detected"
                ),
                final_retention_authorized=row.get("final_retention_authorized"),
                retained_visual_or_table_decision=row.get(
                    "retained_visual_or_table_decision"
                ),
                final_manuscript_prose_permission=row.get(
                    "final_manuscript_prose_permission"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Draft visual/table render candidate "
                    f"`{content_id}` has layout status "
                    f"`{row.get('layout_quality_status')}` and no final "
                    "retention authorized."
                ),
            )
            add_edge(
                edges,
                render_report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(visual_table_render_candidate_audit_json),
                evidence=row_selector(
                    "render_candidate_rows", row_index, "content_area_id"
                ),
            )
            pre_retention_node = (
                "methodology_control:publication_visual_table_audit_execution:"
                f"{slug_fragment(content_id)}"
            )
            add_edge(
                edges,
                node_id,
                pre_retention_node,
                "DERIVED_FROM",
                evidence_path=str(visual_table_render_candidate_audit_json),
                evidence=row_selector(
                    "render_candidate_rows", row_index, "content_area_id"
                ),
            )
        for sidecar_id, sidecar_path, sidecar_summary in (
            (
                "report:visual_table_render_candidate_inventory",
                visual_table_render_candidate_inventory_json,
                "Inventory of draft visual/table render candidates with no final retained artifacts.",
            ),
            (
                "report:visual_table_layout_quality_audit",
                visual_table_layout_quality_audit_json,
                "Layout-quality audit for draft Markdown/SVG visual-table candidates.",
            ),
        ):
            if not sidecar_path.exists():
                continue
            add_node(
                nodes,
                sidecar_id,
                "report",
                json_path=str(sidecar_path),
                summary=sidecar_summary,
            )
            add_edge(edges, sidecar_id, methodology_report_id, "SUPPORTS_REPORT")
            add_edge(
                edges,
                sidecar_id,
                render_report_id,
                "DERIVED_FROM",
                evidence_path=str(sidecar_path),
                evidence="$.sources",
            )

    publication_retention_readiness_md = (
        publication_retention_readiness_audit_json.with_suffix(".md")
    )
    if publication_retention_readiness_audit_json.exists():
        retention_report_id = "report:publication_retention_readiness_audit"
        add_node(
            nodes,
            retention_report_id,
            "report",
            path=(
                str(publication_retention_readiness_md)
                if publication_retention_readiness_md.exists()
                else None
            ),
            json_path=str(publication_retention_readiness_audit_json),
            summary=(
                "Pre-manuscript article/supplement/KG retention-readiness "
                "recommendation audit; candidate placement recommendations are "
                "ready while final retained artifacts, final prose, KG citation, "
                "site deployment, and positive claims remain unauthorized."
            ),
        )
        add_edge(
            edges,
            retention_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(publication_retention_readiness_audit_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:publication_visual_table_render_candidate_audit",
                "$.sources.visual_table_render_candidate_audit",
            ),
            (
                "report:visual_table_layout_quality_audit",
                "$.sources.visual_table_layout_quality_audit",
            ),
            (
                "report:reviewer_design_reconciliation",
                "$.sources.reviewer_design_brief",
            ),
            (
                "report:neutral_result_ledger",
                "$.sources.neutral_result_ledger",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
        ):
            add_edge(
                edges,
                retention_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(publication_retention_readiness_audit_json),
                evidence=selector,
            )
        try:
            retention_payload = json.loads(
                publication_retention_readiness_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            retention_payload = {}
        for row_index, row in enumerate(retention_payload.get("recommendation_rows") or []):
            content_id = str(row.get("content_area_id") or "").strip()
            if not content_id:
                continue
            node_id = (
                "methodology_control:publication_retention_recommendation:"
                f"{slug_fragment(content_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=content_id,
                artifact_type=row.get("artifact_type"),
                recommendation_status=row.get("recommendation_status"),
                recommended_surface=row.get("recommended_surface"),
                retention_readiness_decision=row.get(
                    "retention_readiness_decision"
                ),
                final_retention_authorized=row.get("final_retention_authorized"),
                final_visual_table_retention_authorized=row.get(
                    "final_visual_table_retention_authorized"
                ),
                final_manuscript_prose_permission=row.get(
                    "final_manuscript_prose_permission"
                ),
                publication_site_deployment_authorized=row.get(
                    "publication_site_deployment_authorized"
                ),
                kg_citable_component_authorized=row.get(
                    "kg_citable_component_authorized"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                source_traceability_artifact_status=row.get(
                    "source_traceability_artifact_status"
                ),
                primary_rendered_artifact_path=row.get(
                    "primary_rendered_artifact_path"
                ),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Publication retention-readiness recommendation "
                    f"`{content_id}` is `{row.get('recommended_surface')}` with "
                    "no final retention, release, or positive claim authorized."
                ),
            )
            add_edge(
                edges,
                retention_report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_retention_readiness_audit_json),
                evidence=row_selector(
                    "recommendation_rows", row_index, "content_area_id"
                ),
            )
            render_node_id = (
                "methodology_control:publication_visual_table_render_candidate:"
                f"{slug_fragment(content_id)}"
            )
            add_edge(
                edges,
                node_id,
                render_node_id,
                "DERIVED_FROM",
                evidence_path=str(publication_retention_readiness_audit_json),
                evidence=row_selector(
                    "recommendation_rows", row_index, "content_area_id"
                ),
            )
        if article_supplement_retention_recommendation_matrix_json.exists():
            matrix_id = "report:article_supplement_retention_recommendation_matrix"
            add_node(
                nodes,
                matrix_id,
                "report",
                json_path=str(article_supplement_retention_recommendation_matrix_json),
                summary=(
                    "Article/supplement/KG retention recommendation matrix; "
                    "recommendation rows are not final retained artifacts."
                ),
            )
            add_edge(
                edges,
                matrix_id,
                methodology_report_id,
                "SUPPORTS_REPORT",
                evidence_path=str(
                    article_supplement_retention_recommendation_matrix_json
                ),
                evidence="$.summary",
            )
            add_edge(
                edges,
                matrix_id,
                retention_report_id,
                "SUPPORTS_REPORT",
                evidence_path=str(
                    article_supplement_retention_recommendation_matrix_json
                ),
                evidence="$.summary",
            )
            add_edge(
                edges,
                matrix_id,
                retention_report_id,
                "DERIVED_FROM",
                evidence_path=str(
                    article_supplement_retention_recommendation_matrix_json
                ),
                evidence="$.sources",
            )

    final_visual_auditor_md = (
        final_publication_visual_auditor_readiness_json.with_suffix(".md")
    )
    if final_publication_visual_auditor_readiness_json.exists():
        final_visual_report_id = "report:final_publication_visual_auditor_readiness"
        add_node(
            nodes,
            final_visual_report_id,
            "report",
            path=(
                str(final_visual_auditor_md)
                if final_visual_auditor_md.exists()
                else None
            ),
            json_path=str(final_publication_visual_auditor_readiness_json),
            summary=(
                "Final publication visual/table auditor feedback-loop readiness "
                "artifact; draft candidates are checked for layout, caption, "
                "provenance, reader value, and claim-boundary readiness while "
                "final retention, final prose, release, method recommendation, "
                "and positive-claim promotion remain unauthorized."
            ),
        )
        add_edge(
            edges,
            final_visual_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(final_publication_visual_auditor_readiness_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:publication_visual_table_render_candidate_audit",
                "$.sources.visual_table_render_candidate_audit",
            ),
            (
                "report:publication_retention_readiness_audit",
                "$.sources.publication_retention_readiness_audit",
            ),
            (
                "report:publication_visual_table_audit_report",
                "$.sources.visual_table_audit_report",
            ),
            (
                "report:reviewer_design_reconciliation",
                "$.sources.reviewer_design_brief",
            ),
            (
                "report:section_claim_boundary_audit",
                "$.sources.section_claim_boundary_audit",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.publication_release_gap_register",
            ),
        ):
            add_edge(
                edges,
                final_visual_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(final_publication_visual_auditor_readiness_json),
                evidence=selector,
            )
        try:
            final_visual_payload = json.loads(
                final_publication_visual_auditor_readiness_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            final_visual_payload = {}
        final_visual_source_node_ids = {
            "visual_table_render_candidate_audit.json": (
                "report:publication_visual_table_render_candidate_audit"
            ),
            "publication_retention_readiness_audit.json": (
                "report:publication_retention_readiness_audit"
            ),
            "visual_table_audit_report.json": (
                "report:publication_visual_table_audit_report"
            ),
            "reviewer_design_brief.json": "report:reviewer_design_reconciliation",
            "section_claim_boundary_audit.json": (
                "report:section_claim_boundary_audit"
            ),
            "neutral_reporting_language_audit.json": (
                "report:neutral_reporting_language_audit"
            ),
            "publication_release_gap_register.json": (
                "report:publication_release_gap_register"
            ),
        }
        for row_index, row in enumerate(
            final_visual_payload.get("visual_auditor_feedback_rows") or []
        ):
            content_id = str(row.get("content_area_id") or "").strip()
            if not content_id:
                continue
            node_id = (
                "methodology_control:final_publication_visual_auditor:"
                f"{slug_fragment(content_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=content_id,
                artifact_type=row.get("artifact_type"),
                recommended_surface=row.get("recommended_surface"),
                visual_auditor_feedback_status=row.get(
                    "visual_auditor_feedback_status"
                ),
                feedback_item_count=row.get("feedback_item_count"),
                layout_quality_status=row.get("layout_quality_status"),
                caption_quality_status=row.get("caption_quality_status"),
                source_traceability_status=row.get("source_traceability_status"),
                svg_static_text_overlap_detected=row.get(
                    "svg_static_text_overlap_detected"
                ),
                final_retention_authorized=False,
                final_visual_table_retention_authorized=False,
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                positive_claim_promotion_authorized=False,
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Final publication visual auditor feedback row "
                    f"`{content_id}` is `{row.get('visual_auditor_feedback_status')}` "
                    "with final retention and positive-claim promotion blocked."
                ),
            )
            add_edge(
                edges,
                final_visual_report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(final_publication_visual_auditor_readiness_json),
                evidence=row_selector(
                    "visual_auditor_feedback_rows", row_index, "content_area_id"
                ),
            )
            for source_path in row.get("source_artifacts") or []:
                source_node_id = final_visual_source_node_ids.get(
                    Path(str(source_path)).name
                )
                if source_node_id:
                    add_edge(
                        edges,
                        node_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(
                            final_publication_visual_auditor_readiness_json
                        ),
                        evidence=(
                            f"$.visual_auditor_feedback_rows[{row_index}]"
                            ".source_artifacts"
                        ),
                    )
            retention_node_id = (
                "methodology_control:publication_retention_recommendation:"
                f"{slug_fragment(content_id)}"
            )
            add_edge(
                edges,
                node_id,
                retention_node_id,
                "DERIVED_FROM",
                evidence_path=str(final_publication_visual_auditor_readiness_json),
                evidence=row_selector(
                    "visual_auditor_feedback_rows", row_index, "content_area_id"
                ),
            )

    article_supplement_blueprint_alignment_md = (
        article_supplement_blueprint_alignment_json.with_suffix(".md")
    )
    if article_supplement_blueprint_alignment_json.exists():
        alignment_report_id = "report:article_supplement_blueprint_alignment"
        add_node(
            nodes,
            alignment_report_id,
            "report",
            path=(
                str(article_supplement_blueprint_alignment_md)
                if article_supplement_blueprint_alignment_md.exists()
                else None
            ),
            json_path=str(article_supplement_blueprint_alignment_json),
            summary=(
                "Neutral article/supplement/KG blueprint-alignment audit; "
                "candidate surfaces are linked to reviewer advice, retention "
                "recommendations, neutral result boundaries, and activation "
                "gates without final prose, method recommendation, or positive "
                "claim promotion."
            ),
        )
        add_edge(
            edges,
            alignment_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(article_supplement_blueprint_alignment_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:reviewer_design_reconciliation",
                "$.sources.reviewer_design_brief",
            ),
            (
                "report:publication_retention_readiness_audit",
                "$.sources.publication_retention_readiness_audit",
            ),
            (
                "report:article_supplement_retention_recommendation_matrix",
                "$.sources.article_supplement_retention_recommendation_matrix",
            ),
            ("report:neutral_result_ledger", "$.sources.neutral_result_ledger"),
            (
                "report:post_experiment_publication_activation_audit",
                "$.sources.post_experiment_publication_activation_audit",
            ),
            ("report:manuscript_readiness_map", "$.sources.paper_readiness_map"),
            ("report:paper_gate_closure_map", "$.sources.paper_gate_closure_map"),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
        ):
            add_edge(
                edges,
                alignment_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(article_supplement_blueprint_alignment_json),
                evidence=selector,
            )
        try:
            alignment_payload = json.loads(
                article_supplement_blueprint_alignment_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            alignment_payload = {}
        for row_index, row in enumerate(
            alignment_payload.get("alignment_rows") or []
        ):
            content_id = str(row.get("content_area_id") or "").strip()
            if not content_id:
                continue
            node_id = (
                "methodology_control:article_supplement_blueprint_alignment:"
                f"{slug_fragment(content_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=content_id,
                artifact_type=row.get("artifact_type"),
                recommended_surface=row.get("recommended_surface"),
                reviewer_alignment_status=row.get("reviewer_alignment_status"),
                linked_neutral_result_count=row.get("linked_neutral_result_count"),
                scientific_reporting_role=row.get("scientific_reporting_role"),
                retention_recommendation_status=row.get(
                    "retention_recommendation_status"
                ),
                source_traceability_status=row.get("source_traceability_status"),
                final_retention_authorized=row.get("final_retention_authorized"),
                final_visual_table_retention_authorized=row.get(
                    "final_visual_table_retention_authorized"
                ),
                final_manuscript_prose_permission=row.get(
                    "final_manuscript_prose_permission"
                ),
                publication_site_deployment_authorized=row.get(
                    "publication_site_deployment_authorized"
                ),
                kg_citable_component_authorized=row.get(
                    "kg_citable_component_authorized"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                sterile_repository_creation_authorized=row.get(
                    "sterile_repository_creation_authorized"
                ),
                method_recommendation_authorized=row.get(
                    "method_recommendation_authorized"
                ),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Article/supplement blueprint alignment row "
                    f"`{content_id}` has role "
                    f"`{row.get('scientific_reporting_role')}` and keeps final "
                    "prose, method recommendation, and positive claims unauthorized."
                ),
            )
            add_edge(
                edges,
                alignment_report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(article_supplement_blueprint_alignment_json),
                evidence=row_selector("alignment_rows", row_index, "content_area_id"),
            )
            retention_node_id = (
                "methodology_control:publication_retention_recommendation:"
                f"{slug_fragment(content_id)}"
            )
            add_edge(
                edges,
                node_id,
                retention_node_id,
                "DERIVED_FROM",
                evidence_path=str(article_supplement_blueprint_alignment_json),
                evidence=row_selector("alignment_rows", row_index, "content_area_id"),
            )
            for result_id in row.get("neutral_result_ids") or []:
                result_node_id = (
                    "methodology_control:neutral_result_ledger:"
                    f"{slug_fragment(str(result_id))}"
                )
                add_edge(
                    edges,
                    node_id,
                    result_node_id,
                    "DERIVED_FROM",
                    evidence_path=str(article_supplement_blueprint_alignment_json),
                    evidence=(
                        f"$.alignment_rows[{row_index}].neutral_result_ids"
                        f"[?(@ == {json.dumps(str(result_id))})]"
                    ),
                )
        for surface_index, surface in enumerate(
            alignment_payload.get("surface_rows") or []
        ):
            surface_id = str(surface.get("surface_id") or "").strip()
            if not surface_id:
                continue
            surface_node_id = (
                "methodology_control:article_supplement_blueprint_surface:"
                f"{slug_fragment(surface_id)}"
            )
            add_node(
                nodes,
                surface_node_id,
                "methodology_control",
                name=surface_id,
                candidate_content_area_count=surface.get(
                    "candidate_content_area_count"
                ),
                final_manuscript_prose_permission=surface.get(
                    "final_manuscript_prose_permission"
                ),
                final_visual_table_retention_authorized=surface.get(
                    "final_visual_table_retention_authorized"
                ),
                publication_site_deployment_authorized=surface.get(
                    "publication_site_deployment_authorized"
                ),
                kg_citable_component_authorized=surface.get(
                    "kg_citable_component_authorized"
                ),
                positive_claim_promotion_authorized=surface.get(
                    "positive_claim_promotion_authorized"
                ),
                sterile_repository_creation_authorized=surface.get(
                    "sterile_repository_creation_authorized"
                ),
                claim_boundary=surface.get("claim_boundary"),
                summary=(
                    "Article/supplement/KG blueprint surface "
                    f"`{surface_id}` is candidate-only with final release and "
                    "positive claims unauthorized."
                ),
            )
            add_edge(
                edges,
                alignment_report_id,
                surface_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(article_supplement_blueprint_alignment_json),
                evidence=row_selector("surface_rows", surface_index, "surface_id"),
            )

    publication_release_gap_register_md = (
        publication_release_gap_register_json.with_suffix(".md")
    )
    if publication_release_gap_register_json.exists():
        release_gap_report_id = "report:publication_release_gap_register"
        add_node(
            nodes,
            release_gap_report_id,
            "report",
            path=(
                str(publication_release_gap_register_md)
                if publication_release_gap_register_md.exists()
                else None
            ),
            json_path=str(publication_release_gap_register_json),
            summary=(
                "Neutral publication release-gap register; maps article, "
                "supplement, KG/site, individual report, and sterile repository "
                "deliverables to blocked release gates without final prose, "
                "method recommendation, positive claim promotion, or sterile "
                "repository creation."
            ),
        )
        add_edge(
            edges,
            release_gap_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(publication_release_gap_register_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_experiment_publication_program",
            ),
            ("report:goal_completion_audit", "$.sources.goal_completion_audit"),
            (
                "report:post_experiment_publication_activation_audit",
                "$.sources.post_experiment_publication_activation_audit",
            ),
            ("report:manuscript_readiness_map", "$.sources.paper_readiness_map"),
            ("report:paper_gate_closure_map", "$.sources.paper_gate_closure_map"),
            (
                "report:article_supplement_blueprint_alignment",
                "$.sources.article_supplement_blueprint_alignment",
            ),
            (
                "report:publication_retention_readiness_audit",
                "$.sources.publication_retention_readiness_audit",
            ),
            (
                "report:publication_visual_table_audit_report",
                "$.sources.visual_table_audit_report",
            ),
            (
                "report:kg_publication_quality_audit",
                "$.sources.kg_publication_quality_audit",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
        ):
            add_edge(
                edges,
                release_gap_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(publication_release_gap_register_json),
                evidence=selector,
            )
        try:
            release_gap_payload = json.loads(
                publication_release_gap_register_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            release_gap_payload = {}
        for row_index, row in enumerate(release_gap_payload.get("deliverable_rows") or []):
            deliverable_id = str(row.get("deliverable_id") or "").strip()
            if not deliverable_id:
                continue
            control_id = (
                "methodology_control:publication_release_gap:"
                f"{slug_fragment(deliverable_id)}"
            )
            add_node(
                nodes,
                control_id,
                "methodology_control",
                name=deliverable_id,
                family=row.get("family"),
                format=row.get("format"),
                pre_prose_evidence_ready=row.get("pre_prose_evidence_ready"),
                release_status=row.get("release_status"),
                release_authorized=row.get("release_authorized"),
                release_blocker_count=row.get("release_blocker_count"),
                source_traceability_status=row.get("source_traceability_status"),
                final_manuscript_prose_permission=row.get(
                    "final_manuscript_prose_permission"
                ),
                final_visual_table_retention_authorized=row.get(
                    "final_visual_table_retention_authorized"
                ),
                publication_site_deployment_authorized=row.get(
                    "publication_site_deployment_authorized"
                ),
                kg_citable_component_authorized=row.get(
                    "kg_citable_component_authorized"
                ),
                sterile_repository_creation_authorized=row.get(
                    "sterile_repository_creation_authorized"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                method_recommendation_authorized=row.get(
                    "method_recommendation_authorized"
                ),
                working_repository_final_citable=row.get(
                    "working_repository_final_citable"
                ),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Publication release-gap row "
                    f"`{deliverable_id}` is `{row.get('release_status')}`; "
                    "release, final prose, sterile repository creation, method "
                    "recommendation, and positive claims remain unauthorized."
                ),
            )
            add_edge(
                edges,
                release_gap_report_id,
                control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_release_gap_register_json),
                evidence=row_selector("deliverable_rows", row_index, "deliverable_id"),
            )
            deliverable_node_id = f"publication_deliverable:{slug_fragment(deliverable_id)}"
            add_edge(
                edges,
                release_gap_report_id,
                deliverable_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_release_gap_register_json),
                evidence=row_selector("deliverable_rows", row_index, "deliverable_id"),
            )
            for blocker_index, blocker in enumerate(row.get("release_blockers") or []):
                blocker_id = (
                    "methodology_control:publication_release_blocker:"
                    f"{slug_fragment(str(blocker))}"
                )
                add_node(
                    nodes,
                    blocker_id,
                    "methodology_control",
                    name=str(blocker),
                    summary=(
                        "Reusable publication release blocker recorded by the "
                        "release-gap register."
                    ),
                )
                add_edge(
                    edges,
                    control_id,
                    blocker_id,
                    "DERIVED_FROM",
                    evidence_path=str(publication_release_gap_register_json),
                    evidence=(
                        f"$.deliverable_rows[{row_index}].release_blockers"
                        f"[{blocker_index}]"
                    ),
                )

    individual_report_blueprint_md = (
        individual_experiment_report_blueprint_json.with_suffix(".md")
    )
    if individual_experiment_report_blueprint_json.exists():
        individual_report_blueprint_id = (
            "report:individual_experiment_report_blueprint"
        )
        add_node(
            nodes,
            individual_report_blueprint_id,
            "report",
            path=(
                str(individual_report_blueprint_md)
                if individual_report_blueprint_md.exists()
                else None
            ),
            json_path=str(individual_experiment_report_blueprint_json),
            summary=(
                "Author-stamped neutral individual experiment report blueprint; "
                "maps report sections to source artifacts and neutral result "
                "boundaries without final prose, release authorization, method "
                "recommendation, or positive claim promotion."
            ),
        )
        add_edge(
            edges,
            individual_report_blueprint_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(individual_experiment_report_blueprint_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_program",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.release_gap",
            ),
            ("report:goal_completion_audit", "$.sources.goal_completion"),
            (
                "report:post_experiment_publication_activation_audit",
                "$.sources.activation",
            ),
            ("report:manuscript_readiness_map", "$.sources.paper_readiness"),
            (
                "report:article_supplement_blueprint_alignment",
                "$.sources.blueprint_alignment",
            ),
            ("report:neutral_result_ledger", "$.sources.neutral_ledger"),
            ("report:experiment_accounting_audit", "$.sources.experiment_accounting"),
            ("report:method_performance_synthesis", "$.sources.method_performance"),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.kg_quality",
            ),
            ("report:kg_publication_quality_audit", "$.sources.kg_publication"),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_language",
            ),
        ):
            add_edge(
                edges,
                individual_report_blueprint_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(individual_experiment_report_blueprint_json),
                evidence=selector,
            )
        add_edge(
            edges,
            individual_report_blueprint_id,
            "publication_deliverable:individual_experiment_report",
            "SUMMARIZES_CONTROL",
            evidence_path=str(individual_experiment_report_blueprint_json),
            evidence="$.summary.deliverable_registered",
        )
        try:
            individual_report_payload = json.loads(
                individual_experiment_report_blueprint_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            individual_report_payload = {}
        for row_index, row in enumerate(
            individual_report_payload.get("section_rows") or []
        ):
            section_id = str(row.get("section_id") or "").strip()
            if not section_id:
                continue
            section_node_id = (
                "methodology_control:individual_experiment_report_blueprint:"
                f"{slug_fragment(section_id)}"
            )
            add_node(
                nodes,
                section_node_id,
                "methodology_control",
                name=section_id,
                title=row.get("title"),
                section_role=row.get("section_role"),
                source_traceability_status=row.get("source_traceability_status"),
                linked_neutral_result_count=row.get(
                    "linked_neutral_result_count"
                ),
                final_report_prose_permission=row.get(
                    "final_report_prose_permission"
                ),
                latex_output_authorized=row.get("latex_output_authorized"),
                html_output_authorized=row.get("html_output_authorized"),
                markdown_output_authorized=row.get("markdown_output_authorized"),
                release_authorized=row.get("release_authorized"),
                sterile_repository_creation_authorized=row.get(
                    "sterile_repository_creation_authorized"
                ),
                working_repository_final_citable=row.get(
                    "working_repository_final_citable"
                ),
                method_recommendation_authorized=row.get(
                    "method_recommendation_authorized"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                section_decision_scope=row.get("section_decision_scope"),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Individual experiment report blueprint section "
                    f"`{section_id}` has role `{row.get('section_role')}` and "
                    "keeps final prose, release, method recommendation, and "
                    "positive claims unauthorized."
                ),
            )
            add_edge(
                edges,
                individual_report_blueprint_id,
                section_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(individual_experiment_report_blueprint_json),
                evidence=row_selector("section_rows", row_index, "section_id"),
            )
            for result_id in row.get("neutral_result_ids") or []:
                result_node_id = (
                    "methodology_control:neutral_result_ledger:"
                    f"{slug_fragment(str(result_id))}"
                )
                add_edge(
                    edges,
                    section_node_id,
                    result_node_id,
                    "DERIVED_FROM",
                    evidence_path=str(individual_experiment_report_blueprint_json),
                    evidence=(
                        f"$.section_rows[{row_index}].neutral_result_ids"
                        f"[?(@ == {json.dumps(str(result_id))})]"
                    ),
                )

    claim_safe_result_extraction_matrix_md = (
        claim_safe_result_extraction_matrix_json.with_suffix(".md")
    )
    if claim_safe_result_extraction_matrix_json.exists():
        claim_safe_matrix_id = "report:claim_safe_result_extraction_matrix"
        add_node(
            nodes,
            claim_safe_matrix_id,
            "report",
            path=(
                str(claim_safe_result_extraction_matrix_md)
                if claim_safe_result_extraction_matrix_md.exists()
                else None
            ),
            json_path=str(claim_safe_result_extraction_matrix_json),
            summary=(
                "Claim-safe pre-prose result extraction matrix; maps "
                "paper-facing result surfaces to source artifacts, neutral "
                "result boundaries, blocked main-result status, and negative "
                "Venn-Abers reporting scope without final prose, method "
                "recommendation, positive claim promotion, or release."
            ),
        )
        add_edge(
            edges,
            claim_safe_matrix_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(claim_safe_result_extraction_matrix_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            ("report:manuscript_readiness_map", "$.sources.paper_readiness"),
            ("report:paper_gate_closure_map", "$.sources.paper_gate_closure"),
            ("report:neutral_result_ledger", "$.sources.neutral_ledger"),
            (
                "report:article_supplement_blueprint_alignment",
                "$.sources.blueprint_alignment",
            ),
            (
                "report:individual_experiment_report_blueprint",
                "$.sources.individual_report_blueprint",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.release_gap",
            ),
            (
                "report:publication_retention_readiness_audit",
                "$.sources.retention_readiness",
            ),
            (
                "report:publication_visual_table_render_candidate_audit",
                "$.sources.visual_render_audit",
            ),
            ("report:kg_publication_quality_audit", "$.sources.kg_publication"),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_language",
            ),
            ("report:experiment_accounting_audit", "$.sources.experiment_accounting"),
            ("report:method_performance_synthesis", "$.sources.method_performance"),
            (
                "report:venn_abers_negative_evidence_disposition_audit",
                "$.sources.venn_abers_negative",
            ),
            (
                "report:final_selection_claim_boundary_audit",
                "$.sources.final_selection",
            ),
        ):
            add_edge(
                edges,
                claim_safe_matrix_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(claim_safe_result_extraction_matrix_json),
                evidence=selector,
            )
        try:
            claim_safe_payload = json.loads(
                claim_safe_result_extraction_matrix_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            claim_safe_payload = {}
        for row_index, row in enumerate(claim_safe_payload.get("surface_rows") or []):
            surface_id = str(row.get("surface_id") or "").strip()
            if not surface_id:
                continue
            surface_node_id = (
                "methodology_control:claim_safe_result_extraction:"
                f"{slug_fragment(surface_id)}"
            )
            add_node(
                nodes,
                surface_node_id,
                "methodology_control",
                name=surface_id,
                surface_family=row.get("surface_family"),
                surface_role=row.get("surface_role"),
                pre_prose_extraction_status=row.get("pre_prose_extraction_status"),
                claim_scope=row.get("claim_scope"),
                safe_pre_prose_extraction_candidate=row.get(
                    "safe_pre_prose_extraction_candidate"
                ),
                positive_claim_surface_blocked=row.get(
                    "positive_claim_surface_blocked"
                ),
                source_traceability_status=row.get("source_traceability_status"),
                linked_neutral_result_count=row.get(
                    "linked_neutral_result_count"
                ),
                final_manuscript_prose_permission=row.get(
                    "final_manuscript_prose_permission"
                ),
                final_visual_table_retention_authorized=row.get(
                    "final_visual_table_retention_authorized"
                ),
                release_authorized=row.get("release_authorized"),
                publication_site_deployment_authorized=row.get(
                    "publication_site_deployment_authorized"
                ),
                kg_citable_component_authorized=row.get(
                    "kg_citable_component_authorized"
                ),
                sterile_repository_creation_authorized=row.get(
                    "sterile_repository_creation_authorized"
                ),
                working_repository_final_citable=row.get(
                    "working_repository_final_citable"
                ),
                method_recommendation_authorized=row.get(
                    "method_recommendation_authorized"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Claim-safe result extraction surface "
                    f"`{surface_id}` has status "
                    f"`{row.get('pre_prose_extraction_status')}` and keeps "
                    "final prose, final visual/table retention, release, "
                    "method recommendation, and positive claims unauthorized."
                ),
            )
            add_edge(
                edges,
                claim_safe_matrix_id,
                surface_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(claim_safe_result_extraction_matrix_json),
                evidence=row_selector("surface_rows", row_index, "surface_id"),
            )
            surface_family = str(row.get("surface_family") or "")
            if surface_family in {
                "main_article",
                "supplementary_document",
                "kg_or_publication_site",
            }:
                add_edge(
                    edges,
                    surface_node_id,
                    (
                        "methodology_control:article_supplement_blueprint_surface:"
                        f"{slug_fragment(surface_family)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(claim_safe_result_extraction_matrix_json),
                    evidence=row_selector("surface_rows", row_index, "surface_family"),
                )
            for result_id in row.get("neutral_result_ids") or []:
                result_node_id = (
                    "methodology_control:neutral_result_ledger:"
                    f"{slug_fragment(str(result_id))}"
                )
                add_edge(
                    edges,
                    surface_node_id,
                    result_node_id,
                    "DERIVED_FROM",
                    evidence_path=str(claim_safe_result_extraction_matrix_json),
                    evidence=(
                        f"$.surface_rows[{row_index}].neutral_result_ids"
                        f"[?(@ == {json.dumps(str(result_id))})]"
                    ),
                )

    manuscript_section_evidence_packet_md = (
        manuscript_section_evidence_packet_json.with_suffix(".md")
    )
    if manuscript_section_evidence_packet_json.exists():
        section_packet_report_id = "report:manuscript_section_evidence_packet"
        add_node(
            nodes,
            section_packet_report_id,
            "report",
            path=(
                str(manuscript_section_evidence_packet_md)
                if manuscript_section_evidence_packet_md.exists()
                else None
            ),
            json_path=str(manuscript_section_evidence_packet_json),
            summary=(
                "Neutral pre-prose manuscript section evidence packet; maps "
                "paper, supplement, and individual-report section packets to "
                "claim-safe surfaces, neutral result rows, source artifacts, "
                "and blocked final-output permissions without method promotion."
            ),
        )
        add_edge(
            edges,
            section_packet_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(manuscript_section_evidence_packet_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:claim_safe_result_extraction_matrix",
                "$.sources.claim_safe_matrix",
            ),
            ("report:neutral_result_ledger", "$.sources.neutral_ledger"),
            (
                "report:article_supplement_blueprint_alignment",
                "$.sources.blueprint_alignment",
            ),
            (
                "report:individual_experiment_report_blueprint",
                "$.sources.individual_report_blueprint",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.release_gap",
            ),
            (
                "report:publication_retention_readiness_audit",
                "$.sources.retention_readiness",
            ),
            (
                "report:publication_visual_table_render_candidate_audit",
                "$.sources.visual_render_audit",
            ),
            (
                "report:reader_method_primer_citation_map",
                "$.sources.reader_primer",
            ),
            (
                "report:reader_primer_section_alignment",
                "$.sources.reader_primer_alignment",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_language",
            ),
            ("report:kg_publication_quality_audit", "$.sources.kg_publication"),
            ("report:experiment_accounting_audit", "$.sources.experiment_accounting"),
            ("report:method_performance_synthesis", "$.sources.method_performance"),
            (
                "report:venn_abers_negative_evidence_disposition_audit",
                "$.sources.venn_abers_negative",
            ),
            ("report:goal_completion_audit", "$.sources.goal_completion"),
        ):
            add_edge(
                edges,
                section_packet_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(manuscript_section_evidence_packet_json),
                evidence=selector,
            )
        try:
            section_packet_payload = json.loads(
                manuscript_section_evidence_packet_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            section_packet_payload = {}
        for row_index, row in enumerate(
            section_packet_payload.get("section_packet_rows") or []
        ):
            packet_id = str(row.get("packet_id") or "").strip()
            if not packet_id:
                continue
            packet_node_id = (
                "methodology_control:manuscript_section_evidence_packet:"
                f"{slug_fragment(packet_id)}"
            )
            add_node(
                nodes,
                packet_node_id,
                "methodology_control",
                name=packet_id,
                target_document=row.get("target_document"),
                section_role=row.get("section_role"),
                packet_status=row.get("packet_status"),
                claim_safe_surface_id=row.get("claim_safe_surface_id"),
                claim_safe_surface_status=row.get("claim_safe_surface_status"),
                safe_pre_prose_evidence_packet=row.get(
                    "safe_pre_prose_evidence_packet"
                ),
                positive_claim_packet_blocked=row.get(
                    "positive_claim_packet_blocked"
                ),
                source_traceability_status=row.get("source_traceability_status"),
                linked_neutral_result_count=row.get(
                    "linked_neutral_result_count"
                ),
                reader_concept_ids=row.get("reader_concept_ids") or [],
                reader_concept_count=row.get("reader_concept_count"),
                paragraph_blueprint=row.get("paragraph_blueprint") or [],
                paragraph_blueprint_step_count=row.get(
                    "paragraph_blueprint_step_count"
                ),
                final_section_prose_authorized=row.get(
                    "final_section_prose_authorized"
                ),
                final_manuscript_prose_permission=row.get(
                    "final_manuscript_prose_permission"
                ),
                final_visual_table_retention_authorized=row.get(
                    "final_visual_table_retention_authorized"
                ),
                release_authorized=row.get("release_authorized"),
                sterile_repository_creation_authorized=row.get(
                    "sterile_repository_creation_authorized"
                ),
                working_repository_final_citable=row.get(
                    "working_repository_final_citable"
                ),
                method_recommendation_authorized=row.get(
                    "method_recommendation_authorized"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Manuscript section evidence packet "
                    f"`{packet_id}` targets `{row.get('target_document')}` with "
                    f"status `{row.get('packet_status')}` and keeps final "
                    "prose, release, method recommendation, and positive "
                    "claims unauthorized."
                ),
            )
            add_edge(
                edges,
                section_packet_report_id,
                packet_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(manuscript_section_evidence_packet_json),
                evidence=row_selector("section_packet_rows", row_index, "packet_id"),
            )
            surface_id = str(row.get("claim_safe_surface_id") or "").strip()
            if surface_id:
                add_edge(
                    edges,
                    packet_node_id,
                    (
                        "methodology_control:claim_safe_result_extraction:"
                        f"{slug_fragment(surface_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(manuscript_section_evidence_packet_json),
                    evidence=row_selector(
                        "section_packet_rows", row_index, "claim_safe_surface_id"
                    ),
                )
            for result_id in row.get("neutral_result_ids") or []:
                result_node_id = (
                    "methodology_control:neutral_result_ledger:"
                    f"{slug_fragment(str(result_id))}"
                )
                add_edge(
                    edges,
                    packet_node_id,
                    result_node_id,
                    "DERIVED_FROM",
                    evidence_path=str(manuscript_section_evidence_packet_json),
                    evidence=(
                        f"$.section_packet_rows[{row_index}].neutral_result_ids"
                        f"[?(@ == {json.dumps(str(result_id))})]"
                    ),
                )
            for concept_id in row.get("reader_concept_ids") or []:
                add_edge(
                    edges,
                    packet_node_id,
                    (
                        "methodology_control:reader_method_primer:"
                        f"{slug_fragment(str(concept_id))}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(manuscript_section_evidence_packet_json),
                    evidence=(
                        f"$.section_packet_rows[{row_index}].reader_concept_ids"
                        f"[?(@ == {json.dumps(str(concept_id))})]"
                    ),
                )

    section_claim_boundary_audit_md = section_claim_boundary_audit_json.with_suffix(
        ".md"
    )
    if section_claim_boundary_audit_json.exists():
        boundary_report_id = "report:section_claim_boundary_audit"
        add_node(
            nodes,
            boundary_report_id,
            "report",
            path=(
                str(section_claim_boundary_audit_md)
                if section_claim_boundary_audit_md.exists()
                else None
            ),
            json_path=str(section_claim_boundary_audit_json),
            summary=(
                "Section-level claim-boundary audit linking manuscript section "
                "packets to allowed/blocked-use text, claim-safe surfaces, "
                "neutral-result rows, and blocked release targets without "
                "final prose or method promotion."
            ),
        )
        add_edge(
            edges,
            boundary_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(section_claim_boundary_audit_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:manuscript_section_evidence_packet",
                "$.sources.section_packet",
            ),
            (
                "report:claim_safe_result_extraction_matrix",
                "$.sources.claim_safe_matrix",
            ),
            ("report:neutral_result_ledger", "$.sources.neutral_ledger"),
            (
                "report:publication_release_gap_register",
                "$.sources.release_gap",
            ),
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_experiment_publication_program",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_language",
            ),
            (
                "report:venn_abers_negative_evidence_disposition_audit",
                "$.sources.venn_abers_negative",
            ),
        ):
            add_edge(
                edges,
                boundary_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(section_claim_boundary_audit_json),
                evidence=selector,
            )
        try:
            boundary_payload = json.loads(
                section_claim_boundary_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            boundary_payload = {}
        for row_index, row in enumerate(boundary_payload.get("boundary_rows") or []):
            packet_id = str(row.get("packet_id") or "").strip()
            if not packet_id:
                continue
            boundary_node_id = (
                "methodology_control:section_claim_boundary_audit:"
                f"{slug_fragment(packet_id)}"
            )
            add_node(
                nodes,
                boundary_node_id,
                "methodology_control",
                name=packet_id,
                target_document=row.get("target_document"),
                boundary_status=row.get("boundary_status"),
                scientific_reporting_role=row.get("scientific_reporting_role"),
                claim_safe_surface_id=row.get("claim_safe_surface_id"),
                claim_safe_surface_status=row.get("claim_safe_surface_status"),
                release_target_deliverable_ids=row.get(
                    "release_target_deliverable_ids"
                ),
                linked_release_target_count=row.get("linked_release_target_count"),
                boundary_complete=row.get("boundary_complete"),
                section_boundary_backfills_ledger_gap=row.get(
                    "section_boundary_backfills_ledger_gap"
                ),
                release_targets_blocked=row.get("release_targets_blocked"),
                main_positive_boundary_blocked=row.get(
                    "main_positive_boundary_blocked"
                ),
                venn_abers_negative_boundary_preserved=row.get(
                    "venn_abers_negative_boundary_preserved"
                ),
                method_recommendation_authorized=row.get(
                    "method_recommendation_authorized"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                release_authorized=row.get("release_authorized"),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Section claim-boundary audit row "
                    f"`{packet_id}` has status `{row.get('boundary_status')}` "
                    "and keeps final prose, release, method recommendation, "
                    "and positive claims unauthorized."
                ),
            )
            add_edge(
                edges,
                boundary_report_id,
                boundary_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(section_claim_boundary_audit_json),
                evidence=row_selector("boundary_rows", row_index, "packet_id"),
            )
            add_edge(
                edges,
                boundary_node_id,
                (
                    "methodology_control:manuscript_section_evidence_packet:"
                    f"{slug_fragment(packet_id)}"
                ),
                "DERIVED_FROM",
                evidence_path=str(section_claim_boundary_audit_json),
                evidence=row_selector("boundary_rows", row_index, "packet_id"),
            )
            surface_id = str(row.get("claim_safe_surface_id") or "").strip()
            if surface_id:
                add_edge(
                    edges,
                    boundary_node_id,
                    (
                        "methodology_control:claim_safe_result_extraction:"
                        f"{slug_fragment(surface_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(section_claim_boundary_audit_json),
                    evidence=row_selector(
                        "boundary_rows", row_index, "claim_safe_surface_id"
                    ),
                )
            for result_id in row.get("neutral_result_ids") or []:
                add_edge(
                    edges,
                    boundary_node_id,
                    (
                        "methodology_control:neutral_result_ledger:"
                        f"{slug_fragment(str(result_id))}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(section_claim_boundary_audit_json),
                    evidence=(
                        f"$.boundary_rows[{row_index}].neutral_result_ids"
                        f"[?(@ == {json.dumps(str(result_id))})]"
                    ),
                )
    article_supplement_kg_navigation_index_md = (
        article_supplement_kg_navigation_index_json.with_suffix(".md")
    )
    if article_supplement_kg_navigation_index_json.exists():
        navigation_report_id = "report:article_supplement_kg_navigation_index"
        add_node(
            nodes,
            navigation_report_id,
            "report",
            path=(
                str(article_supplement_kg_navigation_index_md)
                if article_supplement_kg_navigation_index_md.exists()
                else None
            ),
            json_path=str(article_supplement_kg_navigation_index_json),
            summary=(
                "Pre-release article/supplement/KG navigation index tying "
                "reader-facing candidate surfaces to section boundaries, "
                "visual/table candidates, release blockers, and KG references "
                "without final prose, citation, deployment, or method promotion."
            ),
        )
        add_edge(
            edges,
            navigation_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(article_supplement_kg_navigation_index_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:section_claim_boundary_audit",
                "$.sources.section_claim_boundary_audit",
            ),
            (
                "report:manuscript_section_evidence_packet",
                "$.sources.manuscript_section_evidence_packet",
            ),
            (
                "report:claim_safe_result_extraction_matrix",
                "$.sources.claim_safe_result_extraction_matrix",
            ),
            ("report:neutral_result_ledger", "$.sources.neutral_result_ledger"),
            (
                "report:publication_release_gap_register",
                "$.sources.publication_release_gap_register",
            ),
            (
                "report:publication_visual_table_render_candidate_audit",
                "$.sources.visual_table_render_candidate_audit",
            ),
            (
                "report:publication_retention_readiness_audit",
                "$.sources.publication_retention_readiness_audit",
            ),
            (
                "report:article_supplement_kg_triptych_decision",
                "$.sources.article_supplement_kg_triptych_decision",
            ),
            (
                "methodology_control:reviewer_design_publication_site_decision",
                "$.sources.publication_site_decision_record",
            ),
            (
                "report:kg_navigation_usability_audit",
                "$.sources.kg_navigation_usability_audit",
            ),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.knowledge_graph_quality_summary",
            ),
            (
                "report:kg_publication_quality_audit",
                "$.sources.kg_publication_quality_audit",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
            (
                "report:venn_abers_negative_evidence_disposition_audit",
                "$.sources.venn_abers_negative_evidence_disposition_audit",
            ),
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_experiment_publication_program",
            ),
            ("report:goal_completion_audit", "$.sources.goal_completion_audit"),
        ):
            add_edge(
                edges,
                navigation_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(article_supplement_kg_navigation_index_json),
                evidence=selector,
            )
        try:
            navigation_payload = json.loads(
                article_supplement_kg_navigation_index_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            navigation_payload = {}
        for row_index, row in enumerate(navigation_payload.get("navigation_rows") or []):
            navigation_id = str(row.get("navigation_id") or "").strip()
            if not navigation_id:
                continue
            node_id = (
                "methodology_control:article_supplement_kg_navigation_index:"
                f"{slug_fragment(navigation_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=navigation_id,
                navigation_family=row.get("navigation_family"),
                target_document=row.get("target_document"),
                reader_navigation_role=row.get("reader_navigation_role"),
                boundary_status=row.get("boundary_status"),
                claim_safe_surface_id=row.get("claim_safe_surface_id"),
                neutral_result_ids=row.get("neutral_result_ids"),
                linked_visual_table_candidate_ids=row.get(
                    "linked_visual_table_candidate_ids"
                ),
                release_target_deliverable_ids=row.get(
                    "release_target_deliverable_ids"
                ),
                release_authorized_target_count=row.get(
                    "release_authorized_target_count"
                ),
                kg_reference_node_ids=row.get("kg_reference_node_ids"),
                missing_kg_reference_node_ids=row.get(
                    "missing_kg_reference_node_ids"
                ),
                source_traceability_status=row.get("source_traceability_status"),
                main_results_positive_boundary_blocked=row.get(
                    "main_results_positive_boundary_blocked"
                ),
                venn_abers_negative_boundary_preserved=row.get(
                    "venn_abers_negative_boundary_preserved"
                ),
                method_recommendation_authorized=row.get(
                    "method_recommendation_authorized"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                release_authorized=row.get("release_authorized"),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Article/supplement/KG navigation row "
                    f"`{navigation_id}` maps target `{row.get('target_document')}` "
                    f"to boundary `{row.get('boundary_status')}` with release, "
                    "citation, method recommendation, and positive claims still "
                    "unauthorized."
                ),
            )
            selector = row_selector("navigation_rows", row_index, "navigation_id")
            add_edge(
                edges,
                navigation_report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(article_supplement_kg_navigation_index_json),
                evidence=selector,
            )
            for source_node_id in row.get("kg_reference_node_ids") or []:
                add_edge(
                    edges,
                    node_id,
                    str(source_node_id),
                    "DERIVED_FROM",
                    evidence_path=str(article_supplement_kg_navigation_index_json),
                    evidence=(
                        f"$.navigation_rows[{row_index}].kg_reference_node_ids"
                        f"[?(@ == {json.dumps(str(source_node_id))})]"
                    ),
                )
            for visual_id in row.get("linked_visual_table_candidate_ids") or []:
                add_edge(
                    edges,
                    node_id,
                    (
                        "methodology_control:publication_visual_table_render_candidate:"
                        f"{slug_fragment(visual_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(article_supplement_kg_navigation_index_json),
                    evidence=(
                        f"$.navigation_rows[{row_index}].linked_visual_table_candidate_ids"
                        f"[?(@ == {json.dumps(str(visual_id))})]"
                    ),
                )
            for deliverable_id in row.get("release_target_deliverable_ids") or []:
                add_edge(
                    edges,
                    node_id,
                    (
                        "methodology_control:publication_release_gap:"
                        f"{slug_fragment(deliverable_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(article_supplement_kg_navigation_index_json),
                    evidence=(
                        f"$.navigation_rows[{row_index}].release_target_deliverable_ids"
                        f"[?(@ == {json.dumps(str(deliverable_id))})]"
                    ),
                )
    publication_phase_progress_reconciliation_md = (
        publication_phase_progress_reconciliation_json.with_suffix(".md")
    )
    if publication_phase_progress_reconciliation_json.exists():
        reconciliation_report_id = (
            "report:publication_phase_progress_reconciliation_audit"
        )
        add_node(
            nodes,
            reconciliation_report_id,
            "report",
            path=(
                str(publication_phase_progress_reconciliation_md)
                if publication_phase_progress_reconciliation_md.exists()
                else None
            ),
            json_path=str(publication_phase_progress_reconciliation_json),
            summary=(
                "Publication progress reconciliation audit separating completed "
                "pre-prose controls from still-active final prose, visual/table "
                "retention, KG/site, sterile repository, method recommendation, "
                "and positive-claim blockers."
            ),
        )
        add_edge(
            edges,
            reconciliation_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(publication_phase_progress_reconciliation_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_experiment_publication_program",
            ),
            (
                "report:post_experiment_publication_activation_audit",
                "$.sources.post_experiment_publication_activation_audit",
            ),
            ("report:goal_completion_audit", "$.sources.goal_completion_audit"),
            (
                "report:publication_preparation_packets",
                "$.sources.publication_preparation_packets",
            ),
            (
                "report:reviewer_design_reconciliation",
                "$.sources.reviewer_design_brief",
            ),
            (
                "report:publication_visual_table_audit_plan",
                "$.sources.visual_table_audit_plan",
            ),
            (
                "report:publication_visual_table_audit_report",
                "$.sources.visual_table_audit_report",
            ),
            (
                "report:publication_visual_table_render_candidate_audit",
                "$.sources.visual_table_render_candidate_audit",
            ),
            (
                "report:publication_retention_readiness_audit",
                "$.sources.publication_retention_readiness_audit",
            ),
            (
                "report:final_publication_visual_auditor_readiness",
                "$.sources.final_publication_visual_auditor_readiness",
            ),
            (
                "report:article_supplement_blueprint_alignment",
                "$.sources.article_supplement_blueprint_alignment",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.publication_release_gap_register",
            ),
            (
                "report:claim_safe_result_extraction_matrix",
                "$.sources.claim_safe_result_extraction_matrix",
            ),
            (
                "report:manuscript_section_evidence_packet",
                "$.sources.manuscript_section_evidence_packet",
            ),
            (
                "report:section_claim_boundary_audit",
                "$.sources.section_claim_boundary_audit",
            ),
            (
                "report:article_supplement_kg_navigation_index",
                "$.sources.article_supplement_kg_navigation_index",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
            (
                "report:venn_abers_negative_evidence_disposition_audit",
                "$.sources.venn_abers_negative_evidence_disposition_audit",
            ),
            (
                "report:kg_publication_quality_audit",
                "$.sources.kg_publication_quality_audit",
            ),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.knowledge_graph_quality_summary",
            ),
        ):
            add_edge(
                edges,
                reconciliation_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(publication_phase_progress_reconciliation_json),
                evidence=selector,
            )
        try:
            reconciliation_payload = json.loads(
                publication_phase_progress_reconciliation_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            reconciliation_payload = {}
        for row_index, row in enumerate(
            reconciliation_payload.get("pre_prose_control_rows") or []
        ):
            control_id = str(row.get("control_id") or "").strip()
            if not control_id:
                continue
            node_id = (
                "methodology_control:publication_phase_progress_reconciliation:"
                f"{slug_fragment(control_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=control_id,
                reconciliation_family="pre_prose_control",
                status=row.get("status"),
                note=row.get("note"),
                final_outputs_authorized=False,
                method_recommendation_authorized=False,
                positive_claim_promotion_authorized=False,
                summary=(
                    "Publication progress pre-prose control "
                    f"`{control_id}` is `{row.get('status')}` while final "
                    "outputs and method/positive-claim promotion remain blocked."
                ),
            )
            add_edge(
                edges,
                reconciliation_report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_phase_progress_reconciliation_json),
                evidence=row_selector(
                    "pre_prose_control_rows", row_index, "control_id"
                ),
            )
            for source_path in row.get("source_artifacts") or []:
                source_name = Path(str(source_path)).name
                source_id = {
                    "publication_preparation_packets.json": "report:publication_preparation_packets",
                    "reviewer_design_brief.json": "report:reviewer_design_reconciliation",
                    "reviewer_reconciliation_matrix.json": "report:reviewer_design_reconciliation",
                    "visual_table_audit_plan.json": "report:publication_visual_table_audit_plan",
                    "visual_table_audit_report.json": "report:publication_visual_table_audit_report",
                    "visual_table_render_candidate_audit.json": "report:publication_visual_table_render_candidate_audit",
                    "publication_retention_readiness_audit.json": "report:publication_retention_readiness_audit",
                    "final_publication_visual_auditor_readiness.json": "report:final_publication_visual_auditor_readiness",
                    "publication_release_gap_register.json": "report:publication_release_gap_register",
                    "claim_safe_result_extraction_matrix.json": "report:claim_safe_result_extraction_matrix",
                    "manuscript_section_evidence_packet.json": "report:manuscript_section_evidence_packet",
                    "section_claim_boundary_audit.json": "report:section_claim_boundary_audit",
                    "article_supplement_kg_navigation_index.json": "report:article_supplement_kg_navigation_index",
                    "neutral_reporting_language_audit.json": "report:neutral_reporting_language_audit",
                    "kg_publication_quality_audit.json": "report:kg_publication_quality_audit",
                    "quality_summary.json": "report:knowledge_graph_quality_summary",
                }.get(source_name)
                if source_id:
                    add_edge(
                        edges,
                        node_id,
                        source_id,
                        "DERIVED_FROM",
                        evidence_path=str(
                            publication_phase_progress_reconciliation_json
                        ),
                        evidence=(
                            f"$.pre_prose_control_rows[{row_index}]"
                            ".source_artifacts"
                        ),
                    )
        for row_index, row in enumerate(
            reconciliation_payload.get("resolved_prior_blocker_rows") or []
        ):
            blocker_id = str(row.get("blocker_id") or "").strip()
            if not blocker_id:
                continue
            node_id = (
                "methodology_control:publication_phase_progress_resolved_blocker:"
                f"{slug_fragment(blocker_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=blocker_id,
                reconciliation_family="resolved_prior_blocker",
                status=row.get("status"),
                resolved_by_control_id=row.get("resolved_by_control_id"),
                method_recommendation_authorized=False,
                positive_claim_promotion_authorized=False,
                summary=(
                    "Publication progress resolved prior blocker "
                    f"`{blocker_id}` is no longer an active pre-prose blocker."
                ),
            )
            add_edge(
                edges,
                reconciliation_report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_phase_progress_reconciliation_json),
                evidence=row_selector(
                    "resolved_prior_blocker_rows", row_index, "blocker_id"
                ),
            )
            resolved_by = row.get("resolved_by_control_id")
            if resolved_by:
                add_edge(
                    edges,
                    node_id,
                    (
                        "methodology_control:publication_phase_progress_reconciliation:"
                        f"{slug_fragment(resolved_by)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(publication_phase_progress_reconciliation_json),
                    evidence=(
                        f"$.resolved_prior_blocker_rows[{row_index}]"
                        ".resolved_by_control_id"
                    ),
                )
        for row_index, row in enumerate(
            reconciliation_payload.get("active_final_blocker_rows") or []
        ):
            blocker_id = str(row.get("blocker_id") or "").strip()
            if not blocker_id:
                continue
            node_id = (
                "methodology_control:publication_phase_progress_active_blocker:"
                f"{slug_fragment(blocker_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=blocker_id,
                reconciliation_family="active_final_blocker",
                status=row.get("status"),
                reason=row.get("reason"),
                method_recommendation_authorized=False,
                positive_claim_promotion_authorized=False,
                summary=(
                    "Publication progress active final blocker "
                    f"`{blocker_id}` keeps final publication outputs or claims "
                    "unauthorized."
                ),
            )
            add_edge(
                edges,
                reconciliation_report_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_phase_progress_reconciliation_json),
                evidence=row_selector(
                    "active_final_blocker_rows", row_index, "blocker_id"
                ),
            )
            add_edge(
                edges,
                node_id,
                "report:publication_release_gap_register",
                "DERIVED_FROM",
                evidence_path=str(publication_phase_progress_reconciliation_json),
                evidence=(
                    f"$.active_final_blocker_rows[{row_index}].blocker_id"
                ),
            )
    scientific_neutrality_interpretation_lock_md = (
        scientific_neutrality_interpretation_lock_json.with_suffix(".md")
    )
    if scientific_neutrality_interpretation_lock_json.exists():
        interpretation_lock_id = (
            "report:scientific_neutrality_interpretation_lock"
        )
        add_node(
            nodes,
            interpretation_lock_id,
            "report",
            path=(
                str(scientific_neutrality_interpretation_lock_md)
                if scientific_neutrality_interpretation_lock_md.exists()
                else None
            ),
            json_path=str(scientific_neutrality_interpretation_lock_json),
            summary=(
                "Scientific neutrality interpretation lock mapping allowed "
                "and blocked publication-prep interpretations without final "
                "prose, method recommendation, or positive-claim promotion."
            ),
        )
        add_edge(
            edges,
            interpretation_lock_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(scientific_neutrality_interpretation_lock_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            ("report:goal_completion_audit", "$.sources.goal_completion_audit"),
            (
                "report:publication_phase_progress_reconciliation_audit",
                "$.sources.publication_phase_progress_reconciliation_audit",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
            ("report:neutral_result_ledger", "$.sources.neutral_result_ledger"),
            (
                "report:method_performance_synthesis",
                "$.sources.method_performance_synthesis",
            ),
            (
                "report:method_selection_candidate_audit",
                "$.sources.method_selection_candidate_audit",
            ),
            (
                "report:method_selection_inferential_audit",
                "$.sources.method_selection_inferential_audit",
            ),
            (
                "report:venn_abers_negative_evidence_disposition_audit",
                "$.sources.venn_abers_negative_evidence_disposition_audit",
            ),
            (
                "report:venn_abers_validation_readiness_audit",
                "$.sources.venn_abers_validation_readiness_audit",
            ),
            (
                "report:venn_abers_claim_gate_matrix",
                "$.sources.venn_abers_claim_gate_matrix",
            ),
            ("report:paper_gate_closure_map", "$.sources.paper_gate_closure_map"),
            (
                "report:section_claim_boundary_audit",
                "$.sources.section_claim_boundary_audit",
            ),
            (
                "report:claim_safe_result_extraction_matrix",
                "$.sources.claim_safe_result_extraction_matrix",
            ),
            (
                "report:article_supplement_kg_navigation_index",
                "$.sources.article_supplement_kg_navigation_index",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.publication_release_gap_register",
            ),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.knowledge_graph_quality_summary",
            ),
        ):
            add_edge(
                edges,
                interpretation_lock_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(scientific_neutrality_interpretation_lock_json),
                evidence=selector,
            )
        try:
            interpretation_lock_payload = json.loads(
                scientific_neutrality_interpretation_lock_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            interpretation_lock_payload = {}
        interpretation_source_node_ids = {
            "goal_completion_audit.json": "report:goal_completion_audit",
            "publication_phase_progress_reconciliation_audit.json": (
                "report:publication_phase_progress_reconciliation_audit"
            ),
            "neutral_reporting_language_audit.json": (
                "report:neutral_reporting_language_audit"
            ),
            "neutral_result_ledger.json": "report:neutral_result_ledger",
            "method_performance_synthesis.json": (
                "report:method_performance_synthesis"
            ),
            "method_selection_candidate_audit.json": (
                "report:method_selection_candidate_audit"
            ),
            "method_selection_inferential_audit.json": (
                "report:method_selection_inferential_audit"
            ),
            "venn_abers_negative_evidence_disposition_audit.json": (
                "report:venn_abers_negative_evidence_disposition_audit"
            ),
            "venn_abers_validation_readiness_audit.json": (
                "report:venn_abers_validation_readiness_audit"
            ),
            "venn_abers_claim_gate_matrix.json": (
                "report:venn_abers_claim_gate_matrix"
            ),
            "paper_gate_closure_map.json": "report:paper_gate_closure_map",
            "section_claim_boundary_audit.json": (
                "report:section_claim_boundary_audit"
            ),
            "claim_safe_result_extraction_matrix.json": (
                "report:claim_safe_result_extraction_matrix"
            ),
            "article_supplement_kg_navigation_index.json": (
                "report:article_supplement_kg_navigation_index"
            ),
            "publication_release_gap_register.json": (
                "report:publication_release_gap_register"
            ),
            "quality_summary.json": "report:knowledge_graph_quality_summary",
        }
        for row_index, row in enumerate(
            interpretation_lock_payload.get("interpretation_rows") or []
        ):
            row_id = str(row.get("row_id") or "").strip()
            if not row_id:
                continue
            node_id = (
                "methodology_control:scientific_neutrality_interpretation_lock:"
                f"{slug_fragment(row_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=row_id,
                surface=row.get("surface"),
                allowed_interpretation=row.get("allowed_interpretation"),
                blocked_interpretation=row.get("blocked_interpretation"),
                final_prose_authorized=False,
                method_recommendation_authorized=False,
                positive_claim_promotion_authorized=False,
                summary=(
                    "Scientific neutrality interpretation row "
                    f"`{row_id}` permits scoped reporting but blocks method "
                    "recommendation, positive-claim promotion, and final prose."
                ),
            )
            add_edge(
                edges,
                interpretation_lock_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(scientific_neutrality_interpretation_lock_json),
                evidence=row_selector("interpretation_rows", row_index, "row_id"),
            )
            for source_path in row.get("source_artifacts") or []:
                source_node_id = interpretation_source_node_ids.get(
                    Path(str(source_path)).name
                )
                if source_node_id:
                    add_edge(
                        edges,
                        node_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(
                            scientific_neutrality_interpretation_lock_json
                        ),
                        evidence=(
                            f"$.interpretation_rows[{row_index}]"
                            ".source_artifacts"
                        ),
                    )
    final_authorization_md = (
        final_publication_output_authorization_protocol_json.with_suffix(".md")
    )
    if final_publication_output_authorization_protocol_json.exists():
        final_authorization_id = (
            "report:final_publication_output_authorization_protocol"
        )
        add_node(
            nodes,
            final_authorization_id,
            "report",
            path=(
                str(final_authorization_md)
                if final_authorization_md.exists()
                else None
            ),
            json_path=str(final_publication_output_authorization_protocol_json),
            summary=(
                "Final publication output authorization protocol mapping active "
                "final-output blockers to required evidence while keeping final "
                "prose, retained visuals/tables, KG/site release, sterile "
                "repository creation, method recommendation, and positive "
                "claims unauthorized."
            ),
        )
        add_edge(
            edges,
            final_authorization_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(final_publication_output_authorization_protocol_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            ("report:goal_completion_audit", "$.sources.goal_completion_audit"),
            (
                "report:publication_phase_progress_reconciliation_audit",
                "$.sources.publication_phase_progress_reconciliation_audit",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.publication_release_gap_register",
            ),
            (
                "report:scientific_neutrality_interpretation_lock",
                "$.sources.scientific_neutrality_interpretation_lock",
            ),
            (
                "report:final_publication_visual_auditor_readiness",
                "$.sources.final_publication_visual_auditor_readiness",
            ),
            (
                "report:section_claim_boundary_audit",
                "$.sources.section_claim_boundary_audit",
            ),
            (
                "report:article_supplement_kg_navigation_index",
                "$.sources.article_supplement_kg_navigation_index",
            ),
            ("report:paper_gate_closure_map", "$.sources.paper_gate_closure_map"),
            (
                "report:kg_publication_quality_audit",
                "$.sources.kg_publication_quality_audit",
            ),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.knowledge_graph_quality_summary",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
        ):
            add_edge(
                edges,
                final_authorization_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(final_publication_output_authorization_protocol_json),
                evidence=selector,
            )
        try:
            final_authorization_payload = json.loads(
                final_publication_output_authorization_protocol_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            final_authorization_payload = {}
        final_authorization_source_ids = {
            "goal_completion_audit.json": "report:goal_completion_audit",
            "publication_phase_progress_reconciliation_audit.json": (
                "report:publication_phase_progress_reconciliation_audit"
            ),
            "publication_release_gap_register.json": (
                "report:publication_release_gap_register"
            ),
            "scientific_neutrality_interpretation_lock.json": (
                "report:scientific_neutrality_interpretation_lock"
            ),
            "final_publication_visual_auditor_readiness.json": (
                "report:final_publication_visual_auditor_readiness"
            ),
            "section_claim_boundary_audit.json": (
                "report:section_claim_boundary_audit"
            ),
            "article_supplement_kg_navigation_index.json": (
                "report:article_supplement_kg_navigation_index"
            ),
            "paper_gate_closure_map.json": "report:paper_gate_closure_map",
            "kg_publication_quality_audit.json": (
                "report:kg_publication_quality_audit"
            ),
            "quality_summary.json": "report:knowledge_graph_quality_summary",
            "neutral_reporting_language_audit.json": (
                "report:neutral_reporting_language_audit"
            ),
        }
        for row_index, row in enumerate(
            final_authorization_payload.get("authorization_rows") or []
        ):
            blocker_id = str(row.get("blocker_id") or "").strip()
            if not blocker_id:
                continue
            node_id = (
                "methodology_control:final_publication_output_authorization:"
                f"{slug_fragment(blocker_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=blocker_id,
                output_family=row.get("output_family"),
                authorization_status=row.get("authorization_status"),
                source_traceability_status=row.get("source_traceability_status"),
                active_progress_status=row.get("active_progress_status"),
                ready_to_authorize=False,
                final_output_authorized=False,
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                positive_claim_promotion_authorized=False,
                blocked_current_action=row.get("blocked_current_action"),
                allowed_current_action=row.get("allowed_current_action"),
                summary=(
                    "Final publication output authorization row "
                    f"`{blocker_id}` remains `{row.get('authorization_status')}`; "
                    "the current manuscript route is neutral and does not "
                    "authorize final outputs or method promotion."
                ),
            )
            add_edge(
                edges,
                final_authorization_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(final_publication_output_authorization_protocol_json),
                evidence=row_selector(
                    "authorization_rows", row_index, "blocker_id"
                ),
            )
            for source_path in row.get("source_artifacts") or []:
                source_node_id = final_authorization_source_ids.get(
                    Path(str(source_path)).name
                )
                if source_node_id:
                    add_edge(
                        edges,
                        node_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(
                            final_publication_output_authorization_protocol_json
                        ),
                        evidence=(
                            f"$.authorization_rows[{row_index}]"
                            ".source_artifacts"
                        ),
            )
    publication_authoring_decision_md = (
        publication_authoring_decision_record_json.with_suffix(".md")
    )
    if publication_authoring_decision_record_json.exists():
        publication_authoring_decision_id = "report:publication_authoring_decision_record"
        add_node(
            nodes,
            publication_authoring_decision_id,
            "report",
            path=(
                str(publication_authoring_decision_md)
                if publication_authoring_decision_md.exists()
                else None
            ),
            json_path=str(publication_authoring_decision_record_json),
            summary=(
                "Publication authoring decision record separating private "
                "Research Document, main article, and supplementary authoring "
                "from public release, method recommendation, and positive-claim "
                "promotion."
            ),
        )
        add_edge(
            edges,
            publication_authoring_decision_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(publication_authoring_decision_record_json),
            evidence="$.summary",
        )
    publication_exemplar_review_md = publication_exemplar_review_json.with_suffix(
        ".md"
    )
    if publication_exemplar_review_json.exists():
        publication_exemplar_review_id = "report:publication_exemplar_review"
        add_node(
            nodes,
            publication_exemplar_review_id,
            "report",
            path=(
                str(publication_exemplar_review_md)
                if publication_exemplar_review_md.exists()
                else None
            ),
            json_path=str(publication_exemplar_review_json),
            summary=(
                "Publication exemplar review summarizing comparable conformal "
                "prediction papers, repositories, documentation, and sites into "
                "claim-safe design decisions for the Research Document, main "
                "article, supplement, README, private site, and future sterile "
                "repository."
            ),
        )
        add_edge(
            edges,
            publication_exemplar_review_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(publication_exemplar_review_json),
            evidence="$.summary",
        )
    sterile_manifest_md = sterile_repository_staging_manifest_json.with_suffix(".md")
    publication_claim_matrix_md = (
        publication_claim_evidence_verification_matrix_json.with_suffix(".md")
    )
    if publication_claim_evidence_verification_matrix_json.exists():
        publication_claim_matrix_id = (
            "report:publication_claim_evidence_verification_matrix"
        )
        add_node(
            nodes,
            publication_claim_matrix_id,
            "report",
            path=(
                str(publication_claim_matrix_md)
                if publication_claim_matrix_md.exists()
                else None
            ),
            json_path=str(publication_claim_evidence_verification_matrix_json),
            summary=(
                "Publication claim/evidence verification matrix linking "
                "claim-safe surfaces, section evidence packets, boundary "
                "audits, KG navigation rows, and neutral result evidence "
                "under no-final-prose and no-method-advocacy reporting."
            ),
        )
        add_edge(
            edges,
            publication_claim_matrix_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(publication_claim_evidence_verification_matrix_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:claim_safe_result_extraction_matrix",
                "$.sources.claim_safe_result_extraction_matrix",
            ),
            (
                "report:manuscript_section_evidence_packet",
                "$.sources.manuscript_section_evidence_packet",
            ),
            (
                "report:section_claim_boundary_audit",
                "$.sources.section_claim_boundary_audit",
            ),
            (
                "report:article_supplement_kg_navigation_index",
                "$.sources.article_supplement_kg_navigation_index",
            ),
            (
                "report:final_publication_output_authorization_protocol",
                "$.sources.final_publication_output_authorization_protocol",
            ),
            (
                "report:scientific_neutrality_interpretation_lock",
                "$.sources.scientific_neutrality_interpretation_lock",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.publication_release_gap_register",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.knowledge_graph_quality_summary",
            ),
            (
                "report:publication_citation_registry",
                "$.sources.publication_citation_registry",
            ),
            (
                "report:main_article_draft",
                "$.sources.main_article_draft",
            ),
            (
                "report:supplementary_document_draft",
                "$.sources.supplementary_document_draft",
            ),
            (
                "report:individual_experiment_report_draft",
                "$.sources.individual_experiment_report_draft",
            ),
            (
                "report:sterile_repository_readme_draft",
                "$.sources.sterile_repository_readme_draft",
            ),
        ):
            add_edge(
                edges,
                publication_claim_matrix_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(publication_claim_evidence_verification_matrix_json),
                evidence=selector,
            )
        try:
            publication_claim_matrix_payload = json.loads(
                publication_claim_evidence_verification_matrix_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            publication_claim_matrix_payload = {}
        verification_source_ids = {
            "article_supplement_blueprint_alignment.json": (
                "report:article_supplement_blueprint_alignment"
            ),
            "claim_safe_result_extraction_matrix.json": (
                "report:claim_safe_result_extraction_matrix"
            ),
            "experiment_accounting_audit.json": "report:experiment_accounting_audit",
            "final_selection_claim_boundary_audit.json": (
                "report:final_selection_claim_boundary_audit"
            ),
            "goal_completion_audit.json": "report:goal_completion_audit",
            "individual_experiment_report_blueprint.json": (
                "report:individual_experiment_report_blueprint"
            ),
            "kg_publication_quality_audit.json": (
                "report:kg_publication_quality_audit"
            ),
            "method_performance_synthesis.json": (
                "report:method_performance_synthesis"
            ),
            "neutral_reporting_language_audit.json": (
                "report:neutral_reporting_language_audit"
            ),
            "neutral_result_ledger.json": "report:neutral_result_ledger",
            "paper_gate_closure_map.json": "report:paper_gate_closure_map",
            "paper_readiness_map.json": "report:manuscript_readiness_map",
            "publication_release_gap_register.json": (
                "report:publication_release_gap_register"
            ),
            "publication_retention_readiness_audit.json": (
                "report:publication_retention_readiness_audit"
            ),
            "venn_abers_negative_evidence_disposition_audit.json": (
                "report:venn_abers_negative_evidence_disposition_audit"
            ),
        }
        for row_index, row in enumerate(
            publication_claim_matrix_payload.get("verification_rows") or []
        ):
            verification_id = str(row.get("verification_id") or "").strip()
            if not verification_id:
                continue
            node_id = (
                "methodology_control:publication_claim_evidence_verification:"
                f"{slug_fragment(verification_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=verification_id,
                target_document=row.get("target_document"),
                claim_safe_surface_id=row.get("claim_safe_surface_id"),
                verification_status=row.get("verification_status"),
                source_traceability_status=row.get("source_traceability_status"),
                boundary_complete=row.get("boundary_complete"),
                claim_safe_surface_consistent=row.get(
                    "claim_safe_surface_consistent"
                ),
                release_targets_blocked=row.get("release_targets_blocked"),
                safe_pre_prose_evidence_packet=row.get(
                    "safe_pre_prose_evidence_packet"
                ),
                positive_claim_packet_blocked=row.get(
                    "positive_claim_packet_blocked"
                ),
                main_results_positive_boundary_blocked=row.get(
                    "main_results_positive_boundary_blocked"
                ),
                venn_abers_negative_boundary_preserved=row.get(
                    "venn_abers_negative_boundary_preserved"
                ),
                authorization_violation_count=len(
                    row.get("authorization_violations") or []
                ),
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                method_advocacy_authorized=False,
                positive_claim_promotion_authorized=False,
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Publication claim/evidence verification row "
                    f"`{verification_id}` is `{row.get('verification_status')}` "
                    "for a pre-prose evidence packet; it preserves neutral "
                    "reporting and blocks final method promotion."
                ),
            )
            add_edge(
                edges,
                publication_claim_matrix_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_claim_evidence_verification_matrix_json),
                evidence=row_selector(
                    "verification_rows", row_index, "verification_id"
                ),
            )
            for control_id in (
                (
                    "methodology_control:manuscript_section_evidence_packet:"
                    f"{slug_fragment(verification_id)}"
                ),
                (
                    "methodology_control:section_claim_boundary_audit:"
                    f"{slug_fragment(verification_id)}"
                ),
                (
                    "methodology_control:article_supplement_kg_navigation_index:"
                    f"{slug_fragment(verification_id)}"
                ),
            ):
                add_edge(
                    edges,
                    node_id,
                    control_id,
                    "DERIVED_FROM",
                    evidence_path=str(publication_claim_evidence_verification_matrix_json),
                    evidence=row_selector(
                        "verification_rows", row_index, "verification_id"
                    ),
                )
            surface_id = str(row.get("claim_safe_surface_id") or "").strip()
            if surface_id:
                add_edge(
                    edges,
                    node_id,
                    (
                        "methodology_control:claim_safe_result_extraction:"
                        f"{slug_fragment(surface_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(publication_claim_evidence_verification_matrix_json),
                    evidence=(
                        f"$.verification_rows[{row_index}]"
                        ".claim_safe_surface_id"
                    ),
                )
            for result_id in row.get("neutral_result_ids") or []:
                add_edge(
                    edges,
                    node_id,
                    (
                        "methodology_control:neutral_result_ledger:"
                        f"{slug_fragment(result_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(publication_claim_evidence_verification_matrix_json),
                    evidence=f"$.verification_rows[{row_index}].neutral_result_ids",
                )
            for kg_node_id in row.get("kg_reference_node_ids") or []:
                if str(kg_node_id) == node_id:
                    continue
                add_edge(
                    edges,
                    node_id,
                    str(kg_node_id),
                    "DERIVED_FROM",
                    evidence_path=str(publication_claim_evidence_verification_matrix_json),
                    evidence=f"$.verification_rows[{row_index}].kg_reference_node_ids",
                )
            for source_path in row.get("source_artifacts") or []:
                source_node_id = verification_source_ids.get(
                    str(source_path)
                ) or verification_source_ids.get(Path(str(source_path)).name)
                if source_node_id:
                    add_edge(
                        edges,
                        node_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(
                            publication_claim_evidence_verification_matrix_json
                        ),
                        evidence=(
                            f"$.verification_rows[{row_index}]"
                            ".source_artifacts"
                        ),
                    )
        draft_artifact_source_ids = {
            "article_supplement_blueprint_alignment": (
                "report:article_supplement_blueprint_alignment"
            ),
            "final_publication_output_authorization_protocol": (
                "report:final_publication_output_authorization_protocol"
            ),
            "individual_experiment_report_draft": (
                "report:individual_experiment_report_draft"
            ),
            "knowledge_graph_quality_summary": (
                "report:knowledge_graph_quality_summary"
            ),
            "main_article_draft": "report:main_article_draft",
            "manuscript_section_evidence_packet": (
                "report:manuscript_section_evidence_packet"
            ),
            "method_literature_coverage_audit": (
                "report:method_literature_coverage_audit"
            ),
            "publication_citation_registry": "report:publication_citation_registry",
            "publication_claim_evidence_verification_matrix": (
                publication_claim_matrix_id
            ),
            "publication_release_gap_register": (
                "report:publication_release_gap_register"
            ),
            "reader_method_primer_citation_map": (
                "report:reader_method_primer_citation_map"
            ),
            "reader_primer_section_alignment": (
                "report:reader_primer_section_alignment"
            ),
            "section_claim_boundary_audit": (
                "report:section_claim_boundary_audit"
            ),
            "sterile_repository_staging_manifest": (
                "report:sterile_repository_staging_manifest"
            ),
            "sterile_repository_readme_draft": (
                "report:sterile_repository_readme_draft"
            ),
            "supplementary_document_draft": (
                "report:supplementary_document_draft"
            ),
        }
        for row_index, row in enumerate(
            publication_claim_matrix_payload.get(
                "current_publication_draft_artifact_rows"
            )
            or []
        ):
            artifact_id = str(row.get("artifact_id") or "").strip()
            if not artifact_id:
                continue
            node_id = (
                "methodology_control:publication_claim_evidence_draft_artifact:"
                f"{slug_fragment(artifact_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=artifact_id,
                target_document=row.get("target_document"),
                verification_status=row.get("verification_status"),
                source_traceability_status=row.get("source_traceability_status"),
                missing_required_source_key_count=len(
                    row.get("missing_required_source_keys") or []
                ),
                failed_check_count=row.get("failed_check_count"),
                authorization_violation_count=len(
                    row.get("authorization_violations") or []
                ),
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                method_advocacy_authorized=False,
                positive_claim_promotion_authorized=False,
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Publication claim/evidence matrix covers current draft "
                    f"artifact `{artifact_id}` as `{row.get('verification_status')}` "
                    "draft-only evidence with final prose and method promotion "
                    "blocked."
                ),
            )
            add_edge(
                edges,
                publication_claim_matrix_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_claim_evidence_verification_matrix_json),
                evidence=row_selector(
                    "current_publication_draft_artifact_rows",
                    row_index,
                    "artifact_id",
                ),
            )
            artifact_report_id = draft_artifact_source_ids.get(artifact_id)
            if artifact_report_id:
                add_edge(
                    edges,
                    node_id,
                    artifact_report_id,
                    "DERIVED_FROM",
                    evidence_path=str(
                        publication_claim_evidence_verification_matrix_json
                    ),
                    evidence=(
                        "$.current_publication_draft_artifact_rows"
                        f"[{row_index}].artifact_id"
                    ),
                )
            for source_key in row.get("required_source_keys") or []:
                source_report_id = draft_artifact_source_ids.get(str(source_key))
                if not source_report_id:
                    continue
                add_edge(
                    edges,
                    node_id,
                    source_report_id,
                    "DERIVED_FROM",
                    evidence_path=str(
                        publication_claim_evidence_verification_matrix_json
                    ),
                    evidence=(
                        "$.current_publication_draft_artifact_rows"
                        f"[{row_index}].required_source_keys"
                    ),
                )
    reader_method_primer_md = reader_method_primer_citation_map_json.with_suffix(".md")
    if reader_method_primer_citation_map_json.exists():
        reader_method_primer_id = "report:reader_method_primer_citation_map"
        add_node(
            nodes,
            reader_method_primer_id,
            "report",
            path=str(reader_method_primer_md) if reader_method_primer_md.exists() else None,
            json_path=str(reader_method_primer_citation_map_json),
            summary=(
                "Reader method-primer citation map linking non-specialist "
                "conformal prediction concept explanations to primary sources "
                "and blocked-language boundaries while final prose remains "
                "unauthorized."
            ),
        )
        add_edge(
            edges,
            reader_method_primer_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(reader_method_primer_citation_map_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:method_literature_coverage_audit",
                "$.sources.method_literature_coverage_audit",
            ),
            (
                "report:publication_claim_evidence_verification_matrix",
                "$.sources.publication_claim_evidence_verification_matrix",
            ),
        ):
            add_edge(
                edges,
                reader_method_primer_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(reader_method_primer_citation_map_json),
                evidence=selector,
            )
        try:
            reader_method_primer_payload = json.loads(
                reader_method_primer_citation_map_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            reader_method_primer_payload = {}
        for row_index, row in enumerate(
            reader_method_primer_payload.get("concept_rows") or []
        ):
            concept_id = str(row.get("concept_id") or "").strip()
            if not concept_id:
                continue
            concept_node_id = (
                "methodology_control:reader_method_primer:"
                f"{slug_fragment(concept_id)}"
            )
            add_node(
                nodes,
                concept_node_id,
                "methodology_control",
                name=concept_id,
                concept_id=concept_id,
                paper_use=row.get("paper_use"),
                required_reader_explanation_count=len(
                    row.get("required_reader_explanation") or []
                ),
                reader_explanation_outline=row.get("reader_explanation_outline") or [],
                reader_explanation_outline_count=len(
                    row.get("reader_explanation_outline") or []
                ),
                citation_use_note=row.get("citation_use_note"),
                primary_source_url_count=len(row.get("primary_source_urls") or []),
                primary_source_urls=row.get("primary_source_urls") or [],
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                method_advocacy_authorized=False,
                positive_claim_promotion_authorized=False,
                summary=(
                    "Reader method-primer concept row "
                    f"`{concept_id}` defines a non-specialist explanation and "
                    "blocked-language boundary before any final prose is written."
                ),
            )
            add_edge(
                edges,
                reader_method_primer_id,
                concept_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(reader_method_primer_citation_map_json),
                evidence=row_selector("concept_rows", row_index, "concept_id"),
            )
    publication_citation_registry_md = (
        publication_citation_registry_json.with_suffix(".md")
    )
    if publication_citation_registry_json.exists():
        publication_citation_registry_id = "report:publication_citation_registry"
        add_node(
            nodes,
            publication_citation_registry_id,
            "report",
            path=(
                str(publication_citation_registry_md)
                if publication_citation_registry_md.exists()
                else None
            ),
            json_path=str(publication_citation_registry_json),
            summary=(
                "Publication citation registry mapping audited reader-primer "
                "and method-literature source URLs to stable citation keys "
                "and BibTeX entries while final prose remains unauthorized."
            ),
        )
        add_edge(
            edges,
            publication_citation_registry_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(publication_citation_registry_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:reader_method_primer_citation_map",
                "$.sources.reader_method_primer_citation_map",
            ),
            (
                "report:method_literature_coverage_audit",
                "$.sources.method_literature_coverage_audit",
            ),
        ):
            add_edge(
                edges,
                publication_citation_registry_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(publication_citation_registry_json),
                evidence=selector,
            )
        try:
            publication_citation_registry_payload = json.loads(
                publication_citation_registry_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            publication_citation_registry_payload = {}
        for row_index, row in enumerate(
            publication_citation_registry_payload.get("citation_rows") or []
        ):
            citation_key = str(row.get("citation_key") or "").strip()
            if not citation_key:
                continue
            citation_node_id = (
                "methodology_control:publication_citation_registry:"
                f"{slug_fragment(citation_key)}"
            )
            add_node(
                nodes,
                citation_node_id,
                "methodology_control",
                name=citation_key,
                citation_key=citation_key,
                entry_type=row.get("entry_type"),
                title=row.get("title"),
                year=row.get("year"),
                url=row.get("url"),
                source_kind=row.get("source_kind"),
                source_role=row.get("source_role"),
                covered_primer_concept_ids=row.get("covered_primer_concept_ids")
                or [],
                covered_literature_requirement_ids=row.get(
                    "covered_literature_requirement_ids"
                )
                or [],
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                method_advocacy_authorized=False,
                positive_claim_promotion_authorized=False,
                summary=(
                    "Publication citation registry row "
                    f"`{citation_key}` maps an audited source URL to a stable "
                    "citation key and BibTeX entry without authorizing final "
                    "prose or method claims."
                ),
            )
            add_edge(
                edges,
                publication_citation_registry_id,
                citation_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(publication_citation_registry_json),
                evidence=row_selector("citation_rows", row_index, "citation_key"),
            )
            for concept_id in row.get("covered_primer_concept_ids") or []:
                add_edge(
                    edges,
                    citation_node_id,
                    (
                        "methodology_control:reader_method_primer:"
                        f"{slug_fragment(concept_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(publication_citation_registry_json),
                    evidence=(
                        f"$.citation_rows[{row_index}]."
                        "covered_primer_concept_ids"
                    ),
                )
    individual_report_draft_md = individual_experiment_report_draft_json.with_suffix(
        ".md"
    )
    if individual_experiment_report_draft_json.exists():
        individual_report_draft_id = "report:individual_experiment_report_draft"
        add_node(
            nodes,
            individual_report_draft_id,
            "report",
            path=(
                str(individual_report_draft_md)
                if individual_report_draft_md.exists()
                else None
            ),
            json_path=str(individual_experiment_report_draft_json),
            summary=(
                "Evidence-linked individual experiment report draft with "
                "author metadata, reader primer, empirical scope, method "
                "diagnostics, negative/blocked claims, KG traceability, and "
                "release boundaries."
            ),
        )
        add_edge(
            edges,
            individual_report_draft_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(individual_experiment_report_draft_json),
            evidence="$.summary",
        )
        try:
            individual_report_draft_payload = json.loads(
                individual_experiment_report_draft_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            individual_report_draft_payload = {}
        individual_report_source_node_map = {
            "experiment_accounting_audit": "report:experiment_accounting_audit",
            "method_performance_synthesis": "report:method_performance_synthesis",
            "method_selection_robustness_audit": "report:method_selection_robustness_audit",
            "venn_abers_negative_evidence_disposition_audit": "report:venn_abers_negative_evidence_disposition_audit",
            "venn_abers_grid_failure_mode_decomposition": "report:venn_abers_grid_failure_mode_decomposition",
            "bounded_support_endpoint_closure_audit": "report:bounded_support_endpoint_closure_audit",
            "fairness_population_readiness_audit": "report:fairness_population_readiness_audit",
            "goal_completion_audit": "report:goal_completion_audit",
            "publication_release_gap_register": "report:publication_release_gap_register",
            "knowledge_graph_quality_summary": "report:knowledge_graph_quality_summary",
            "publication_citation_registry": "report:publication_citation_registry",
            "reader_primer_section_alignment": "report:reader_primer_section_alignment",
        }
        for source_key, source_id in individual_report_source_node_map.items():
            if source_key in (individual_report_draft_payload.get("sources") or {}):
                add_edge(
                    edges,
                    individual_report_draft_id,
                    source_id,
                    "DERIVED_FROM",
                    evidence_path=str(individual_experiment_report_draft_json),
                    evidence=f"$.sources.{source_key}",
                )
        for row_index, row in enumerate(
            individual_report_draft_payload.get("sections") or []
        ):
            section_id = str(row.get("section_id") or "").strip()
            if not section_id:
                continue
            section_node_id = (
                "methodology_control:individual_experiment_report_draft:"
                f"{slug_fragment(section_id)}"
            )
            add_node(
                nodes,
                section_node_id,
                "methodology_control",
                name=section_id,
                section_id=section_id,
                evidence_sources=row.get("evidence_sources") or [],
                evidence_source_count=len(row.get("evidence_sources") or []),
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                positive_claim_promotion_authorized=False,
                summary=(
                    "Individual experiment report draft section "
                    f"`{section_id}` maps prose content to audited evidence "
                    "sources while release and final method claims remain blocked."
                ),
            )
            add_edge(
                edges,
                individual_report_draft_id,
                section_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(individual_experiment_report_draft_json),
                evidence=row_selector("sections", row_index, "section_id"),
            )
            for source_key in row.get("evidence_sources") or []:
                source_id = individual_report_source_node_map.get(source_key)
                if source_id:
                    add_edge(
                        edges,
                        section_node_id,
                        source_id,
                        "DERIVED_FROM",
                        evidence_path=str(individual_experiment_report_draft_json),
                        evidence=f"$.sections[{row_index}].evidence_sources",
                    )
    main_article_draft_md = main_article_draft_json.with_suffix(".md")
    if main_article_draft_json.exists():
        main_article_draft_id = "report:main_article_draft"
        add_node(
            nodes,
            main_article_draft_id,
            "report",
            path=str(main_article_draft_md) if main_article_draft_md.exists() else None,
            json_path=str(main_article_draft_json),
            summary=(
                "Evidence-linked main article draft reporting regression "
                "conformal prediction scope, method diagnostics, negative "
                "Venn-Abers bridge evidence, claim boundaries, and KG "
                "traceability without release or method recommendation."
            ),
        )
        add_edge(
            edges,
            main_article_draft_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(main_article_draft_json),
            evidence="$.summary",
        )
        try:
            main_article_draft_payload = json.loads(
                main_article_draft_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            main_article_draft_payload = {}
        main_article_source_node_map = {
            "individual_experiment_report_draft": "report:individual_experiment_report_draft",
            "article_supplement_blueprint_alignment": "report:article_supplement_blueprint_alignment",
            "manuscript_section_evidence_packet": "report:manuscript_section_evidence_packet",
            "section_claim_boundary_audit": "report:section_claim_boundary_audit",
            "publication_claim_evidence_verification_matrix": "report:publication_claim_evidence_verification_matrix",
            "publication_citation_registry": "report:publication_citation_registry",
            "publication_exemplar_review": "report:publication_exemplar_review",
            "knowledge_graph_quality_summary": "report:knowledge_graph_quality_summary",
        }
        for source_key, source_id in main_article_source_node_map.items():
            if source_key in (main_article_draft_payload.get("sources") or {}):
                add_edge(
                    edges,
                    main_article_draft_id,
                    source_id,
                    "DERIVED_FROM",
                    evidence_path=str(main_article_draft_json),
                    evidence=f"$.sources.{source_key}",
                )
        for row_index, row in enumerate(
            main_article_draft_payload.get("article_sections") or []
        ):
            section_id = str(row.get("section_id") or "").strip()
            if not section_id:
                continue
            section_node_id = (
                "methodology_control:main_article_draft:"
                f"{slug_fragment(section_id)}"
            )
            add_node(
                nodes,
                section_node_id,
                "methodology_control",
                name=section_id,
                section_id=section_id,
                role=row.get("role"),
                evidence_sources=row.get("evidence_sources") or [],
                evidence_source_count=len(row.get("evidence_sources") or []),
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                positive_claim_promotion_authorized=False,
                release_authorized=False,
                summary=(
                    "Main article draft section "
                    f"`{section_id}` links draft article text to audited "
                    "evidence while final release and method claims remain blocked."
                ),
            )
            add_edge(
                edges,
                main_article_draft_id,
                section_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(main_article_draft_json),
                evidence=row_selector("article_sections", row_index, "section_id"),
            )
            for source_key in row.get("evidence_sources") or []:
                source_id = main_article_source_node_map.get(source_key)
                if source_id:
                    add_edge(
                        edges,
                        section_node_id,
                        source_id,
                        "DERIVED_FROM",
                        evidence_path=str(main_article_draft_json),
                        evidence=f"$.article_sections[{row_index}].evidence_sources",
                    )
    supplementary_document_draft_md = supplementary_document_draft_json.with_suffix(
        ".md"
    )
    if supplementary_document_draft_json.exists():
        supplementary_document_draft_id = "report:supplementary_document_draft"
        add_node(
            nodes,
            supplementary_document_draft_id,
            "report",
            path=(
                str(supplementary_document_draft_md)
                if supplementary_document_draft_md.exists()
                else None
            ),
            json_path=str(supplementary_document_draft_json),
            summary=(
                "Evidence-linked supplementary document draft covering method "
                "selection robustness, post-selection validation, bounded-support "
                "endpoint policy, fairness group diagnostics, duplicate caveats, "
                "and traceability without release or method recommendation."
            ),
        )
        add_edge(
            edges,
            supplementary_document_draft_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(supplementary_document_draft_json),
            evidence="$.summary",
        )
        try:
            supplementary_document_draft_payload = json.loads(
                supplementary_document_draft_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            supplementary_document_draft_payload = {}
        supplementary_source_node_map = {
            "main_article_draft": "report:main_article_draft",
            "individual_experiment_report_draft": "report:individual_experiment_report_draft",
            "article_supplement_blueprint_alignment": "report:article_supplement_blueprint_alignment",
            "method_selection_robustness_audit": "report:method_selection_robustness_audit",
            "method_selection_inferential_audit": "report:method_selection_inferential_audit",
            "method_selection_post_selection_validation_results": "report:method_selection_post_selection_validation_results",
            "dataset_final_gate_post_selection_validation_bridge_results": "report:dataset_final_gate_post_selection_validation_bridge_results",
            "bounded_support_endpoint_closure_audit": "report:bounded_support_endpoint_closure_audit",
            "bounded_support_positive_validation_protocol": "report:bounded_support_positive_validation_protocol",
            "fairness_group_diagnostic_audit": "report:fairness_group_diagnostic_audit",
            "fairness_population_readiness_audit": "report:fairness_population_readiness_audit",
            "fairness_group_multiplicity_scope": "report:fairness_group_multiplicity_scope",
            "duplicate_sensitivity_closure_audit": "report:duplicate_sensitivity_closure_audit",
            "duplicate_content_quarantine_audit": "report:duplicate_content_quarantine_audit",
            "cross_run_integrity_audit": "report:cross_run_integrity_audit",
            "publication_citation_registry": "report:publication_citation_registry",
            "knowledge_graph_quality_summary": "report:knowledge_graph_quality_summary",
        }
        for source_key, source_id in supplementary_source_node_map.items():
            if source_key in (
                supplementary_document_draft_payload.get("sources") or {}
            ):
                add_edge(
                    edges,
                    supplementary_document_draft_id,
                    source_id,
                    "DERIVED_FROM",
                    evidence_path=str(supplementary_document_draft_json),
                    evidence=f"$.sources.{source_key}",
                )
        for row_index, row in enumerate(
            supplementary_document_draft_payload.get("supplement_sections") or []
        ):
            section_id = str(row.get("section_id") or "").strip()
            if not section_id:
                continue
            section_node_id = (
                "methodology_control:supplementary_document_draft:"
                f"{slug_fragment(section_id)}"
            )
            add_node(
                nodes,
                section_node_id,
                "methodology_control",
                name=section_id,
                section_id=section_id,
                role=row.get("role"),
                claim_boundary=row.get("claim_boundary"),
                evidence_sources=row.get("evidence_sources") or [],
                evidence_source_count=len(row.get("evidence_sources") or []),
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                positive_claim_promotion_authorized=False,
                release_authorized=False,
                summary=(
                    "Supplementary document draft section "
                    f"`{section_id}` links supplement text to audited evidence "
                    "while final release and method claims remain blocked."
                ),
            )
            add_edge(
                edges,
                supplementary_document_draft_id,
                section_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(supplementary_document_draft_json),
                evidence=row_selector("supplement_sections", row_index, "section_id"),
            )
            for source_key in row.get("evidence_sources") or []:
                source_id = supplementary_source_node_map.get(source_key)
                if source_id:
                    add_edge(
                        edges,
                        section_node_id,
                        source_id,
                        "DERIVED_FROM",
                        evidence_path=str(supplementary_document_draft_json),
                        evidence=(
                            f"$.supplement_sections[{row_index}].evidence_sources"
                        ),
                    )
    sterile_repository_readme_draft_md = sterile_repository_readme_draft_json.with_suffix(
        ".md"
    )
    if sterile_repository_readme_draft_json.exists():
        sterile_repository_readme_draft_id = "report:sterile_repository_readme_draft"
        add_node(
            nodes,
            sterile_repository_readme_draft_id,
            "report",
            path=(
                str(sterile_repository_readme_draft_md)
                if sterile_repository_readme_draft_md.exists()
                else None
            ),
            json_path=str(sterile_repository_readme_draft_json),
            summary=(
                "Evidence-linked draft README for the future sterile "
                "publication repository, preserving release, method "
                "recommendation, positive-claim, Venn-Abers validation, "
                "bounded-support, and fairness claim boundaries."
            ),
        )
        add_edge(
            edges,
            sterile_repository_readme_draft_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(sterile_repository_readme_draft_json),
            evidence="$.summary",
        )
        try:
            sterile_readme_payload = json.loads(
                sterile_repository_readme_draft_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            sterile_readme_payload = {}
        sterile_readme_source_node_map = {
            "sterile_repository_staging_manifest": "report:sterile_repository_staging_manifest",
            "main_article_draft": "report:main_article_draft",
            "supplementary_document_draft": "report:supplementary_document_draft",
            "individual_experiment_report_draft": "report:individual_experiment_report_draft",
            "research_document": (
                "methodology_control:publication_claim_evidence_draft_artifact:"
                "research_document"
            ),
            "publication_citation_registry": "report:publication_citation_registry",
            "knowledge_graph_quality_summary": "report:knowledge_graph_quality_summary",
            "final_publication_output_authorization_protocol": "report:final_publication_output_authorization_protocol",
            "publication_authoring_decision_record": "report:publication_authoring_decision_record",
            "publication_claim_evidence_verification_matrix": "report:publication_claim_evidence_verification_matrix",
            "private_sterile_publication_package_manifest": "report:private_sterile_publication_package_manifest",
            "private_latex_html_review_output_audit": "report:private_latex_html_review_output_audit",
            "private_publication_repository_remote_audit": "report:private_publication_repository_remote_audit",
        }
        for source_key, source_id in sterile_readme_source_node_map.items():
            if source_key in (sterile_readme_payload.get("sources") or {}):
                add_edge(
                    edges,
                    sterile_repository_readme_draft_id,
                    source_id,
                    "DERIVED_FROM",
                    evidence_path=str(sterile_repository_readme_draft_json),
                    evidence=f"$.sources.{source_key}",
                )
        for row_index, row in enumerate(
            sterile_readme_payload.get("readme_sections") or []
        ):
            section_id = str(row.get("section_id") or "").strip()
            if not section_id:
                continue
            section_node_id = (
                "methodology_control:sterile_repository_readme_draft:"
                f"{slug_fragment(section_id)}"
            )
            add_node(
                nodes,
                section_node_id,
                "methodology_control",
                name=section_id,
                section_id=section_id,
                heading=row.get("heading"),
                evidence_sources=row.get("evidence_sources") or [],
                evidence_source_count=len(row.get("evidence_sources") or []),
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                positive_claim_promotion_authorized=False,
                release_authorized=False,
                summary=(
                    "Sterile repository README draft section "
                    f"`{section_id}` links clean-repository README text to "
                    "audited evidence while final release and method claims "
                    "remain blocked."
                ),
            )
            add_edge(
                edges,
                sterile_repository_readme_draft_id,
                section_node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(sterile_repository_readme_draft_json),
                evidence=row_selector("readme_sections", row_index, "section_id"),
            )
            for source_key in row.get("evidence_sources") or []:
                source_id = sterile_readme_source_node_map.get(source_key)
                if source_id:
                    add_edge(
                        edges,
                        section_node_id,
                        source_id,
                        "DERIVED_FROM",
                        evidence_path=str(sterile_repository_readme_draft_json),
                        evidence=f"$.readme_sections[{row_index}].evidence_sources",
                    )
    reader_primer_alignment_md = reader_primer_section_alignment_json.with_suffix(".md")
    if reader_primer_section_alignment_json.exists():
        reader_primer_alignment_id = "report:reader_primer_section_alignment"
        add_node(
            nodes,
            reader_primer_alignment_id,
            "report",
            path=(
                str(reader_primer_alignment_md)
                if reader_primer_alignment_md.exists()
                else None
            ),
            json_path=str(reader_primer_section_alignment_json),
            summary=(
                "Reader-primer section alignment map linking planned article, "
                "supplement, and individual-report rows to the concept primer "
                "checklist required before any final prose is drafted."
            ),
        )
        add_edge(
            edges,
            reader_primer_alignment_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(reader_primer_section_alignment_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:reader_method_primer_citation_map",
                "$.sources.reader_method_primer_citation_map",
            ),
            (
                "report:article_supplement_blueprint_alignment",
                "$.sources.article_supplement_blueprint_alignment",
            ),
            (
                "report:individual_experiment_report_blueprint",
                "$.sources.individual_experiment_report_blueprint",
            ),
        ):
            add_edge(
                edges,
                reader_primer_alignment_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(reader_primer_section_alignment_json),
                evidence=selector,
            )
        try:
            reader_primer_alignment_payload = json.loads(
                reader_primer_section_alignment_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            reader_primer_alignment_payload = {}
        for row_index, row in enumerate(
            reader_primer_alignment_payload.get("alignment_rows") or []
        ):
            alignment_id = str(row.get("alignment_id") or "").strip()
            if not alignment_id:
                continue
            node_id = (
                "methodology_control:reader_primer_section_alignment:"
                f"{slug_fragment(alignment_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=alignment_id,
                source_family=row.get("source_family"),
                source_row_id=row.get("source_row_id"),
                scientific_reporting_role=row.get("scientific_reporting_role"),
                target_surfaces=row.get("target_surfaces") or [],
                required_concept_ids=row.get("required_concept_ids") or [],
                required_concept_count=len(row.get("required_concept_ids") or []),
                concept_alignment_status=row.get("concept_alignment_status"),
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                positive_claim_promotion_authorized=False,
                summary=(
                    "Reader-primer section alignment row "
                    f"`{alignment_id}` maps a planned publication section or "
                    "surface to required concept explanations before drafting."
                ),
            )
            add_edge(
                edges,
                reader_primer_alignment_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(reader_primer_section_alignment_json),
                evidence=row_selector("alignment_rows", row_index, "alignment_id"),
            )
            for concept_id in row.get("required_concept_ids") or []:
                add_edge(
                    edges,
                    node_id,
                    (
                        "methodology_control:reader_method_primer:"
                        f"{slug_fragment(concept_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(reader_primer_section_alignment_json),
                    evidence=f"$.alignment_rows[{row_index}].required_concept_ids",
                )
    manuscript_claim_citation_md = (
        manuscript_claim_citation_readiness_audit_json.with_suffix(".md")
    )
    if manuscript_claim_citation_readiness_audit_json.exists():
        manuscript_claim_citation_id = (
            "report:manuscript_claim_citation_readiness_audit"
        )
        add_node(
            nodes,
            manuscript_claim_citation_id,
            "report",
            path=(
                str(manuscript_claim_citation_md)
                if manuscript_claim_citation_md.exists()
                else None
            ),
            json_path=str(manuscript_claim_citation_readiness_audit_json),
            summary=(
                "Manuscript claim/citation readiness audit verifying the "
                "current main article and supplementary drafts against "
                "registered citations, reader-primer concept coverage, source "
                "traceability, claim/evidence boundaries, and closed final "
                "output authorizations."
            ),
        )
        add_edge(
            edges,
            manuscript_claim_citation_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(manuscript_claim_citation_readiness_audit_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            ("report:main_article_draft", "$.sources.main_article_draft"),
            (
                "report:supplementary_document_draft",
                "$.sources.supplementary_document_draft",
            ),
            (
                "report:publication_citation_registry",
                "$.sources.publication_citation_registry",
            ),
            (
                "report:reader_method_primer_citation_map",
                "$.sources.reader_method_primer_citation_map",
            ),
            (
                "report:publication_claim_evidence_verification_matrix",
                "$.sources.publication_claim_evidence_verification_matrix",
            ),
            (
                "report:final_publication_output_authorization_protocol",
                "$.sources.final_publication_output_authorization_protocol",
            ),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.knowledge_graph_quality_summary",
            ),
        ):
            add_edge(
                edges,
                manuscript_claim_citation_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(manuscript_claim_citation_readiness_audit_json),
                evidence=selector,
            )
        try:
            manuscript_claim_citation_payload = json.loads(
                manuscript_claim_citation_readiness_audit_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            manuscript_claim_citation_payload = {}
        document_source_ids = {
            "main_article_draft": "report:main_article_draft",
            "supplementary_document_draft": "report:supplementary_document_draft",
        }
        for row_index, row in enumerate(
            manuscript_claim_citation_payload.get("document_rows") or []
        ):
            document_id = str(row.get("document_id") or "").strip()
            if not document_id:
                continue
            node_id = (
                "methodology_control:manuscript_claim_citation_readiness:"
                f"{slug_fragment(document_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=document_id,
                readiness_status=row.get("readiness_status"),
                used_citation_key_count=len(row.get("used_citation_keys") or []),
                required_concept_count=len(row.get("required_concept_ids") or []),
                missing_concept_count=len(row.get("missing_concept_ids") or []),
                unregistered_citation_key_count=len(
                    row.get("unregistered_used_citation_keys") or []
                ),
                missing_reference_key_count=len(row.get("missing_reference_keys") or []),
                authorization_violation_count=len(
                    row.get("authorization_violations") or []
                ),
                final_manuscript_prose_permission=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                method_advocacy_authorized=False,
                positive_claim_promotion_authorized=False,
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Manuscript claim/citation readiness row "
                    f"`{document_id}` is `{row.get('readiness_status')}` with "
                    f"{len(row.get('used_citation_keys') or [])} registered "
                    "body citation key(s) and final prose authorization blocked."
                ),
            )
            add_edge(
                edges,
                manuscript_claim_citation_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(manuscript_claim_citation_readiness_audit_json),
                evidence=row_selector("document_rows", row_index, "document_id"),
            )
            document_report_id = document_source_ids.get(document_id)
            if document_report_id:
                add_edge(
                    edges,
                    node_id,
                    document_report_id,
                    "DERIVED_FROM",
                    evidence_path=str(manuscript_claim_citation_readiness_audit_json),
                    evidence=f"$.document_rows[{row_index}].document_id",
                )
            for concept_row in row.get("concept_rows") or []:
                concept_id = str(concept_row.get("concept_id") or "").strip()
                if not concept_id:
                    continue
                add_edge(
                    edges,
                    node_id,
                    (
                        "methodology_control:reader_method_primer:"
                        f"{slug_fragment(concept_id)}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(manuscript_claim_citation_readiness_audit_json),
                    evidence=f"$.document_rows[{row_index}].concept_rows",
                )
            for citation_key in row.get("used_citation_keys") or []:
                add_edge(
                    edges,
                    node_id,
                    (
                        "methodology_control:publication_citation_registry:"
                        f"{slug_fragment(str(citation_key))}"
                    ),
                    "DERIVED_FROM",
                    evidence_path=str(manuscript_claim_citation_readiness_audit_json),
                    evidence=f"$.document_rows[{row_index}].used_citation_keys",
                )
    neutral_release_cut_md = neutral_publication_release_cut_decision_json.with_suffix(
        ".md"
    )
    if neutral_publication_release_cut_decision_json.exists():
        neutral_release_cut_id = "report:neutral_publication_release_cut_decision"
        add_node(
            nodes,
            neutral_release_cut_id,
            "report",
            path=(
                str(neutral_release_cut_md)
                if neutral_release_cut_md.exists()
                else None
            ),
            json_path=str(neutral_publication_release_cut_decision_json),
            summary=(
                "Neutral publication release-cut decision authorizing private "
                "sterile packaging, neutral article/supplement assembly, "
                "private KG snapshot export, and private LaTeX/HTML/static-site "
                "package preparation while keeping public release, working "
                "repository citation, method recommendation, and positive "
                "claims blocked."
            ),
        )
        add_edge(
            edges,
            neutral_release_cut_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(neutral_publication_release_cut_decision_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:final_publication_output_authorization_protocol",
                "$.sources.final_publication_output_authorization_protocol",
            ),
            (
                "report:manuscript_claim_citation_readiness_audit",
                "$.sources.manuscript_claim_citation_readiness_audit",
            ),
            (
                "report:publication_claim_evidence_verification_matrix",
                "$.sources.publication_claim_evidence_verification_matrix",
            ),
            ("report:main_article_draft", "$.sources.main_article_draft"),
            (
                "report:supplementary_document_draft",
                "$.sources.supplementary_document_draft",
            ),
            (
                "report:individual_experiment_report_draft",
                "$.sources.individual_experiment_report_draft",
            ),
            (
                "report:sterile_repository_staging_manifest",
                "$.sources.sterile_repository_staging_manifest",
            ),
            (
                "report:sterile_repository_readme_draft",
                "$.sources.sterile_repository_readme_draft",
            ),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.knowledge_graph_quality_summary",
            ),
            (
                "report:graph_artifact_readiness_audit",
                "$.sources.graph_artifact_readiness_audit",
            ),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
        ):
            add_edge(
                edges,
                neutral_release_cut_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(neutral_publication_release_cut_decision_json),
                evidence=selector,
            )
        try:
            neutral_release_cut_payload = json.loads(
                neutral_publication_release_cut_decision_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            neutral_release_cut_payload = {}
        action_source_ids = {
            "prepare_private_sterile_repository": (
                "report:sterile_repository_staging_manifest",
                "report:sterile_repository_readme_draft",
            ),
            "assemble_neutral_article_and_supplement_outputs": (
                "report:main_article_draft",
                "report:supplementary_document_draft",
                "report:publication_claim_evidence_verification_matrix",
            ),
            "export_citable_knowledge_graph_snapshot": (
                "report:knowledge_graph_quality_summary",
                "report:graph_artifact_readiness_audit",
            ),
            "prepare_latex_html_and_static_site_package": (
                "report:main_article_draft",
                "report:supplementary_document_draft",
                "report:neutral_reporting_language_audit",
            ),
        }
        for row_index, action in enumerate(
            neutral_release_cut_payload.get("authorized_next_actions") or []
        ):
            action_id = str(action.get("action_id") or "").strip()
            if not action_id:
                continue
            node_id = (
                "methodology_control:neutral_publication_release_cut:"
                f"{slug_fragment(action_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=action_id,
                authorization_status=action.get("authorization_status"),
                scope=action.get("scope"),
                must_preserve=action.get("must_preserve") or [],
                private_packaging_authorized=True,
                public_release_authorized=False,
                working_repository_final_citable=False,
                method_recommendation_authorized=False,
                method_champion_authorized=False,
                method_advocacy_authorized=False,
                positive_claim_promotion_authorized=False,
                raw_data_or_secret_inclusion_authorized=False,
                summary=(
                    "Neutral publication release-cut action "
                    f"`{action_id}` is authorized only for private neutral "
                    "packaging; public release and promotional claims remain "
                    "blocked."
                ),
            )
            add_edge(
                edges,
                neutral_release_cut_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(neutral_publication_release_cut_decision_json),
                evidence=row_selector(
                    "authorized_next_actions", row_index, "action_id"
                ),
            )
            for source_id in action_source_ids.get(action_id, ()):
                add_edge(
                    edges,
                    node_id,
                    source_id,
                    "DERIVED_FROM",
                    evidence_path=str(neutral_publication_release_cut_decision_json),
                    evidence=f"$.authorized_next_actions[{row_index}].action_id",
                )
    private_latex_html_md = (
        private_latex_html_review_outputs_manifest_json.with_suffix(".md")
    )
    if private_latex_html_review_outputs_manifest_json.exists():
        private_latex_html_report_id = (
            "report:private_latex_html_review_outputs_manifest"
        )
        add_node(
            nodes,
            private_latex_html_report_id,
            "report",
            path=str(private_latex_html_md) if private_latex_html_md.exists() else None,
            json_path=str(private_latex_html_review_outputs_manifest_json),
            summary=(
                "Private LaTeX/HTML review output manifest for the current "
                "article and supplementary draft renders. It records review "
                "LaTeX, HTML, BibTeX, and static index outputs while keeping "
                "final prose, public release, method recommendation, and "
                "positive claims blocked."
            ),
        )
        add_edge(
            edges,
            private_latex_html_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(private_latex_html_review_outputs_manifest_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:neutral_publication_release_cut_decision",
                "$.sources.neutral_publication_release_cut_decision",
            ),
            ("report:main_article_draft", "$.sources.main_article_draft"),
            (
                "report:supplementary_document_draft",
                "$.sources.supplementary_document_draft",
            ),
            (
                "report:publication_citation_registry",
                "$.sources.publication_citation_registry",
            ),
        ):
            add_edge(
                edges,
                private_latex_html_report_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(private_latex_html_review_outputs_manifest_json),
                evidence=selector,
            )
        try:
            private_latex_html_payload = json.loads(
                private_latex_html_review_outputs_manifest_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            private_latex_html_payload = {}
        private_latex_html_summary = private_latex_html_payload.get("summary") or {}
        render_manifest_id = "manifest:private_latex_html_review_outputs"
        add_node(
            nodes,
            render_manifest_id,
            "manifest",
            output_dir=private_latex_html_summary.get("output_dir"),
            output_count=private_latex_html_summary.get("output_count"),
            latex_output_count=private_latex_html_summary.get("latex_output_count"),
            html_output_count=private_latex_html_summary.get("html_output_count"),
            bibtex_output_count=private_latex_html_summary.get("bibtex_output_count"),
            secret_pattern_hit_count=private_latex_html_summary.get(
                "secret_pattern_hit_count"
            ),
            public_release_authorized=False,
            working_repository_final_citable=False,
            final_manuscript_prose_permission=False,
            method_recommendation_authorized=False,
            method_champion_authorized=False,
            method_advocacy_authorized=False,
            positive_claim_promotion_authorized=False,
            raw_data_or_secret_inclusion_authorized=False,
            summary=(
                "Private review render manifest for article and supplement "
                "LaTeX/HTML outputs with final prose and public release blocked."
            ),
        )
        add_edge(
            edges,
            private_latex_html_report_id,
            render_manifest_id,
            "SUMMARIZES_MANIFEST",
            evidence_path=str(private_latex_html_review_outputs_manifest_json),
            evidence="$.summary",
        )
        for source_id in (
            "report:neutral_publication_release_cut_decision",
            "report:main_article_draft",
            "report:supplementary_document_draft",
            "report:publication_citation_registry",
        ):
            add_edge(
                edges,
                render_manifest_id,
                source_id,
                "SUPPORTED_BY",
                evidence_path=str(private_latex_html_review_outputs_manifest_json),
                evidence="$.summary",
            )
    private_latex_html_audit_md = (
        private_latex_html_review_output_audit_json.with_suffix(".md")
    )
    if private_latex_html_review_output_audit_json.exists():
        private_latex_html_audit_report_id = (
            "report:private_latex_html_review_output_audit"
        )
        add_node(
            nodes,
            private_latex_html_audit_report_id,
            "report",
            path=(
                str(private_latex_html_audit_md)
                if private_latex_html_audit_md.exists()
                else None
            ),
            json_path=str(private_latex_html_review_output_audit_json),
            summary=(
                "Private LaTeX/HTML review output audit. It verifies output "
                "hashes, HTML citation/link quality, LaTeX/BibTeX compilation, "
                "secret-pattern absence, and closed public/final/method-positive "
                "authorization flags for private review renders."
            ),
        )
        add_edge(
            edges,
            private_latex_html_audit_report_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(private_latex_html_review_output_audit_json),
            evidence="$.summary",
        )
        add_edge(
            edges,
            private_latex_html_audit_report_id,
            "report:private_latex_html_review_outputs_manifest",
            "DERIVED_FROM",
            evidence_path=str(private_latex_html_review_output_audit_json),
            evidence="$.sources.private_latex_html_review_outputs_manifest",
        )
    private_package_md = private_sterile_publication_package_manifest_json.with_suffix(
        ".md"
    )
    if private_sterile_publication_package_manifest_json.exists():
        private_package_id = "report:private_sterile_publication_package_manifest"
        add_node(
            nodes,
            private_package_id,
            "report",
            path=str(private_package_md) if private_package_md.exists() else None,
            json_path=str(private_sterile_publication_package_manifest_json),
            summary=(
                "Private sterile publication package manifest for the local "
                "review package. It records copied files, excluded files, "
                "checksum provenance, secret/raw/cache risk checks, and local "
                "git provenance while keeping public release, working "
                "repository citation, method recommendation, and positive "
                "claims blocked."
            ),
        )
        add_edge(
            edges,
            private_package_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(private_sterile_publication_package_manifest_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "report:neutral_publication_release_cut_decision",
                "$.sources.neutral_publication_release_cut_decision",
            ),
            (
                "report:sterile_repository_staging_manifest",
                "$.sources.sterile_repository_staging_manifest",
            ),
            (
                "report:private_latex_html_review_outputs_manifest",
                "$.sources.private_latex_html_review_outputs_manifest",
            ),
            (
                "report:private_latex_html_review_output_audit",
                "$.sources.private_latex_html_review_output_audit",
            ),
        ):
            add_edge(
                edges,
                private_package_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(private_sterile_publication_package_manifest_json),
                evidence=selector,
            )
        try:
            private_package_payload = json.loads(
                private_sterile_publication_package_manifest_json.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError:
            private_package_payload = {}
        private_package_summary = private_package_payload.get("summary") or {}
        package_node_id = "manifest:private_sterile_publication_review_package"
        add_node(
            nodes,
            package_node_id,
            "manifest",
            package_root=private_package_summary.get("package_root"),
            local_git_initialized=private_package_summary.get(
                "local_git_initialized"
            ),
            local_git_commit_recorded=bool(
                private_package_summary.get("local_git_commit")
            ),
            copied_file_count=private_package_summary.get("copied_file_count"),
            excluded_file_count=private_package_summary.get("excluded_file_count"),
            packaged_bytes=private_package_summary.get("packaged_bytes"),
            private_latex_html_output_audit_status=private_package_summary.get(
                "private_latex_html_output_audit_status"
            ),
            path_risk_hit_count=private_package_summary.get("path_risk_hit_count"),
            secret_pattern_hit_count=private_package_summary.get(
                "secret_pattern_hit_count"
            ),
            public_release_authorized=False,
            working_repository_final_citable=False,
            method_recommendation_authorized=False,
            method_champion_authorized=False,
            method_advocacy_authorized=False,
            positive_claim_promotion_authorized=False,
            raw_data_or_secret_inclusion_authorized=False,
            summary=(
                "Local private sterile publication review package generated "
                "from allow-listed publication sources with raw/cache/secret "
                "risk checks passing and public release still blocked."
            ),
        )
        add_edge(
            edges,
            private_package_id,
            package_node_id,
            "SUMMARIZES_MANIFEST",
            evidence_path=str(private_sterile_publication_package_manifest_json),
            evidence="$.summary",
        )
        for source_id in (
            "report:neutral_publication_release_cut_decision",
            "report:sterile_repository_staging_manifest",
            "report:private_latex_html_review_outputs_manifest",
            "report:private_latex_html_review_output_audit",
            "report:knowledge_graph_quality_summary",
        ):
            add_edge(
                edges,
                package_node_id,
                source_id,
                "SUPPORTED_BY",
                evidence_path=str(private_sterile_publication_package_manifest_json),
                evidence="$.summary",
            )
    private_remote_audit_md = (
        private_publication_repository_remote_audit_json.with_suffix(".md")
    )
    if private_publication_repository_remote_audit_json.exists():
        private_remote_audit_id = "report:private_publication_repository_remote_audit"
        add_node(
            nodes,
            private_remote_audit_id,
            "report",
            path=(
                str(private_remote_audit_md)
                if private_remote_audit_md.exists()
                else None
            ),
            json_path=str(private_publication_repository_remote_audit_json),
            summary=(
                "Private publication repository remote audit recording private "
                "GitHub visibility, local/remote commit match, and closed public "
                "release boundaries for the sterile review package."
            ),
        )
        add_edge(
            edges,
            private_remote_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(private_publication_repository_remote_audit_json),
            evidence="$.summary",
        )
        if private_sterile_publication_package_manifest_json.exists():
            add_edge(
                edges,
                private_remote_audit_id,
                "report:private_sterile_publication_package_manifest",
                "DERIVED_FROM",
                evidence_path=str(private_publication_repository_remote_audit_json),
                evidence="$.summary.local_package_commit",
            )
    if sterile_repository_staging_manifest_json.exists():
        sterile_manifest_id = "report:sterile_repository_staging_manifest"
        add_node(
            nodes,
            sterile_manifest_id,
            "report",
            path=(
                str(sterile_manifest_md)
                if sterile_manifest_md.exists()
                else None
            ),
            json_path=str(sterile_repository_staging_manifest_json),
            summary=(
                "Sterile final-repository staging manifest that maps required "
                "publication-release contents, exclusion policies, and source "
                "provenance while keeping repository creation, release, working "
                "repository citation, method recommendation, and positive claims "
                "unauthorized."
            ),
        )
        add_edge(
            edges,
            sterile_manifest_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(sterile_repository_staging_manifest_json),
            evidence="$.summary",
        )
        for source_id, selector in (
            (
                "catalog:post_experiment_publication_program",
                "$.sources.post_experiment_publication_program",
            ),
            (
                "report:publication_release_gap_register",
                "$.sources.publication_release_gap_register",
            ),
            (
                "report:final_publication_output_authorization_protocol",
                "$.sources.final_publication_output_authorization_protocol",
            ),
            ("report:goal_completion_audit", "$.sources.goal_completion_audit"),
            (
                "report:neutral_reporting_language_audit",
                "$.sources.neutral_reporting_language_audit",
            ),
            (
                "report:knowledge_graph_quality_summary",
                "$.sources.knowledge_graph_quality_summary",
            ),
            (
                "report:kg_publication_quality_audit",
                "$.sources.kg_publication_quality_audit",
            ),
            (
                "report:graph_artifact_readiness_audit",
                "$.sources.graph_artifact_readiness_audit",
            ),
            (
                "report:section_claim_boundary_audit",
                "$.sources.section_claim_boundary_audit",
            ),
            (
                "report:article_supplement_kg_navigation_index",
                "$.sources.article_supplement_kg_navigation_index",
            ),
            (
                "report:final_publication_visual_auditor_readiness",
                "$.sources.final_publication_visual_auditor_readiness",
            ),
        ):
            add_edge(
                edges,
                sterile_manifest_id,
                source_id,
                "DERIVED_FROM",
                evidence_path=str(sterile_repository_staging_manifest_json),
                evidence=selector,
            )
        try:
            sterile_manifest_payload = json.loads(
                sterile_repository_staging_manifest_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            sterile_manifest_payload = {}
        source_id_by_path = {
            "post_experiment_publication_program.json": (
                "catalog:post_experiment_publication_program"
            ),
            "publication_release_gap_register.json": (
                "report:publication_release_gap_register"
            ),
            "final_publication_output_authorization_protocol.json": (
                "report:final_publication_output_authorization_protocol"
            ),
            "goal_completion_audit.json": "report:goal_completion_audit",
            "neutral_reporting_language_audit.json": (
                "report:neutral_reporting_language_audit"
            ),
            "quality_summary.json": "report:knowledge_graph_quality_summary",
            "kg_publication_quality_audit.json": (
                "report:kg_publication_quality_audit"
            ),
            "graph_artifact_readiness_audit.json": (
                "report:graph_artifact_readiness_audit"
            ),
            "section_claim_boundary_audit.json": (
                "report:section_claim_boundary_audit"
            ),
            "article_supplement_blueprint_alignment.json": (
                "report:article_supplement_blueprint_alignment"
            ),
            "manuscript_section_evidence_packet.json": (
                "report:manuscript_section_evidence_packet"
            ),
            "claim_safe_result_extraction_matrix.json": (
                "report:claim_safe_result_extraction_matrix"
            ),
            "individual_experiment_report_blueprint.json": (
                "report:individual_experiment_report_blueprint"
            ),
            "article_supplement_kg_navigation_index.json": (
                "report:article_supplement_kg_navigation_index"
            ),
            "article_supplement_kg_triptych_decision.json": (
                "report:article_supplement_kg_triptych_decision"
            ),
            "main_article_draft.md": "report:main_article_draft",
            "main_article_draft.json": "report:main_article_draft",
            "supplementary_document_draft.md": (
                "report:supplementary_document_draft"
            ),
            "supplementary_document_draft.json": (
                "report:supplementary_document_draft"
            ),
            "individual_experiment_report_draft.md": (
                "report:individual_experiment_report_draft"
            ),
            "individual_experiment_report_draft.json": (
                "report:individual_experiment_report_draft"
            ),
            "publication_citation_registry.md": (
                "report:publication_citation_registry"
            ),
            "publication_citation_registry.json": (
                "report:publication_citation_registry"
            ),
            "references.bib": "report:publication_citation_registry",
            "final_publication_visual_auditor_readiness.json": (
                "report:final_publication_visual_auditor_readiness"
            ),
            "sterile_repository_readme_draft.md": (
                "report:sterile_repository_readme_draft"
            ),
            "sterile_repository_readme_draft.json": (
                "report:sterile_repository_readme_draft"
            ),
            "README.md": "doc:root_readme",
            "experiments/regression/manuscript/README.md": (
                "catalog:manuscript_workspace_readme"
            ),
            "experiments/regression/CHANGELOG.md": "catalog:regression_changelog",
        }
        for row_index, row in enumerate(
            sterile_manifest_payload.get("required_content_rows") or []
        ):
            content_id = str(row.get("content_id") or "").strip()
            if not content_id:
                continue
            node_id = (
                "methodology_control:sterile_repository_required_content:"
                f"{slug_fragment(content_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=content_id,
                package_family=row.get("package_family"),
                staging_status=row.get("staging_status"),
                blocking_gate=row.get("blocking_gate"),
                source_traceability_status=row.get("source_traceability_status"),
                candidate_exclusion_risk_hit_count=len(
                    row.get("candidate_exclusion_risk_hits") or []
                ),
                final_content_authorized=row.get("final_content_authorized"),
                release_authorized=row.get("release_authorized"),
                claim_boundary=row.get("claim_boundary"),
                summary=(
                    "Sterile repository required-content row "
                    f"`{content_id}` is `{row.get('staging_status')}` and "
                    f"blocked by `{row.get('blocking_gate')}`; final copying "
                    "and release remain unauthorized."
                ),
            )
            add_edge(
                edges,
                sterile_manifest_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(sterile_repository_staging_manifest_json),
                evidence=row_selector("required_content_rows", row_index, "content_id"),
            )
            blocking_gate = row.get("blocking_gate")
            if blocking_gate:
                blocking_gate_id = (
                    "methodology_control:sterile_repository_blocking_gate:"
                    f"{slug_fragment(str(blocking_gate))}"
                )
                add_node(
                    nodes,
                    blocking_gate_id,
                    "methodology_control",
                    name=str(blocking_gate),
                    summary=(
                        "Sterile repository staging blocker that must remain "
                        "closed before final repository creation or release."
                    ),
                )
                add_edge(
                    edges,
                    node_id,
                    blocking_gate_id,
                    "DERIVED_FROM",
                    evidence_path=str(sterile_repository_staging_manifest_json),
                    evidence=(
                        f"$.required_content_rows[{row_index}].blocking_gate"
                    ),
                )
                final_auth_gate_id = (
                    "methodology_control:final_publication_output_authorization:"
                    f"{slug_fragment(str(blocking_gate))}"
                )
                if final_auth_gate_id in nodes:
                    add_edge(
                        edges,
                        blocking_gate_id,
                        final_auth_gate_id,
                        "DERIVED_FROM",
                        evidence_path=str(sterile_repository_staging_manifest_json),
                        evidence=(
                            f"$.required_content_rows[{row_index}].blocking_gate"
                        ),
                    )
            for source_path in row.get("source_artifacts") or []:
                source_node_id = source_id_by_path.get(
                    str(source_path)
                ) or source_id_by_path.get(Path(str(source_path)).name)
                if source_node_id:
                    add_edge(
                        edges,
                        node_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(sterile_repository_staging_manifest_json),
                        evidence=(
                            f"$.required_content_rows[{row_index}]"
                            ".source_artifacts"
                        ),
                    )
        for row_index, row in enumerate(
            sterile_manifest_payload.get("exclusion_policy_rows") or []
        ):
            exclusion_id = str(row.get("exclusion_id") or "").strip()
            if not exclusion_id:
                continue
            node_id = (
                "methodology_control:sterile_repository_exclusion_policy:"
                f"{slug_fragment(exclusion_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=exclusion_id,
                source=row.get("source"),
                pattern_count=len(row.get("patterns") or []),
                tracked_path_hit_count=row.get("tracked_path_hit_count"),
                source_traceability_status=row.get("source_traceability_status"),
                rationale=row.get("rationale"),
                summary=(
                    "Sterile repository exclusion-policy row "
                    f"`{exclusion_id}` excludes non-citable, risky, raw, "
                    "secret, cache, or unapproved working artifacts from the "
                    "future clean repository."
                ),
            )
            add_edge(
                edges,
                sterile_manifest_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(sterile_repository_staging_manifest_json),
                evidence=row_selector(
                    "exclusion_policy_rows", row_index, "exclusion_id"
                ),
            )
            for source_path in row.get("source_artifacts") or []:
                source_node_id = source_id_by_path.get(
                    str(source_path)
                ) or source_id_by_path.get(Path(str(source_path)).name)
                if source_node_id:
                    add_edge(
                        edges,
                        node_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(sterile_repository_staging_manifest_json),
                        evidence=(
                            f"$.exclusion_policy_rows[{row_index}]"
                            ".source_artifacts"
                        ),
                    )
    neutral_result_ledger_md = neutral_result_ledger_json.with_suffix(".md")
    if neutral_result_ledger_json.exists():
        neutral_result_ledger_id = "report:neutral_result_ledger"
        add_node(
            nodes,
            neutral_result_ledger_id,
            "report",
            path=(
                str(neutral_result_ledger_md)
                if neutral_result_ledger_md.exists()
                else None
            ),
            json_path=str(neutral_result_ledger_json),
            summary=(
                "Neutral claim-bounded result ledger that records observed "
                "regression CP findings without final method selection, final "
                "prose, sterile repository release, or positive method promotion."
            ),
        )
        add_edge(edges, neutral_result_ledger_id, methodology_report_id, "SUPPORTS_REPORT")
        source_report_ids = {
            "experiment_accounting_audit.json": "report:experiment_accounting_audit",
            "method_performance_synthesis.json": "report:method_performance_synthesis",
            "method_selection_robustness_audit.json": "report:method_selection_robustness_audit",
            "selection_multiplicity_evidence_record.json": "report:selection_multiplicity_evidence_record",
            "venn_abers_claim_gate_matrix.json": "report:venn_abers_claim_gate_matrix",
            "venn_abers_negative_evidence_disposition_audit.json": "report:venn_abers_negative_evidence_disposition_audit",
            "venn_abers_grid_failure_mode_decomposition.json": "report:venn_abers_grid_failure_mode_decomposition",
            "bounded_support_endpoint_closure_audit.json": "report:bounded_support_endpoint_closure_audit",
            "bounded_support_positive_validation_protocol.json": "report:bounded_support_positive_validation_protocol",
            "fairness_group_diagnostic_audit.json": "report:fairness_group_diagnostic_audit",
            "fairness_population_readiness_audit.json": "report:fairness_population_readiness_audit",
            "visual_table_render_candidate_audit.json": "report:publication_visual_table_render_candidate_audit",
            "publication_retention_readiness_audit.json": "report:publication_retention_readiness_audit",
            "kg_navigation_usability_audit.json": "report:kg_navigation_usability_audit",
            "graph_artifact_readiness_audit.json": "report:graph_artifact_readiness_audit",
            "neutral_reporting_language_audit.json": "report:neutral_reporting_language_audit",
            "goal_completion_audit.json": "report:goal_completion_audit",
            "publication_preparation_packets.json": "report:publication_preparation_packets",
        }
        try:
            ledger_payload = json.loads(
                neutral_result_ledger_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            ledger_payload = {}
        for row_index, row in enumerate(ledger_payload.get("result_rows") or []):
            result_id = str(row.get("result_id") or "").strip()
            if not result_id:
                continue
            node_id = f"methodology_control:neutral_result_ledger:{slug_fragment(result_id)}"
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=result_id,
                result_family=row.get("result_family"),
                evidence_strength=row.get("evidence_strength"),
                claim_status=row.get("claim_status"),
                source_traceability_status=row.get("source_traceability_status"),
                final_method_selection_authorized=row.get(
                    "final_method_selection_authorized"
                ),
                final_visual_table_retention_authorized=row.get(
                    "final_visual_table_retention_authorized"
                ),
                final_manuscript_prose_permission=row.get(
                    "final_manuscript_prose_permission"
                ),
                positive_claim_promotion_authorized=row.get(
                    "positive_claim_promotion_authorized"
                ),
                sterile_repository_creation_authorized=row.get(
                    "sterile_repository_creation_authorized"
                ),
                summary=(
                    "Neutral result ledger row "
                    f"`{result_id}` records `{row.get('claim_status')}` "
                    "without positive claim promotion."
                ),
            )
            add_edge(
                edges,
                neutral_result_ledger_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(neutral_result_ledger_json),
                evidence=row_selector("result_rows", row_index, "result_id"),
            )
            for source_path in row.get("source_artifacts") or []:
                source_name = Path(str(source_path)).name
                source_id = source_report_ids.get(source_name)
                if not source_id:
                    continue
                add_edge(
                    edges,
                    node_id,
                    source_id,
                    "DERIVED_FROM",
                    evidence_path=str(neutral_result_ledger_json),
                    evidence=(
                        f"$.result_rows[{row_index}].source_artifacts"
                        f"[?(@ == {json.dumps(str(source_path))})]"
                    ),
                )
                add_edge(
                    edges,
                    neutral_result_ledger_id,
                    source_id,
                    "DERIVED_FROM",
                    evidence_path=str(neutral_result_ledger_json),
                    evidence=(
                        f"$.result_rows[{row_index}].source_artifacts"
                        f"[?(@ == {json.dumps(str(source_path))})]"
                    ),
                )

    neutral_reporting_language_md = neutral_reporting_language_json.with_suffix(".md")
    if neutral_reporting_language_json.exists():
        neutral_reporting_language_id = "report:neutral_reporting_language_audit"
        add_node(
            nodes,
            neutral_reporting_language_id,
            "report",
            path=(
                str(neutral_reporting_language_md)
                if neutral_reporting_language_md.exists()
                else None
            ),
            json_path=str(neutral_reporting_language_json),
            summary=(
                "Audit of neutral scientific-reporting language that keeps method "
                "promotion, final-selection, fairness, bounded-support, production, "
                "and Venn-Abers claims guarded by explicit claim boundaries."
            ),
        )
        add_edge(
            edges,
            neutral_reporting_language_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            ("report:paper_gate_closure_map", paper_gate_closure_map_json),
            (
                "report:post_experiment_publication_activation_audit",
                post_experiment_publication_activation_json,
            ),
            (
                "report:publication_methodology_audit",
                publication_methodology_audit_json,
            ),
            (
                "report:scientific_review_finding_register",
                scientific_review_register_json,
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    neutral_reporting_language_id,
                    support_id,
                    "DERIVED_FROM",
                    evidence_path=str(neutral_reporting_language_json),
                    evidence="$.source_artifacts",
                )
        try:
            neutral_language_audit = json.loads(
                neutral_reporting_language_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            neutral_language_audit = {}
        for check_index, check in enumerate(neutral_language_audit.get("checks") or []):
            check_id = str(check.get("check_id") or "").strip()
            if not check_id:
                continue
            node_id = (
                "methodology_control:neutral_reporting_language:"
                f"{slug_fragment(check_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=check_id,
                status=check.get("status"),
                blocks_neutral_reporting=check.get("blocks_neutral_reporting"),
                blocker=check.get("blocker"),
                source_artifacts=check.get("source_artifacts"),
                summary=(
                    "Neutral reporting language check "
                    f"`{check_id}` has status {check.get('status')}."
                ),
            )
            add_edge(
                edges,
                neutral_reporting_language_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(neutral_reporting_language_json),
                evidence=row_selector("checks", check_index, "check_id"),
            )

    neutral_experiment_closure_md = neutral_experiment_closure_json.with_suffix(".md")
    if neutral_experiment_closure_json.exists():
        neutral_experiment_closure_id = "report:neutral_experiment_closure_audit"
        add_node(
            nodes,
            neutral_experiment_closure_id,
            "report",
            path=(
                str(neutral_experiment_closure_md)
                if neutral_experiment_closure_md.exists()
                else None
            ),
            json_path=str(neutral_experiment_closure_json),
            summary=(
                "Audit of neutral no-promotion experiment-closure readiness before "
                "any goal-policy update, manuscript drafting, or sterile repository "
                "creation."
            ),
        )
        add_edge(
            edges,
            neutral_experiment_closure_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            ("report:goal_completion_audit", goal_completion_audit_json),
            ("report:paper_gate_closure_map", paper_gate_closure_map_json),
            (
                "report:paper_gate_closure_execution_plan",
                paper_gate_execution_plan_json,
            ),
            (
                "report:post_experiment_publication_activation_audit",
                post_experiment_publication_activation_json,
            ),
            ("report:experiment_accounting_audit", experiment_accounting_json),
            ("report:method_literature_coverage_audit", method_literature_audit_json),
            ("report:method_performance_synthesis", method_performance_json),
            (
                "report:publication_methodology_audit",
                publication_methodology_audit_json,
            ),
            (
                "report:neutral_reporting_language_audit",
                neutral_reporting_language_json,
            ),
            (
                "report:scientific_review_finding_register",
                scientific_review_register_json,
            ),
            ("report:knowledge_graph_quality_summary", knowledge_graph_quality_json),
            ("report:kg_publication_quality_audit", kg_publication_quality_json),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    neutral_experiment_closure_id,
                    support_id,
                    "DERIVED_FROM",
                    evidence_path=str(neutral_experiment_closure_json),
                    evidence="$.source_artifacts",
                )
        try:
            neutral_closure_audit = json.loads(
                neutral_experiment_closure_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            neutral_closure_audit = {}
        for check_index, check in enumerate(neutral_closure_audit.get("checks") or []):
            check_id = str(check.get("check_id") or "").strip()
            if not check_id:
                continue
            node_id = (
                "methodology_control:neutral_experiment_closure:"
                f"{slug_fragment(check_id)}"
            )
            add_node(
                nodes,
                node_id,
                "methodology_control",
                name=check_id,
                status=check.get("status"),
                blocks_neutral_closure=check.get("blocks_neutral_closure"),
                blocker=check.get("blocker"),
                source_artifacts=check.get("source_artifacts"),
                summary=(
                    "Neutral experiment closure check "
                    f"`{check_id}` has status {check.get('status')}."
                ),
            )
            add_edge(
                edges,
                neutral_experiment_closure_id,
                node_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(neutral_experiment_closure_json),
                evidence=row_selector("checks", check_index, "check_id"),
            )

    goal_completion_audit_md = goal_completion_audit_json.with_suffix(".md")
    if goal_completion_audit_json.exists():
        goal_completion_audit_id = "report:goal_completion_audit"
        add_node(
            nodes,
            goal_completion_audit_id,
            "report",
            path=(
                str(goal_completion_audit_md)
                if goal_completion_audit_md.exists()
                else None
            ),
            json_path=str(goal_completion_audit_json),
            summary=(
                "Goal completion audit mapping the original regression CP "
                "objective to proven, scoped, blocked, and deferred evidence."
            ),
        )
        add_edge(
            edges,
            goal_completion_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for source_id in (
            "report:manuscript_readiness_map",
            "report:paper_gate_closure_map",
            "report:paper_gate_closure_execution_plan",
            "report:paper_gate_protocol_design_bundle",
            "report:fairness_sampling_weight_policy",
            "report:publication_methodology_audit",
            "report:experiment_accounting_audit",
            "report:method_literature_coverage_audit",
            "report:method_performance_synthesis",
            "report:knowledge_graph_quality_summary",
            "catalog:post_experiment_publication_program",
            "report:post_experiment_publication_activation_audit",
            "report:neutral_reporting_language_audit",
            "report:graph_artifact_readiness_audit",
            "report:scientific_review_finding_register",
        ):
            if source_id in nodes:
                add_edge(
                    edges,
                    goal_completion_audit_id,
                    source_id,
                    "DERIVED_FROM",
                )
        if "report:post_experiment_publication_activation_audit" in nodes:
            add_edge(
                edges,
                "report:post_experiment_publication_activation_audit",
                goal_completion_audit_id,
                "DERIVED_FROM",
                evidence_path=str(post_experiment_publication_activation_json),
                evidence="$.sources.goal_completion_audit",
            )
        try:
            goal_completion_audit = json.loads(
                goal_completion_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            goal_completion_audit = {}
        path_index = build_node_path_index(nodes)
        for requirement in goal_completion_audit.get("requirement_rows", []) or []:
            if not isinstance(requirement, dict) or not requirement.get(
                "requirement_id"
            ):
                continue
            requirement_id = str(requirement["requirement_id"])
            control_id = (
                "methodology_control:goal_completion:"
                f"{slug_fragment(requirement_id)}"
            )
            add_node(
                nodes,
                control_id,
                "methodology_control",
                requirement_id=requirement_id,
                completion_status=requirement.get("status"),
                completion_ready=requirement.get("completion_ready"),
                blockers=requirement.get("blockers"),
                next_action=requirement.get("next_action"),
                scope_limit=requirement.get("scope_limit"),
                summary=(
                    f"Goal completion requirement `{requirement_id}` has "
                    f"status {requirement.get('status')}."
                ),
            )
            add_edge(
                edges,
                goal_completion_audit_id,
                control_id,
                "SUMMARIZES_CONTROL",
                evidence_path=str(goal_completion_audit_json),
                evidence=goal_completion_requirement_json_selector(requirement_id),
                provenance_mode="goal_completion_requirement_selector",
            )
            if requirement_id.startswith("paper_gate:"):
                gate_key = requirement_id.split(":", 1)[1]
                paper_gate_id = f"paper_gate:{slug_fragment(gate_key)}"
                if paper_gate_id in nodes:
                    add_edge(
                        edges,
                        goal_completion_audit_id,
                        paper_gate_id,
                        "SUMMARIZES_CONTROL",
                        evidence_path=str(goal_completion_audit_json),
                        evidence=goal_completion_requirement_json_selector(
                            requirement_id
                        ),
                        provenance_mode="goal_completion_paper_gate_summary",
                    )
            for artifact_path in requirement.get("source_artifacts", []) or []:
                for source_node_id in artifact_support_node_ids(
                    nodes, path_index, artifact_path
                ):
                    if nodes.get(source_node_id, {}).get("type") not in {
                        "audit",
                        "catalog",
                        "report",
                    }:
                        continue
                    add_edge(
                        edges,
                        goal_completion_audit_id,
                        source_node_id,
                        "DERIVED_FROM",
                        evidence_path=str(goal_completion_audit_json),
                        evidence=goal_completion_requirement_json_selector(
                            requirement_id,
                            "source_artifacts",
                            artifact_path,
                        ),
                        artifact_path=str(artifact_path),
                        provenance_mode="goal_completion_requirement_source_artifact",
                    )
    graph_artifact_audit_md = graph_artifact_audit_json.with_suffix(".md")
    if graph_artifact_audit_json.exists():
        graph_artifact_audit_id = "report:graph_artifact_readiness_audit"
        add_node(
            nodes,
            graph_artifact_audit_id,
            "report",
            path=(
                str(graph_artifact_audit_md)
                if graph_artifact_audit_md.exists()
                else None
            ),
            json_path=str(graph_artifact_audit_json),
            summary="Audit of Mermaid graph artifact freshness, required current audit tokens, and knowledge-graph traceability.",
        )
        add_edge(
            edges,
            graph_artifact_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        add_edge(
            edges,
            graph_artifact_audit_id,
            "catalog:knowledge_graph",
            "DERIVED_FROM",
        )
        for graph_id in (
            "system_ontology",
            "data_flow",
            "control_flow",
            "dependency_graph",
        ):
            add_edge(
                edges,
                graph_artifact_audit_id,
                f"graph:{graph_id}",
                "AUDITS_GRAPH",
            )
    final_selection_audit_md = final_selection_audit_json.with_suffix(".md")
    if final_selection_audit_json.exists():
        final_selection_audit_id = "report:final_selection_claim_boundary_audit"
        add_node(
            nodes,
            final_selection_audit_id,
            "report",
            path=(
                str(final_selection_audit_md)
                if final_selection_audit_md.exists()
                else None
            ),
            json_path=str(final_selection_audit_json),
            summary="Audit of the study-wide final-selection, fairness, endpoint-validity, production, and Venn-Abers-validation blocked claim boundary.",
        )
        add_edge(
            edges,
            final_selection_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "catalog:manuscript_claim_register",
                Path("experiments/regression/catalogs/manuscript_claim_register.json"),
            ),
            ("report:integrity_remediation_backlog", remediation_backlog_json),
            ("report:retrospective_methodology_controls", retrospective_controls_json),
            (
                "report:manuscript_manifest_completeness_audit",
                manuscript_manifest_audit_json,
            ),
        ):
            if support_path.exists():
                add_edge(edges, final_selection_audit_id, support_id, "DERIVED_FROM")
    venn_abers_validation_audit_md = venn_abers_validation_audit_json.with_suffix(".md")
    if venn_abers_validation_audit_json.exists():
        venn_abers_validation_audit_id = "report:venn_abers_validation_readiness_audit"
        add_node(
            nodes,
            venn_abers_validation_audit_id,
            "report",
            path=(
                str(venn_abers_validation_audit_md)
                if venn_abers_validation_audit_md.exists()
                else None
            ),
            json_path=str(venn_abers_validation_audit_json),
            summary="Audit of the Venn-Abers regression validation blocked boundary, fast-bridge negative evidence, split-fallback role, and grid-reference diagnostics.",
        )
        add_edge(
            edges,
            venn_abers_validation_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "catalog:manuscript_claim_register",
                Path("experiments/regression/catalogs/manuscript_claim_register.json"),
            ),
            ("report:final_selection_claim_boundary_audit", final_selection_audit_json),
        ):
            if support_path.exists():
                add_edge(
                    edges, venn_abers_validation_audit_id, support_id, "DERIVED_FROM"
                )
        for report_id, report_path in (
            (
                "report:venn_abers_quantile_bridge_benchmark",
                Path(
                    "experiments/regression/reports/venn_abers_quantile_bridge_benchmark/benchmark.json"
                ),
            ),
            (
                "report:venn_abers_real_data_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_fairness_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json"
                ),
            ),
        ):
            if report_path.exists():
                add_edge(
                    edges, venn_abers_validation_audit_id, report_id, "SUPPORTS_REPORT"
                )
        for method_id in (
            "venn_abers_quantile",
            "venn_abers_split_fallback",
            "ivapd_regression",
        ):
            add_edge(
                edges,
                venn_abers_validation_audit_id,
                method_node_id(method_id),
                "EVALUATES_METHOD",
            )
        add_edge(
            edges,
            venn_abers_validation_audit_id,
            "method:venn_abers_quantile_grid",
            "USES_REFERENCE",
        )
        add_edge(
            edges,
            venn_abers_validation_audit_id,
            "method_spec:venn_abers_regression",
            "EVIDENCES",
        )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            venn_abers_validation_audit_id,
            "SUPPORTED_BY",
            evidence_path=str(venn_abers_validation_audit_json),
            evidence="$.summary",
        )
    venn_abers_grid_ivapd_protocol_md = venn_abers_grid_ivapd_protocol_json.with_suffix(
        ".md"
    )
    if venn_abers_grid_ivapd_protocol_json.exists():
        venn_abers_grid_ivapd_protocol_id = (
            "report:venn_abers_grid_ivapd_validation_protocol"
        )
        add_node(
            nodes,
            venn_abers_grid_ivapd_protocol_id,
            "report",
            path=(
                str(venn_abers_grid_ivapd_protocol_md)
                if venn_abers_grid_ivapd_protocol_md.exists()
                else None
            ),
            json_path=str(venn_abers_grid_ivapd_protocol_json),
            summary="Audit defining the score-grid and IVAPD evidence required before any validated Venn-Abers regression interval claim.",
        )
        add_edge(
            edges,
            venn_abers_grid_ivapd_protocol_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "report:venn_abers_validation_readiness_audit",
                venn_abers_validation_audit_json,
            ),
            (
                "catalog:manuscript_claim_register",
                Path("experiments/regression/catalogs/manuscript_claim_register.json"),
            ),
            ("report:final_selection_claim_boundary_audit", final_selection_audit_json),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    venn_abers_grid_ivapd_protocol_id,
                    support_id,
                    "DERIVED_FROM",
                )
        for report_id, report_path in (
            (
                "report:venn_abers_real_data_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_fairness_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json"
                ),
            ),
        ):
            if report_path.exists():
                add_edge(
                    edges,
                    venn_abers_grid_ivapd_protocol_id,
                    report_id,
                    "SUPPORTS_REPORT",
                )
        add_edge(
            edges,
            venn_abers_grid_ivapd_protocol_id,
            "method:venn_abers_quantile_grid",
            "USES_REFERENCE",
        )
        add_edge(
            edges,
            venn_abers_grid_ivapd_protocol_id,
            "method:ivapd_regression",
            "EVALUATES_METHOD",
        )
        add_edge(
            edges,
            venn_abers_grid_ivapd_protocol_id,
            "method_spec:venn_abers_regression",
            "EVIDENCES",
        )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            venn_abers_grid_ivapd_protocol_id,
            "SUPPORTED_BY",
            evidence_path=str(venn_abers_grid_ivapd_protocol_json),
            evidence="$.summary",
        )
    venn_abers_grid_expansion_plan_md = venn_abers_grid_expansion_plan_json.with_suffix(
        ".md"
    )
    if venn_abers_grid_expansion_plan_json.exists():
        venn_abers_grid_expansion_plan_id = "report:venn_abers_grid_expansion_plan"
        add_node(
            nodes,
            venn_abers_grid_expansion_plan_id,
            "report",
            path=(
                str(venn_abers_grid_expansion_plan_md)
                if venn_abers_grid_expansion_plan_md.exists()
                else None
            ),
            json_path=str(venn_abers_grid_expansion_plan_json),
            summary="Resumable row-level work queue for expanding Venn-Abers score-grid reference diagnostics toward full-test validation.",
        )
        add_edge(
            edges,
            venn_abers_grid_expansion_plan_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "report:venn_abers_grid_ivapd_validation_protocol",
                venn_abers_grid_ivapd_protocol_json,
            ),
            (
                "report:venn_abers_validation_readiness_audit",
                venn_abers_validation_audit_json,
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    venn_abers_grid_expansion_plan_id,
                    support_id,
                    "DERIVED_FROM",
                )
        for report_id, report_path in (
            (
                "report:venn_abers_real_data_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_fairness_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json"
                ),
            ),
        ):
            if report_path.exists():
                add_edge(
                    edges,
                    venn_abers_grid_expansion_plan_id,
                    report_id,
                    "SUPPORTS_REPORT",
                )
        add_edge(
            edges,
            venn_abers_grid_expansion_plan_id,
            "method:venn_abers_quantile_grid",
            "USES_REFERENCE",
        )
        add_edge(
            edges,
            venn_abers_grid_expansion_plan_id,
            "method_spec:venn_abers_regression",
            "EVIDENCES",
        )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            venn_abers_grid_expansion_plan_id,
            "SUPPORTED_BY",
            evidence_path=str(venn_abers_grid_expansion_plan_json),
            evidence="$.summary",
        )
    venn_abers_grid_failure_modes_md = venn_abers_grid_failure_modes_json.with_suffix(
        ".md"
    )
    if venn_abers_grid_failure_modes_json.exists():
        venn_abers_grid_failure_modes_id = (
            "report:venn_abers_grid_failure_mode_decomposition"
        )
        add_node(
            nodes,
            venn_abers_grid_failure_modes_id,
            "report",
            path=(
                str(venn_abers_grid_failure_modes_md)
                if venn_abers_grid_failure_modes_md.exists()
                else None
            ),
            json_path=str(venn_abers_grid_failure_modes_json),
            summary="Diagnostic decomposition of completed Venn-Abers score-grid blockers into coverage, upper-boundary, and IVAPD no-claim failure modes.",
        )
        add_edge(
            edges,
            venn_abers_grid_failure_modes_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "report:venn_abers_grid_ivapd_validation_protocol",
                venn_abers_grid_ivapd_protocol_json,
            ),
            (
                "report:venn_abers_grid_expansion_plan",
                venn_abers_grid_expansion_plan_json,
            ),
            (
                "report:venn_abers_validation_readiness_audit",
                venn_abers_validation_audit_json,
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    venn_abers_grid_failure_modes_id,
                    support_id,
                    "DERIVED_FROM",
                )
        for report_id, report_path in (
            (
                "report:venn_abers_real_data_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_fairness_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json"
                ),
            ),
        ):
            if report_path.exists():
                add_edge(
                    edges,
                    venn_abers_grid_failure_modes_id,
                    report_id,
                    "SUPPORTS_REPORT",
                )
        add_edge(
            edges,
            venn_abers_grid_failure_modes_id,
            "method:venn_abers_quantile_grid",
            "USES_REFERENCE",
        )
        add_edge(
            edges,
            venn_abers_grid_failure_modes_id,
            "method:ivapd_regression",
            "EVALUATES_METHOD",
        )
        add_edge(
            edges,
            venn_abers_grid_failure_modes_id,
            "method_spec:venn_abers_regression",
            "EVIDENCES",
        )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            venn_abers_grid_failure_modes_id,
            "SUPPORTED_BY",
            evidence_path=str(venn_abers_grid_failure_modes_json),
            evidence="$.summary",
        )
        try:
            failure_modes_payload = json.loads(
                venn_abers_grid_failure_modes_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            failure_modes_payload = {}
        for row in failure_modes_payload.get("dataset_rows", []) or []:
            dataset_id = row.get("dataset_id")
            if dataset_id:
                add_edge(
                    edges,
                    venn_abers_grid_failure_modes_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                    evidence_path=str(venn_abers_grid_failure_modes_json),
                    evidence=dataset_payload_selector(
                        failure_modes_payload,
                        str(dataset_id),
                    ),
                )
    venn_abers_claim_gate_matrix_md = venn_abers_claim_gate_matrix_json.with_suffix(
        ".md"
    )
    if venn_abers_claim_gate_matrix_json.exists():
        venn_abers_claim_gate_matrix_id = "report:venn_abers_claim_gate_matrix"
        add_node(
            nodes,
            venn_abers_claim_gate_matrix_id,
            "report",
            path=(
                str(venn_abers_claim_gate_matrix_md)
                if venn_abers_claim_gate_matrix_md.exists()
                else None
            ),
            json_path=str(venn_abers_claim_gate_matrix_json),
            summary="Joined Venn-Abers positive-claim requirement matrix linking fast-bridge negative evidence, full score-grid diagnostics, IVAPD blockers, and publication guardrails.",
        )
        add_edge(
            edges,
            venn_abers_claim_gate_matrix_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "report:venn_abers_validation_readiness_audit",
                venn_abers_validation_audit_json,
            ),
            (
                "report:venn_abers_grid_ivapd_validation_protocol",
                venn_abers_grid_ivapd_protocol_json,
            ),
            (
                "report:venn_abers_grid_expansion_plan",
                venn_abers_grid_expansion_plan_json,
            ),
            (
                "report:venn_abers_grid_failure_mode_decomposition",
                venn_abers_grid_failure_modes_json,
            ),
            ("report:final_selection_claim_boundary_audit", final_selection_audit_json),
            (
                "report:publication_methodology_audit",
                publication_methodology_audit_json,
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    venn_abers_claim_gate_matrix_id,
                    support_id,
                    "DERIVED_FROM",
                )
        for method_id in (
            "venn_abers_quantile",
            "venn_abers_quantile_grid",
            "venn_abers_split_fallback",
            "ivapd_regression",
        ):
            add_edge(
                edges,
                venn_abers_claim_gate_matrix_id,
                method_node_id(method_id),
                "EVALUATES_METHOD",
            )
        add_edge(
            edges,
            venn_abers_claim_gate_matrix_id,
            "method_spec:venn_abers_regression",
            "EVIDENCES",
        )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            venn_abers_claim_gate_matrix_id,
            "SUPPORTED_BY",
            evidence_path=str(venn_abers_claim_gate_matrix_json),
            evidence="$.summary",
        )
        try:
            claim_gate_payload = json.loads(
                venn_abers_claim_gate_matrix_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            claim_gate_payload = {}
        for row in claim_gate_payload.get("requirements", []) or []:
            if not isinstance(row, dict):
                continue
            for node_id in row.get("evidence_node_ids", []) or []:
                node_type = str(nodes.get(str(node_id), {}).get("type") or "")
                if (
                    isinstance(node_id, str)
                    and node_id in nodes
                    and node_type in {"catalog", "report"}
                ):
                    add_edge(
                        edges,
                        venn_abers_claim_gate_matrix_id,
                        node_id,
                        "DERIVED_FROM",
                        evidence_path=str(venn_abers_claim_gate_matrix_json),
                        evidence=(
                            "$.requirements[?(@.requirement_id == "
                            f"{json.dumps(str(row.get('requirement_id')), sort_keys=True)})]"
                        ),
                    )
    venn_abers_negative_disposition_md = (
        venn_abers_negative_disposition_json.with_suffix(".md")
    )
    if venn_abers_negative_disposition_json.exists():
        venn_abers_negative_disposition_id = (
            "report:venn_abers_negative_evidence_disposition_audit"
        )
        add_node(
            nodes,
            venn_abers_negative_disposition_id,
            "report",
            path=(
                str(venn_abers_negative_disposition_md)
                if venn_abers_negative_disposition_md.exists()
                else None
            ),
            json_path=str(venn_abers_negative_disposition_json),
            summary="Audit proving Venn-Abers negative evidence remains diagnostic and is blocked from final-selection and main-result manuscript surfaces.",
        )
        add_edge(
            edges,
            venn_abers_negative_disposition_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
            evidence_path=str(venn_abers_negative_disposition_json),
            evidence="$.summary.overall_status",
        )
        for support_id, support_path, selector in (
            (
                "catalog:manuscript_claim_register",
                Path("experiments/regression/catalogs/manuscript_claim_register.json"),
                "$.claims[?(@.claim_id == \"venn_abers_fast_bridge_negative_result\")]",
            ),
            (
                "report:venn_abers_validation_readiness_audit",
                venn_abers_validation_audit_json,
                "$.sources.validation_readiness",
            ),
            (
                "report:venn_abers_grid_ivapd_validation_protocol",
                venn_abers_grid_ivapd_protocol_json,
                "$.sources.grid_ivapd_protocol",
            ),
            (
                "report:venn_abers_grid_failure_mode_decomposition",
                venn_abers_grid_failure_modes_json,
                "$.sources.grid_failure_modes",
            ),
            (
                "report:venn_abers_claim_gate_matrix",
                venn_abers_claim_gate_matrix_json,
                "$.sources.claim_gate_matrix",
            ),
            (
                "report:method_selection_candidate_audit",
                method_selection_candidate_json,
                "$.sources.method_selection_candidate",
            ),
            (
                "report:method_performance_synthesis",
                method_performance_json,
                "$.sources.method_performance_synthesis",
            ),
            (
                "catalog:manuscript_bundle_eligibility_matrix",
                Path("experiments/regression/manuscript/bundle_eligibility_matrix.json"),
                "$.sources.bundle_eligibility_matrix",
            ),
            (
                "report:final_selection_claim_boundary_audit",
                final_selection_audit_json,
                "$.sources.final_selection_boundary",
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    venn_abers_negative_disposition_id,
                    support_id,
                    "DERIVED_FROM",
                    evidence_path=str(venn_abers_negative_disposition_json),
                    evidence=selector,
                )
        for method_id in (
            "venn_abers_quantile",
            "venn_abers_split_fallback",
            "ivapd_regression",
        ):
            add_edge(
                edges,
                venn_abers_negative_disposition_id,
                method_node_id(method_id),
                "EVALUATES_METHOD",
                evidence_path=str(venn_abers_negative_disposition_json),
                evidence="$.summary",
            )
        add_edge(
            edges,
            manuscript_claim_node_id("venn_abers_fast_bridge_negative_result"),
            venn_abers_negative_disposition_id,
            "SUPPORTED_BY",
            evidence_path=str(venn_abers_negative_disposition_json),
            evidence="$.checks[?(@.check_id == \"negative_claim_registered\")]",
        )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            venn_abers_negative_disposition_id,
            "SUPPORTED_BY",
            evidence_path=str(venn_abers_negative_disposition_json),
            evidence="$.checks[?(@.check_id == \"final_selection_boundary_blocks_venn_abers\")]",
        )
        try:
            va_disposition_payload = json.loads(
                venn_abers_negative_disposition_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            va_disposition_payload = {}
        for row_index, row in enumerate(
            va_disposition_payload.get("excluded_venn_abers_methods") or []
        ):
            method_id = row.get("cp_method")
            if method_id:
                add_edge(
                    edges,
                    venn_abers_negative_disposition_id,
                    method_node_id(str(method_id)),
                    "EVALUATES_METHOD",
                    evidence_path=str(venn_abers_negative_disposition_json),
                    evidence=f"$.excluded_venn_abers_methods[{row_index}]",
                    disposition="excluded_by_validation_gate",
                )
        for row_index, row in enumerate(
            va_disposition_payload.get("venn_abers_bundle_disposition_rows") or []
        ):
            bundle_id = row.get("bundle_id")
            if bundle_id:
                manifest_id = f"manifest:{bundle_id}:publication_readiness"
                if manifest_id in nodes:
                    add_edge(
                        edges,
                        venn_abers_negative_disposition_id,
                        manifest_id,
                        "DERIVED_FROM",
                        evidence_path=str(venn_abers_negative_disposition_json),
                        evidence=(
                            "$.venn_abers_bundle_disposition_rows"
                            f"[{row_index}]"
                        ),
                        disposition="main_results_blocked",
                    )
    venn_abers_grid_expansion_batch_md = (
        venn_abers_grid_expansion_batch_json.with_suffix(".md")
    )
    if venn_abers_grid_expansion_batch_json.exists():
        venn_abers_grid_expansion_batch_id = "report:venn_abers_grid_expansion_batch"
        add_node(
            nodes,
            venn_abers_grid_expansion_batch_id,
            "report",
            path=(
                str(venn_abers_grid_expansion_batch_md)
                if venn_abers_grid_expansion_batch_md.exists()
                else None
            ),
            json_path=str(venn_abers_grid_expansion_batch_json),
            summary="Append-only worker batch summary for row-level Venn-Abers score-grid expansion progress and resume-state health.",
        )
        add_edge(
            edges,
            venn_abers_grid_expansion_batch_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "report:venn_abers_grid_expansion_plan",
                venn_abers_grid_expansion_plan_json,
            ),
            (
                "report:venn_abers_grid_ivapd_validation_protocol",
                venn_abers_grid_ivapd_protocol_json,
            ),
            (
                "report:venn_abers_validation_readiness_audit",
                venn_abers_validation_audit_json,
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    venn_abers_grid_expansion_batch_id,
                    support_id,
                    "DERIVED_FROM",
                )
        for report_id, report_path in (
            (
                "report:venn_abers_real_data_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_real_data_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_fairness_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_fairness_panel_diagnostic/diagnostic.json"
                ),
            ),
            (
                "report:venn_abers_biomarker_clinical_panel_diagnostic",
                Path(
                    "experiments/regression/reports/venn_abers_biomarker_clinical_panel_diagnostic/diagnostic.json"
                ),
            ),
        ):
            if report_path.exists():
                add_edge(
                    edges,
                    venn_abers_grid_expansion_batch_id,
                    report_id,
                    "SUPPORTS_REPORT",
                )
        add_edge(
            edges,
            venn_abers_grid_expansion_batch_id,
            "method:venn_abers_quantile_grid",
            "USES_REFERENCE",
        )
        add_edge(
            edges,
            venn_abers_grid_expansion_batch_id,
            "method_spec:venn_abers_regression",
            "EVIDENCES",
        )
        add_edge(
            edges,
            "claim_requirement:final_selection_and_fairness_claims_blocked:venn_abers_regression_validation_gate",
            venn_abers_grid_expansion_batch_id,
            "SUPPORTED_BY",
            evidence_path=str(venn_abers_grid_expansion_batch_json),
            evidence="$.summary",
        )
    publication_methodology_audit_md = publication_methodology_audit_json.with_suffix(
        ".md"
    )
    if publication_methodology_audit_json.exists():
        publication_methodology_audit_id = "report:publication_methodology_audit"
        add_node(
            nodes,
            publication_methodology_audit_id,
            "report",
            path=(
                str(publication_methodology_audit_md)
                if publication_methodology_audit_md.exists()
                else None
            ),
            json_path=str(publication_methodology_audit_json),
            summary="Source-derived audit of publication-methodology readiness, workbench evidence boundaries, and blocked final scientific claims.",
        )
        add_edge(
            edges,
            publication_methodology_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            ("report:cross_run_integrity_audit", cross_run_integrity_json),
            ("report:retrospective_methodology_controls", retrospective_controls_json),
            ("report:integrity_remediation_backlog", remediation_backlog_json),
            (
                "report:manuscript_manifest_completeness_audit",
                manuscript_manifest_audit_json,
            ),
            ("report:final_selection_claim_boundary_audit", final_selection_audit_json),
            (
                "report:fairness_population_readiness_audit",
                fairness_population_readiness_json,
            ),
            (
                "report:fairness_group_diagnostic_audit",
                fairness_group_diagnostic_json,
            ),
            (
                "report:venn_abers_validation_readiness_audit",
                venn_abers_validation_audit_json,
            ),
            (
                "report:venn_abers_grid_ivapd_validation_protocol",
                venn_abers_grid_ivapd_protocol_json,
            ),
            (
                "catalog:manuscript_claim_register",
                Path("experiments/regression/catalogs/manuscript_claim_register.json"),
            ),
            (
                "catalog:manuscript_bundle_index",
                Path("experiments/regression/catalogs/manuscript_bundle_index.json"),
            ),
            (
                "catalog:publication_readiness_protocol",
                Path("experiments/regression/PUBLICATION_READINESS_PROTOCOL.md"),
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges, publication_methodology_audit_id, support_id, "DERIVED_FROM"
                )
    method_literature_audit_md = method_literature_audit_json.with_suffix(".md")
    if method_literature_audit_json.exists():
        method_literature_audit_id = "report:method_literature_coverage_audit"
        add_node(
            nodes,
            method_literature_audit_id,
            "report",
            path=(
                str(method_literature_audit_md)
                if method_literature_audit_md.exists()
                else None
            ),
            json_path=str(method_literature_audit_json),
            summary="Audit of regression conformal method-literature coverage, runner integration, diagnostic/reference status, and tracked literature gaps.",
        )
        add_edge(
            edges,
            method_literature_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "catalog:method_registry",
                Path("experiments/regression/catalogs/method_registry.json"),
            ),
            (
                "catalog:regression_literature_notes",
                Path("experiments/regression/catalogs/literature_notes.md"),
            ),
            (
                "catalog:manuscript_method_table",
                Path("experiments/regression/manuscript/method_table.md"),
            ),
            (
                "catalog:publication_readiness_protocol",
                Path("experiments/regression/PUBLICATION_READINESS_PROTOCOL.md"),
            ),
        ):
            if support_path.exists():
                add_edge(edges, method_literature_audit_id, support_id, "DERIVED_FROM")
        spec_node_by_path = {
            "experiments/regression/method_specs/split_and_cqr_regression.md": "method_spec:split_and_cqr_regression",
            "experiments/regression/method_specs/plus_family_regression.md": "method_spec:plus_family_regression",
            "experiments/regression/method_specs/tail_specific_split_regression.md": "method_spec:tail_specific_split_regression",
            "experiments/regression/method_specs/covariate_shift_regression.md": "method_spec:covariate_shift_regression",
            "experiments/regression/method_specs/risk_control_and_boundary_methods.md": "method_spec:risk_control_and_boundary_methods",
            "experiments/regression/method_specs/venn_abers_regression.md": "method_spec:venn_abers_regression",
            "experiments/regression/method_specs/distributional_and_full_conformal_regression.md": "method_spec:distributional_and_full_conformal_regression",
        }
        try:
            method_literature = json.loads(
                method_literature_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            method_literature = {}
        for row in method_literature.get("requirements", []) or []:
            for method_id in row.get("method_ids", []) or []:
                add_edge(
                    edges,
                    method_literature_audit_id,
                    method_node_id(str(method_id)),
                    "EVALUATES_METHOD",
                )
            for spec_row in (row.get("spec_status") or {}).get("rows", []) or []:
                spec_node = spec_node_by_path.get(str(spec_row.get("path")))
                if spec_node:
                    add_edge(
                        edges,
                        method_literature_audit_id,
                        spec_node,
                        "EVIDENCES",
                    )
    duplicate_closure_audit_md = duplicate_closure_audit_json.with_suffix(".md")
    if duplicate_closure_audit_json.exists():
        duplicate_closure_audit_id = "report:duplicate_sensitivity_closure_audit"
        add_node(
            nodes,
            duplicate_closure_audit_id,
            "report",
            path=(
                str(duplicate_closure_audit_md)
                if duplicate_closure_audit_md.exists()
                else None
            ),
            json_path=str(duplicate_closure_audit_json),
            summary="Scoped duplicate-sensitivity closure audit that reconciles duplicate caveats, covered sensitivity evidence, and blocked final scientific claims.",
        )
        add_edge(
            edges,
            duplicate_closure_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            ("report:cross_run_integrity_audit", cross_run_integrity_json),
            ("report:duplicate_split_caveat_backlog", duplicate_backlog_json),
            ("report:paired_duplicate_sensitivity_audit", paired_duplicate_audit_json),
            ("report:integrity_remediation_backlog", remediation_backlog_json),
            ("report:final_selection_claim_boundary_audit", final_selection_audit_json),
            (
                "report:publication_methodology_audit",
                publication_methodology_audit_json,
            ),
            (
                "catalog:manuscript_claim_register",
                Path("experiments/regression/catalogs/manuscript_claim_register.json"),
            ),
            (
                "catalog:manuscript_bundle_index",
                Path("experiments/regression/catalogs/manuscript_bundle_index.json"),
            ),
        ):
            if support_path.exists():
                add_edge(edges, duplicate_closure_audit_id, support_id, "DERIVED_FROM")
        add_edge(
            edges,
            duplicate_closure_audit_id,
            "methodology_control:duplicate_signature_sensitivity_tracking",
            "SUMMARIZES_CONTROL",
        )
        try:
            duplicate_closure = json.loads(
                duplicate_closure_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            duplicate_closure = {}
        duplicate_closure_action_rows = [
            *list(duplicate_closure.get("covered_actions", []) or []),
            *list(duplicate_closure.get("tracked_caveat_actions", []) or []),
        ]
        for row in duplicate_closure_action_rows:
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    duplicate_closure_audit_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    duplicate_closure_audit_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges, duplicate_closure_audit_id, config_id, "SUMMARIZES_CONFIG"
                )
    duplicate_quarantine_audit_md = duplicate_quarantine_audit_json.with_suffix(".md")
    if duplicate_quarantine_audit_json.exists():
        duplicate_quarantine_audit_id = "report:duplicate_content_quarantine_audit"
        add_node(
            nodes,
            duplicate_quarantine_audit_id,
            "report",
            path=(
                str(duplicate_quarantine_audit_md)
                if duplicate_quarantine_audit_md.exists()
                else None
            ),
            json_path=str(duplicate_quarantine_audit_json),
            summary="Audit proving duplicate-sensitive evidence is quarantined from final manuscript claims or remains outside manuscript candidate surfaces.",
        )
        add_edge(
            edges,
            duplicate_quarantine_audit_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            (
                "report:duplicate_sensitivity_closure_audit",
                duplicate_closure_audit_json,
            ),
            (
                "catalog:manuscript_bundle_eligibility_matrix",
                Path("experiments/regression/manuscript/bundle_eligibility_matrix.json"),
            ),
            (
                "report:final_selection_claim_boundary_audit",
                final_selection_audit_json,
            ),
            (
                "catalog:manuscript_claim_register",
                Path("experiments/regression/catalogs/manuscript_claim_register.json"),
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    duplicate_quarantine_audit_id,
                    support_id,
                    "DERIVED_FROM",
                )
        add_edge(
            edges,
            duplicate_quarantine_audit_id,
            "methodology_control:duplicate_signature_sensitivity_tracking",
            "SUMMARIZES_CONTROL",
        )
        try:
            duplicate_quarantine = json.loads(
                duplicate_quarantine_audit_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            duplicate_quarantine = {}
        for row_index, row in enumerate(duplicate_quarantine.get("rows") or []):
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    duplicate_quarantine_audit_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                    evidence_path=str(duplicate_quarantine_audit_json),
                    evidence=row_selector("rows", row_index, "report_id"),
                )
    retrospective_quality_gate_md = retrospective_quality_gate_json.with_suffix(".md")
    if retrospective_quality_gate_json.exists():
        retrospective_quality_gate_id = "report:retrospective_quality_gate"
        add_node(
            nodes,
            retrospective_quality_gate_id,
            "report",
            path=(
                str(retrospective_quality_gate_md)
                if retrospective_quality_gate_md.exists()
                else None
            ),
            json_path=str(retrospective_quality_gate_json),
            summary="Retrospective quality gate combining cross-run integrity, methodology controls, remediation backlog, and KG quality status.",
        )
        add_edge(
            edges,
            retrospective_quality_gate_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            ("report:cross_run_integrity_audit", cross_run_integrity_json),
            ("report:retrospective_methodology_controls", retrospective_controls_json),
            ("report:integrity_remediation_backlog", remediation_backlog_json),
            ("report:method_literature_coverage_audit", method_literature_audit_json),
            (
                "report:duplicate_sensitivity_closure_audit",
                duplicate_closure_audit_json,
            ),
            (
                "report:duplicate_content_quarantine_audit",
                duplicate_quarantine_audit_json,
            ),
            (
                "report:manuscript_manifest_completeness_audit",
                manuscript_manifest_audit_json,
            ),
            (
                "report:dataset_specific_final_gate_audit",
                dataset_specific_final_gate_audit_json,
            ),
            (
                "report:dataset_final_gate_remediation_plan",
                dataset_final_gate_remediation_plan_json,
            ),
            (
                "report:dataset_final_gate_post_selection_validation_bridge",
                dataset_final_gate_post_selection_bridge_json,
            ),
            (
                "report:dataset_final_gate_post_selection_validation_bridge_results",
                dataset_final_gate_post_selection_bridge_results_json,
            ),
            (
                "report:selection_multiplicity_protocol",
                selection_multiplicity_protocol_json,
            ),
            (
                "report:selection_multiplicity_evidence_record",
                selection_multiplicity_evidence_record_json,
            ),
            ("report:bounded_support_protocol", bounded_support_protocol_json),
            ("report:target_domain_provenance", target_domain_provenance_json),
            (
                "report:bounded_support_posthandling_validation",
                bounded_support_posthandling_json,
            ),
            (
                "report:bounded_support_dataset_audit",
                bounded_support_dataset_audit_json,
            ),
            (
                "report:bounded_support_endpoint_closure_audit",
                bounded_support_endpoint_closure_json,
            ),
            (
                "report:bounded_support_positive_validation_protocol",
                bounded_support_positive_validation_json,
            ),
            ("report:experiment_accounting_audit", experiment_accounting_json),
            ("report:method_performance_synthesis", method_performance_json),
            (
                "report:method_selection_candidate_audit",
                method_selection_candidate_json,
            ),
            (
                "report:method_selection_robustness_audit",
                method_selection_robustness_json,
            ),
            (
                "report:method_selection_alpha_expansion_plan",
                method_selection_alpha_expansion_json,
            ),
            (
                "report:method_selection_alpha_expansion_execution_audit",
                method_selection_alpha_expansion_execution_json,
            ),
            (
                "report:method_selection_inferential_audit",
                method_selection_inferential_json,
            ),
            (
                "report:method_selection_post_selection_validation_batch",
                method_selection_post_validation_batch_json,
            ),
            (
                "report:method_selection_post_selection_validation_results",
                method_selection_post_validation_results_json,
            ),
            (
                "report:main_result_candidate_bundle_plan",
                main_result_candidate_bundle_plan_json,
            ),
            (
                "report:main_result_candidate_bundle_results",
                main_result_candidate_bundle_results_json,
            ),
            (
                "report:main_result_candidate_post_run_closure_audit",
                main_result_candidate_post_run_closure_json,
            ),
            ("report:manuscript_readiness_map", manuscript_readiness_map_json),
            ("report:graph_artifact_readiness_audit", graph_artifact_audit_json),
            ("report:final_selection_claim_boundary_audit", final_selection_audit_json),
            (
                "report:fairness_population_readiness_audit",
                fairness_population_readiness_json,
            ),
            (
                "report:fairness_group_diagnostic_audit",
                fairness_group_diagnostic_json,
            ),
            (
                "report:venn_abers_validation_readiness_audit",
                venn_abers_validation_audit_json,
            ),
            (
                "report:venn_abers_grid_ivapd_validation_protocol",
                venn_abers_grid_ivapd_protocol_json,
            ),
            (
                "report:venn_abers_grid_expansion_plan",
                venn_abers_grid_expansion_plan_json,
            ),
            (
                "report:venn_abers_grid_failure_mode_decomposition",
                venn_abers_grid_failure_modes_json,
            ),
            (
                "report:venn_abers_claim_gate_matrix",
                venn_abers_claim_gate_matrix_json,
            ),
            (
                "report:venn_abers_negative_evidence_disposition_audit",
                venn_abers_negative_disposition_json,
            ),
            (
                "report:venn_abers_grid_expansion_batch",
                venn_abers_grid_expansion_batch_json,
            ),
            (
                "report:publication_methodology_audit",
                publication_methodology_audit_json,
            ),
            ("report:knowledge_graph_quality_summary", knowledge_graph_quality_json),
            ("report:kg_publication_quality_audit", kg_publication_quality_json),
            (
                "report:scientific_review_finding_register",
                scientific_review_register_json,
            ),
            (
                "report:post_experiment_publication_activation_audit",
                post_experiment_publication_activation_json,
            ),
            (
                "report:neutral_reporting_language_audit",
                neutral_reporting_language_json,
            ),
            (
                "report:individual_experiment_report_blueprint",
                individual_experiment_report_blueprint_json,
            ),
            (
                "report:claim_safe_result_extraction_matrix",
                claim_safe_result_extraction_matrix_json,
            ),
            (
                "report:manuscript_section_evidence_packet",
                manuscript_section_evidence_packet_json,
            ),
            (
                "report:section_claim_boundary_audit",
                section_claim_boundary_audit_json,
            ),
            (
                "report:article_supplement_kg_navigation_index",
                article_supplement_kg_navigation_index_json,
            ),
            (
                "report:publication_phase_progress_reconciliation_audit",
                publication_phase_progress_reconciliation_json,
            ),
            (
                "report:neutral_experiment_closure_audit",
                neutral_experiment_closure_json,
            ),
            (
                "report:scientific_neutrality_interpretation_lock",
                scientific_neutrality_interpretation_lock_json,
            ),
            (
                "report:final_publication_output_authorization_protocol",
                final_publication_output_authorization_protocol_json,
            ),
            (
                "report:publication_claim_evidence_verification_matrix",
                publication_claim_evidence_verification_matrix_json,
            ),
            (
                "report:sterile_repository_staging_manifest",
                sterile_repository_staging_manifest_json,
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    retrospective_quality_gate_id,
                    support_id,
                    "DERIVED_FROM",
                )

    if knowledge_graph_quality_json.exists():
        knowledge_graph_quality_id = "report:knowledge_graph_quality_summary"
        add_node(
            nodes,
            knowledge_graph_quality_id,
            "report",
            json_path=str(knowledge_graph_quality_json),
            summary="Knowledge graph quality summary covering topology, ontology, provenance, confidence, freshness, and linkage metrics.",
        )
        add_edge(
            edges,
            knowledge_graph_quality_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        add_edge(
            edges,
            knowledge_graph_quality_id,
            "catalog:knowledge_graph",
            "DERIVED_FROM",
        )

    kg_publication_quality_md = kg_publication_quality_json.with_suffix(".md")
    if kg_publication_quality_json.exists():
        kg_publication_quality_id = "report:kg_publication_quality_audit"
        add_node(
            nodes,
            kg_publication_quality_id,
            "report",
            path=(
                str(kg_publication_quality_md)
                if kg_publication_quality_md.exists()
                else None
            ),
            json_path=str(kg_publication_quality_json),
            summary="Publication-facing audit of knowledge graph traceability, ontology, provenance, freshness, endpoint state coverage, and claim boundaries.",
        )
        add_edge(
            edges,
            kg_publication_quality_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        add_edge(
            edges,
            kg_publication_quality_id,
            "catalog:knowledge_graph",
            "DERIVED_FROM",
        )
        if knowledge_graph_quality_json.exists():
            add_edge(
                edges,
                kg_publication_quality_id,
                "report:knowledge_graph_quality_summary",
                "DERIVED_FROM",
            )

    scientific_review_register_md = scientific_review_register_json.with_suffix(".md")
    if scientific_review_register_json.exists():
        scientific_review_register_id = "report:scientific_review_finding_register"
        add_node(
            nodes,
            scientific_review_register_id,
            "report",
            path=(
                str(scientific_review_register_md)
                if scientific_review_register_md.exists()
                else None
            ),
            json_path=str(scientific_review_register_json),
            summary="Executable register of external KG and methodology review findings, closure status, tracked caveats, evidence paths, and claim boundaries.",
        )
        add_edge(
            edges,
            scientific_review_register_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        for support_id, support_path in (
            ("report:knowledge_graph_quality_summary", knowledge_graph_quality_json),
            ("report:kg_publication_quality_audit", kg_publication_quality_json),
            (
                "report:publication_methodology_audit",
                publication_methodology_audit_json,
            ),
            (
                "report:neutral_reporting_language_audit",
                neutral_reporting_language_json,
            ),
            ("report:final_selection_claim_boundary_audit", final_selection_audit_json),
            (
                "report:duplicate_sensitivity_closure_audit",
                duplicate_closure_audit_json,
            ),
            (
                "report:duplicate_content_quarantine_audit",
                duplicate_quarantine_audit_json,
            ),
            (
                "report:venn_abers_negative_evidence_disposition_audit",
                venn_abers_negative_disposition_json,
            ),
            ("report:bounded_support_protocol", bounded_support_protocol_json),
            (
                "report:bounded_support_posthandling_validation",
                bounded_support_posthandling_json,
            ),
            (
                "report:bounded_support_dataset_audit",
                bounded_support_dataset_audit_json,
            ),
            (
                "report:bounded_support_endpoint_closure_audit",
                bounded_support_endpoint_closure_json,
            ),
            (
                "report:bounded_support_positive_validation_protocol",
                bounded_support_positive_validation_json,
            ),
        ):
            if support_path.exists():
                add_edge(
                    edges,
                    scientific_review_register_id,
                    support_id,
                    "DERIVED_FROM",
                )

    remediation_backlog_md = remediation_backlog_json.with_suffix(".md")
    if remediation_backlog_json.exists():
        remediation_backlog_id = "report:integrity_remediation_backlog"
        add_node(
            nodes,
            remediation_backlog_id,
            "report",
            path=(
                str(remediation_backlog_md) if remediation_backlog_md.exists() else None
            ),
            json_path=str(remediation_backlog_json),
            summary="Actionable remediation backlog generated from cross-run integrity caveats and blocking issues.",
        )
        add_edge(
            edges, remediation_backlog_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        if cross_run_integrity_json.exists():
            add_edge(
                edges,
                remediation_backlog_id,
                "report:cross_run_integrity_audit",
                "SUPPORTS_REPORT",
            )
        try:
            remediation_backlog = json.loads(
                remediation_backlog_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            remediation_backlog = {}
        for row in remediation_backlog.get("rows", []) or []:
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    remediation_backlog_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    remediation_backlog_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(edges, remediation_backlog_id, config_id, "SUMMARIZES_CONFIG")

    legacy_claim_backfill_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "legacy_claim_guard_backfill.json"
    )
    legacy_claim_backfill_md = legacy_claim_backfill_json.with_suffix(".md")
    if legacy_claim_backfill_json.exists():
        legacy_claim_backfill_id = "report:legacy_claim_guard_backfill"
        add_node(
            nodes,
            legacy_claim_backfill_id,
            "report",
            path=(
                str(legacy_claim_backfill_md)
                if legacy_claim_backfill_md.exists()
                else None
            ),
            json_path=str(legacy_claim_backfill_json),
            summary="Backfill report for legacy CQR fixed-backend and Venn-Abers diagnostic-only claim guards.",
        )
        add_edge(
            edges, legacy_claim_backfill_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        if remediation_backlog_json.exists():
            add_edge(
                edges,
                legacy_claim_backfill_id,
                "report:integrity_remediation_backlog",
                "SUPPORTS_REPORT",
            )
        try:
            legacy_claim_backfill = json.loads(
                legacy_claim_backfill_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            legacy_claim_backfill = {}
        for row in legacy_claim_backfill.get("rows", []) or []:
            if not row.get("backfilled_guards"):
                continue
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges, legacy_claim_backfill_id, config_id, "SUMMARIZES_CONFIG"
                )
                report_dir = (
                    Path("experiments/regression/reports") / Path(str(config_path)).stem
                )
                if report_dir.exists():
                    add_edge(
                        edges,
                        legacy_claim_backfill_id,
                        f"report:{report_dir.name}",
                        "SUPPORTS_REPORT",
                    )

    feature_backfill_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "feature_leakage_sidecar_backfill.json"
    )
    feature_backfill_md = feature_backfill_json.with_suffix(".md")
    if feature_backfill_json.exists():
        feature_backfill_id = "report:feature_leakage_sidecar_backfill"
        add_node(
            nodes,
            feature_backfill_id,
            "report",
            path=str(feature_backfill_md) if feature_backfill_md.exists() else None,
            json_path=str(feature_backfill_json),
            summary="Backfill report for prediction-metadata feature-leakage sidecars generated from the integrity remediation backlog.",
        )
        add_edge(edges, feature_backfill_id, methodology_report_id, "SUPPORTS_REPORT")
        if remediation_backlog_json.exists():
            add_edge(
                edges,
                feature_backfill_id,
                "report:integrity_remediation_backlog",
                "SUPPORTS_REPORT",
            )
        try:
            feature_backfill = json.loads(
                feature_backfill_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            feature_backfill = {}
        for row in feature_backfill.get("rows", []) or []:
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    feature_backfill_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                )
                add_edge(
                    edges,
                    feature_backfill_id,
                    f"{report_id}:feature_leakage_audit",
                    "SUPPORTS_REPORT",
                )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    feature_backfill_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(edges, feature_backfill_id, config_id, "SUMMARIZES_CONFIG")

    feature_provenance_backfill_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "feature_leakage_provenance_label_backfill.json"
    )
    feature_provenance_backfill_md = feature_provenance_backfill_json.with_suffix(".md")
    if feature_provenance_backfill_json.exists():
        feature_provenance_backfill_id = (
            "report:feature_leakage_provenance_label_backfill"
        )
        add_node(
            nodes,
            feature_provenance_backfill_id,
            "report",
            path=(
                str(feature_provenance_backfill_md)
                if feature_provenance_backfill_md.exists()
                else None
            ),
            json_path=str(feature_provenance_backfill_json),
            summary="Label-only backfill report for legacy feature-leakage sidecar provenance labels.",
        )
        add_edge(
            edges,
            feature_provenance_backfill_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        if cross_run_integrity_json.exists():
            add_edge(
                edges,
                feature_provenance_backfill_id,
                "report:cross_run_integrity_audit",
                "SUPPORTS_REPORT",
            )
        if feature_backfill_json.exists():
            add_edge(
                edges,
                feature_provenance_backfill_id,
                "report:feature_leakage_sidecar_backfill",
                "SUPPORTS_REPORT",
            )
        try:
            feature_provenance_backfill = json.loads(
                feature_provenance_backfill_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            feature_provenance_backfill = {}
        for row in feature_provenance_backfill.get("rows", []) or []:
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    feature_provenance_backfill_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                )
                add_edge(
                    edges,
                    feature_provenance_backfill_id,
                    f"{report_id}:feature_leakage_audit",
                    "SUPPORTS_REPORT",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges,
                    feature_provenance_backfill_id,
                    config_id,
                    "SUMMARIZES_CONFIG",
                )

    feature_metadata_triage_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "feature_leakage_metadata_completeness_triage.json"
    )
    feature_metadata_triage_md = feature_metadata_triage_json.with_suffix(".md")
    if feature_metadata_triage_json.exists():
        feature_metadata_triage_id = (
            "report:feature_leakage_metadata_completeness_triage"
        )
        add_node(
            nodes,
            feature_metadata_triage_id,
            "report",
            path=(
                str(feature_metadata_triage_md)
                if feature_metadata_triage_md.exists()
                else None
            ),
            json_path=str(feature_metadata_triage_json),
            summary="Triage report for legacy feature-leakage metadata completeness caveats and claim boundaries.",
        )
        add_edge(
            edges, feature_metadata_triage_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        if cross_run_integrity_json.exists():
            add_edge(
                edges,
                feature_metadata_triage_id,
                "report:cross_run_integrity_audit",
                "SUPPORTS_REPORT",
            )
        if remediation_backlog_json.exists():
            add_edge(
                edges,
                feature_metadata_triage_id,
                "report:integrity_remediation_backlog",
                "SUPPORTS_REPORT",
            )
        if feature_backfill_json.exists():
            add_edge(
                edges,
                feature_metadata_triage_id,
                "report:feature_leakage_sidecar_backfill",
                "SUPPORTS_REPORT",
            )
        if feature_provenance_backfill_json.exists():
            add_edge(
                edges,
                feature_metadata_triage_id,
                "report:feature_leakage_provenance_label_backfill",
                "SUPPORTS_REPORT",
            )
        feature_prediction_metadata_repair_json = Path(
            "experiments/regression/reports/methodology_sanity_audit_20260627/"
            "feature_leakage_prediction_metadata_repair.json"
        )
        if feature_prediction_metadata_repair_json.exists():
            add_edge(
                edges,
                feature_metadata_triage_id,
                "report:feature_leakage_prediction_metadata_repair",
                "SUPPORTS_REPORT",
            )
        try:
            feature_metadata_triage = json.loads(
                feature_metadata_triage_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            feature_metadata_triage = {}
        for row in feature_metadata_triage.get("rows", []) or []:
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    feature_metadata_triage_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                )
                add_edge(
                    edges,
                    feature_metadata_triage_id,
                    f"{report_id}:feature_leakage_audit",
                    "SUPPORTS_REPORT",
                )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    feature_metadata_triage_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges, feature_metadata_triage_id, config_id, "SUMMARIZES_CONFIG"
                )

    feature_prediction_metadata_repair_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "feature_leakage_prediction_metadata_repair.json"
    )
    feature_prediction_metadata_repair_md = (
        feature_prediction_metadata_repair_json.with_suffix(".md")
    )
    if feature_prediction_metadata_repair_json.exists():
        feature_prediction_metadata_repair_id = (
            "report:feature_leakage_prediction_metadata_repair"
        )
        add_node(
            nodes,
            feature_prediction_metadata_repair_id,
            "report",
            path=(
                str(feature_prediction_metadata_repair_md)
                if feature_prediction_metadata_repair_md.exists()
                else None
            ),
            json_path=str(feature_prediction_metadata_repair_json),
            summary="Metadata-only repair report for legacy prediction bundles used by feature-leakage audits.",
        )
        add_edge(
            edges,
            feature_prediction_metadata_repair_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        if cross_run_integrity_json.exists():
            add_edge(
                edges,
                feature_prediction_metadata_repair_id,
                "report:cross_run_integrity_audit",
                "SUPPORTS_REPORT",
            )
        if feature_metadata_triage_json.exists():
            add_edge(
                edges,
                feature_prediction_metadata_repair_id,
                "report:feature_leakage_metadata_completeness_triage",
                "SUPPORTS_REPORT",
            )
        try:
            feature_prediction_metadata_repair = json.loads(
                feature_prediction_metadata_repair_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            feature_prediction_metadata_repair = {}
        for row in feature_prediction_metadata_repair.get("rows", []) or []:
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    feature_prediction_metadata_repair_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                )
                add_edge(
                    edges,
                    feature_prediction_metadata_repair_id,
                    f"{report_id}:feature_leakage_audit",
                    "SUPPORTS_REPORT",
                )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    feature_prediction_metadata_repair_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges,
                    feature_prediction_metadata_repair_id,
                    config_id,
                    "SUMMARIZES_CONFIG",
                )

    endpoint_method_backfill_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "endpoint_method_coverage_backfill.json"
    )
    endpoint_method_backfill_md = endpoint_method_backfill_json.with_suffix(".md")
    if endpoint_method_backfill_json.exists():
        endpoint_method_backfill_id = "report:endpoint_method_coverage_backfill"
        add_node(
            nodes,
            endpoint_method_backfill_id,
            "report",
            path=(
                str(endpoint_method_backfill_md)
                if endpoint_method_backfill_md.exists()
                else None
            ),
            json_path=str(endpoint_method_backfill_json),
            summary="Backfill report for endpoint audit v2 full-method coverage metadata verified against canonical ledgers.",
        )
        add_edge(
            edges, endpoint_method_backfill_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        if cross_run_integrity_json.exists():
            add_edge(
                edges,
                endpoint_method_backfill_id,
                "report:cross_run_integrity_audit",
                "SUPPORTS_REPORT",
            )
        if remediation_backlog_json.exists():
            add_edge(
                edges,
                endpoint_method_backfill_id,
                "report:integrity_remediation_backlog",
                "SUPPORTS_REPORT",
            )
        try:
            endpoint_method_backfill = json.loads(
                endpoint_method_backfill_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            endpoint_method_backfill = {}
        for row in endpoint_method_backfill.get("rows", []) or []:
            report_id = row.get("report_id")
            if report_id:
                add_edge(
                    edges,
                    endpoint_method_backfill_id,
                    str(report_id),
                    "SUPPORTS_REPORT",
                )
                add_edge(
                    edges,
                    endpoint_method_backfill_id,
                    f"{report_id}:endpoint_audit",
                    "SUPPORTS_REPORT",
                )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    endpoint_method_backfill_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges, endpoint_method_backfill_id, config_id, "SUMMARIZES_CONFIG"
                )

    endpoint_schema_feasibility_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "endpoint_schema_backfill_feasibility.json"
    )
    endpoint_schema_feasibility_md = endpoint_schema_feasibility_json.with_suffix(".md")
    if endpoint_schema_feasibility_json.exists():
        endpoint_schema_feasibility_id = "report:endpoint_schema_backfill_feasibility"
        add_node(
            nodes,
            endpoint_schema_feasibility_id,
            "report",
            path=(
                str(endpoint_schema_feasibility_md)
                if endpoint_schema_feasibility_md.exists()
                else None
            ),
            json_path=str(endpoint_schema_feasibility_json),
            summary="Feasibility audit for regenerating legacy endpoint sidecars with the canonical v2 endpoint audit script.",
        )
        add_edge(
            edges,
            endpoint_schema_feasibility_id,
            methodology_report_id,
            "SUPPORTS_REPORT",
        )
        if remediation_backlog_json.exists():
            add_edge(
                edges,
                endpoint_schema_feasibility_id,
                "report:integrity_remediation_backlog",
                "SUPPORTS_REPORT",
            )
        if cross_run_integrity_json.exists():
            add_edge(
                edges,
                endpoint_schema_feasibility_id,
                "report:cross_run_integrity_audit",
                "SUPPORTS_REPORT",
            )
        try:
            endpoint_schema_feasibility = json.loads(
                endpoint_schema_feasibility_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            endpoint_schema_feasibility = {}
        for row in endpoint_schema_feasibility.get("rows", []) or []:
            report_name = row.get("report_name")
            if report_name:
                report_id = f"report:{report_name}"
                add_edge(
                    edges,
                    endpoint_schema_feasibility_id,
                    report_id,
                    "SUPPORTS_REPORT",
                )
                add_edge(
                    edges,
                    endpoint_schema_feasibility_id,
                    f"{report_id}:endpoint_audit",
                    "SUPPORTS_REPORT",
                )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    endpoint_schema_feasibility_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges,
                    endpoint_schema_feasibility_id,
                    config_id,
                    "SUMMARIZES_CONFIG",
                )

    split_profile_backfill_json = Path(
        "experiments/regression/reports/methodology_sanity_audit_20260627/"
        "split_profile_schema_backfill.json"
    )
    split_profile_backfill_md = split_profile_backfill_json.with_suffix(".md")
    if split_profile_backfill_json.exists():
        split_profile_backfill_id = "report:split_profile_schema_backfill"
        add_node(
            nodes,
            split_profile_backfill_id,
            "report",
            path=(
                str(split_profile_backfill_md)
                if split_profile_backfill_md.exists()
                else None
            ),
            json_path=str(split_profile_backfill_json),
            summary="Backfill report for legacy split-profile sidecars regenerated with schema v2 integrity checks.",
        )
        add_edge(
            edges, split_profile_backfill_id, methodology_report_id, "SUPPORTS_REPORT"
        )
        if remediation_backlog_json.exists():
            add_edge(
                edges,
                split_profile_backfill_id,
                "report:integrity_remediation_backlog",
                "SUPPORTS_REPORT",
            )
        if cross_run_integrity_json.exists():
            add_edge(
                edges,
                split_profile_backfill_id,
                "report:cross_run_integrity_audit",
                "SUPPORTS_REPORT",
            )
        try:
            split_profile_backfill = json.loads(
                split_profile_backfill_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            split_profile_backfill = {}
        for row in split_profile_backfill.get("rows", []) or []:
            report_name = row.get("report_name")
            if report_name:
                report_id = f"report:{report_name}"
                add_edge(
                    edges,
                    split_profile_backfill_id,
                    report_id,
                    "SUPPORTS_REPORT",
                )
                add_edge(
                    edges,
                    split_profile_backfill_id,
                    f"{report_id}:split_profile",
                    "SUPPORTS_REPORT",
                )
            for dataset_id in row.get("dataset_ids", []) or []:
                add_edge(
                    edges,
                    split_profile_backfill_id,
                    f"dataset:{dataset_id}",
                    "SUMMARIZES_DATASET",
                )
            config_path = row.get("config_path")
            if config_path and Path(str(config_path)).exists():
                config = yaml.safe_load(
                    Path(str(config_path)).read_text(encoding="utf-8")
                )
                config_id = (
                    f"config:{config.get('experiment_id', Path(str(config_path)).stem)}"
                )
                add_edge(
                    edges, split_profile_backfill_id, config_id, "SUMMARIZES_CONFIG"
                )

    datasets = read_jsonl(Path(args.dataset_candidates))
    for dataset in datasets:
        dataset_id = f"dataset:{dataset['dataset_id']}"
        add_node(nodes, dataset_id, "dataset", **dataset)
        source_id = f"source:{dataset['source']}"
        add_node(
            nodes,
            source_id,
            "source",
            name=dataset["source"],
            url=dataset.get("source_url"),
        )
        add_edge(edges, dataset_id, source_id, "FROM_SOURCE")
        add_edge(edges, dataset_id, "catalog:dataset_candidates", "RECORDED_IN")
        add_edge(edges, dataset_id, "policy:data_policy_registry", "GOVERNED_BY")
        status = dataset.get("status")
        if should_emit_dataset_catalog_decision(status):
            decision_id = dataset_catalog_decision_id(
                dataset["dataset_id"], str(status)
            )
            add_node(
                nodes,
                decision_id,
                "decision",
                dataset_id=dataset["dataset_id"],
                decision=status,
                source="dataset_candidates",
                reason=dataset.get("notes"),
                next_action=(
                    "manual audit before runner queue"
                    if status == "queued_manual_audit"
                    else "keep out of runner queue unless the catalog policy changes"
                ),
                summary=(
                    f"Dataset catalog decision for {dataset['dataset_id']}: {status}. "
                    "This records a queue/audit status, not executed experiment evidence."
                ),
            )
            add_edge(edges, decision_id, dataset_id, "DECIDES_DATASET")
            add_edge(edges, decision_id, "catalog:dataset_candidates", "RECORDED_IN")
        if dataset.get("mirrors_dataset_id"):
            add_edge(
                edges,
                dataset_id,
                f"dataset:{dataset['mirrors_dataset_id']}",
                "MIRRORS_DATASET",
            )
        if dataset.get("variant_of_dataset_id"):
            add_edge(
                edges,
                dataset_id,
                f"dataset:{dataset['variant_of_dataset_id']}",
                "VARIANT_OF_DATASET",
            )
        if dataset.get("family_id"):
            family_id = f"family:{dataset['family_id']}"
            add_node(nodes, family_id, "dataset_family", name=dataset["family_id"])
            add_edge(edges, dataset_id, family_id, "BELONGS_TO_FAMILY")

    audit_index = json.loads(Path(args.audit_index).read_text(encoding="utf-8"))
    for audit in audit_index.get("audits", []):
        audit_id = f"audit:{audit['dataset_id']}"
        add_node(nodes, audit_id, "audit", **audit)
        dataset_id = f"dataset:{audit['dataset_id']}"
        audit_source = audit.get("source")
        audit_source_url = audit.get("source_url")
        if dataset_id not in nodes:
            source = audit_source
            source_url = audit_source_url
            if audit["dataset_id"].startswith("uci_student_performance_"):
                source = "UCI Machine Learning Repository"
                source_url = (
                    "https://archive.ics.uci.edu/dataset/320/student+performance"
                )
            add_node(
                nodes,
                dataset_id,
                "dataset",
                dataset_id=audit["dataset_id"],
                name=audit["dataset_id"],
                source=source,
                source_url=source_url,
                status=audit.get("status"),
                notes=audit.get("notes"),
                summary=(
                    f"Audit-index dataset variant {audit['dataset_id']} "
                    "referenced by policy-gated regression experiments."
                ),
            )
            add_edge(edges, dataset_id, "catalog:audit_index", "RECORDED_IN")
            add_edge(edges, dataset_id, "policy:data_policy_registry", "GOVERNED_BY")
            if audit["dataset_id"].startswith("uci_student_performance_"):
                add_edge(
                    edges,
                    dataset_id,
                    "dataset:uci_student_performance",
                    "VARIANT_OF_DATASET",
                )
                add_edge(
                    edges,
                    dataset_id,
                    "source:UCI Machine Learning Repository",
                    "FROM_SOURCE",
                )
        if audit_source:
            source_id = f"source:{audit_source}"
            add_node(
                nodes,
                source_id,
                "source",
                name=audit_source,
                url=audit_source_url,
            )
            add_edge(edges, dataset_id, source_id, "FROM_SOURCE")
        add_edge(edges, dataset_id, audit_id, "HAS_AUDIT")
        audit_path = Path(audit["audit_path"])
        profile_path = audit_path.with_name("profile.md")
        profile_json_path = audit_path.with_name("profile.json")
        if profile_path.exists():
            profile_id = f"profile:{audit['dataset_id']}"
            add_node(
                nodes,
                profile_id,
                "dataset_profile",
                path=str(profile_path),
                json_path=(
                    str(profile_json_path) if profile_json_path.exists() else None
                ),
            )
            add_edge(edges, audit_id, profile_id, "HAS_PROFILE")

    for review in read_jsonl(Path(args.openml_review_decisions)):
        review_id = f"openml_review:{review['openml_id']}"
        add_node(nodes, review_id, "openml_review_decision", **review)
        add_edge(edges, review_id, "catalog:openml_review_decisions", "RECORDED_IN")
        if review.get("dataset_id"):
            add_edge(
                edges, review_id, f"dataset:{review['dataset_id']}", "DECIDES_DATASET"
            )
        elif review.get("source_url"):
            source_id = f"source:openml_review:{review['openml_id']}"
            add_node(
                nodes,
                source_id,
                "source",
                name=f"OpenML {review['openml_id']} reviewed source",
                url=review.get("source_url"),
                summary=(
                    f"Reviewed OpenML source {review['openml_id']} excluded from "
                    "ordinary regression dataset execution."
                ),
            )
            add_edge(edges, review_id, source_id, "REVIEWS_SOURCE")

    method_registry = json.loads(Path(args.method_registry).read_text(encoding="utf-8"))
    for method in method_registry.get("regression_methods", []):
        method_id = f"method:{method['method_id']}"
        add_node(nodes, method_id, "method", **method)
        add_edge(edges, method_id, "catalog:method_registry", "REGISTERED_IN")

    method_configs_by_label: dict[str, list[tuple[str, str]]] = {}
    config_ids_by_report_name: dict[str, str] = {}
    for config_path in iter_config_paths(args.config_glob):
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config_id = f"config:{config.get('experiment_id', config_path.stem)}"
        config_ids_by_report_name[config_path.stem] = config_id
        add_node(
            nodes,
            config_id,
            "config",
            path=str(config_path),
            experiment_id=config.get("experiment_id"),
            purpose=config.get("purpose"),
            target_transform=config.get("target_transform", "identity"),
            dataset_target_transforms=config.get("dataset_target_transforms", {}),
        )
        config_datasets = config.get("datasets", [])
        if isinstance(config_datasets, list):
            for dataset_id in config_datasets:
                add_edge(
                    edges,
                    config_id,
                    f"dataset:{dataset_id}",
                    "QUEUES_DATASET",
                    evidence_path=str(config_path),
                    evidence=yaml_selector("datasets", dataset_id),
                )
        for model in config.get("models", []):
            model_id = str(model.get("model_id"))
            family = model.get("family")
            add_node(
                nodes,
                f"model:{model_id}",
                "model",
                name=model_id,
                family=family,
            )
            model_edge_attrs = {
                "evidence_path": str(config_path),
                "evidence": yaml_selector("models", model_id, key="model_id"),
            }
            add_edge(
                edges,
                config_id,
                f"model:{model_id}",
                "QUEUES_MODEL",
                **model_edge_attrs,
            )
            add_edge(
                edges, f"model:{model_id}", "catalog:method_registry", "REGISTERED_IN"
            )
        for method in config.get("cp_methods", []):
            method_label = str(method)
            method_id, method_params = cp_method_settings(config, method_label)
            method_edge_attrs = {
                "evidence_path": str(config_path),
                "evidence": yaml_selector("cp_methods", method_label),
            }
            add_edge(
                edges,
                config_id,
                method_node_id(method_id),
                "QUEUES_METHOD",
                **method_edge_attrs,
            )
            if method_id != method_label or method_params:
                variant_id = f"method_config:{config.get('experiment_id', config_path.stem)}:{method_label}"
                add_node(
                    nodes,
                    variant_id,
                    "method_config",
                    label=method_label,
                    method_id=method_id,
                    params=method_params,
                    path=str(config_path),
                )
                add_edge(
                    edges,
                    config_id,
                    variant_id,
                    "QUEUES_METHOD_CONFIG",
                    **method_edge_attrs,
                )
                add_edge(
                    edges,
                    variant_id,
                    method_node_id(method_id),
                    "CONFIGURES_METHOD",
                    **method_edge_attrs,
                )
                method_configs_by_label.setdefault(method_label, []).append(
                    (variant_id, method_id)
                )
        for method in config.get("baseline_interval_methods", []):
            method_label = str(method)
            add_edge(
                edges,
                config_id,
                method_node_id(method_label),
                "QUEUES_BASELINE_METHOD",
                evidence_path=str(config_path),
                evidence=yaml_selector("baseline_interval_methods", method_label),
            )
        diagnostic_methods = config.get("methods_under_diagnostic", {})
        if isinstance(diagnostic_methods, dict):
            for diagnostic_key, method in diagnostic_methods.items():
                add_edge(
                    edges,
                    config_id,
                    method_node_id(str(method)),
                    "QUEUES_DIAGNOSTIC_METHOD",
                    evidence_path=str(config_path),
                    evidence=f"methods_under_diagnostic.{diagnostic_key}",
                )

    report_root = Path("experiments/regression/reports")
    for report_dir in sorted(path for path in report_root.iterdir() if path.is_dir()):
        report_json = report_dir / "pilot_summary.json"
        report = (
            json.loads(report_json.read_text(encoding="utf-8"))
            if report_json.exists()
            else None
        )
        add_report_directory(
            nodes,
            edges,
            report_dir=report_dir,
            report_payload=report,
            config_ids_by_report_name=config_ids_by_report_name,
            method_configs_by_label=method_configs_by_label,
        )

    cqr_model_matched_root = Path(
        "experiments/regression/reports/model_matched_cqr_rerun_plan"
    )
    cqr_model_matched_manifest_json = (
        cqr_model_matched_root / "model_matched_cqr_rerun_manifest.json"
    )
    cqr_model_matched_manifest_md = cqr_model_matched_manifest_json.with_suffix(".md")
    cqr_fixed_vs_model_matched_json = (
        cqr_model_matched_root / "cqr_fixed_vs_model_matched_synthesis.json"
    )
    cqr_fixed_vs_model_matched_md = (
        cqr_fixed_vs_model_matched_json.with_suffix(".md")
    )
    if cqr_model_matched_manifest_json.exists():
        try:
            cqr_manifest_payload = json.loads(
                cqr_model_matched_manifest_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            cqr_manifest_payload = {}
        cqr_manifest_summary = cqr_manifest_payload.get("summary") or {}
        cqr_manifest_id = "report:model_matched_cqr_rerun_manifest"
        add_node(
            nodes,
            cqr_manifest_id,
            "method_report",
            path=(
                str(cqr_model_matched_manifest_md)
                if cqr_model_matched_manifest_md.exists()
                else None
            ),
            json_path=str(cqr_model_matched_manifest_json),
            generated_config_count=cqr_manifest_summary.get("generated_config_count"),
            expected_cqr_model_matched_run_count=cqr_manifest_summary.get(
                "expected_cqr_model_matched_run_count"
            ),
            expected_atomic_run_count=cqr_manifest_summary.get(
                "expected_atomic_run_count"
            ),
            method_boundary=cqr_manifest_summary.get("method_boundary"),
            summary=(
                "Model-matched CQR rerun manifest. It records generated configs, "
                "run commands, and expected model-matched CQR accounting for the "
                "backend-confound check."
            ),
        )
        add_node(
            nodes,
            "method:cqr_model_matched",
            "method",
            name="cqr_model_matched",
            summary=(
                "Model-matched CQR method variant used to test whether the fixed-GBM "
                "CQR signal was backend-specific."
            ),
        )
        add_edge(
            edges,
            cqr_manifest_id,
            "method:cqr_model_matched",
            "EVALUATES_METHOD",
            evidence_path=str(cqr_model_matched_manifest_json),
            evidence="$.summary.expected_cqr_model_matched_run_count",
        )
        add_edge(
            edges,
            "method:cqr_model_matched",
            "method:cqr",
            "VARIANT_OF_METHOD",
            evidence_path=str(cqr_model_matched_manifest_json),
            evidence="$.summary.fixed_gbm_cqr_rows_preserved",
        )

    if cqr_fixed_vs_model_matched_json.exists():
        try:
            cqr_synthesis_payload = json.loads(
                cqr_fixed_vs_model_matched_json.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            cqr_synthesis_payload = {}
        cqr_synthesis_summary = cqr_synthesis_payload.get("summary") or {}
        selected_counts = (
            cqr_synthesis_summary.get(
                "coverage_eligible_interval_score_selected_counts"
            )
            or {}
        )
        cqr_synthesis_id = "report:cqr_fixed_vs_model_matched_synthesis"
        cqr_control_id = "methodology_control:cqr_backend_sensitivity_check"
        cqr_claim_id = "manuscript_claim:cqr_backend_sensitivity_no_method_winner"
        add_node(
            nodes,
            cqr_synthesis_id,
            "method_report",
            path=(
                str(cqr_fixed_vs_model_matched_md)
                if cqr_fixed_vs_model_matched_md.exists()
                else None
            ),
            json_path=str(cqr_fixed_vs_model_matched_json),
            fixed_gbm_cqr_completed_rows=cqr_synthesis_summary.get(
                "fixed_gbm_cqr_completed_rows"
            ),
            model_matched_cqr_completed_rows=cqr_synthesis_summary.get(
                "model_matched_cqr_completed_rows"
            ),
            paired_cell_count=cqr_synthesis_summary.get("paired_cell_count"),
            fixed_gbm_cqr_selected_cells=selected_counts.get("fixed_gbm_cqr"),
            model_matched_cqr_selected_cells=selected_counts.get(
                "model_matched_cqr"
            ),
            no_coverage_eligible_variant_cells=selected_counts.get(
                "no_coverage_eligible_variant"
            ),
            can_support_method_winner_claim=cqr_synthesis_summary.get(
                "can_support_method_winner_claim"
            ),
            method_boundary=cqr_synthesis_summary.get("method_boundary"),
            summary=(
                "Fixed-GBM CQR versus model-matched CQR synthesis. It completed "
                f"{cqr_synthesis_summary.get('model_matched_cqr_completed_rows')} "
                "model-matched CQR rows, paired "
                f"{cqr_synthesis_summary.get('paired_cell_count')} cells, and "
                "keeps the interpretation at pipeline-level descriptive signal."
            ),
        )
        add_node(
            nodes,
            cqr_control_id,
            "methodology_control",
            name="CQR backend sensitivity check",
            status=cqr_synthesis_summary.get("status"),
            can_support_method_winner_claim=cqr_synthesis_summary.get(
                "can_support_method_winner_claim"
            ),
            method_boundary=cqr_synthesis_summary.get("method_boundary"),
            summary=(
                "Backend-confound control for CQR. It compares fixed-GBM and "
                "model-matched CQR selected cells and preserves a descriptive, "
                "experiment-scoped interpretation."
            ),
        )
        add_node(
            nodes,
            cqr_claim_id,
            "manuscript_claim",
            claim_text=(
                "The completed model-matched CQR rerun supports backend-sensitivity "
                "analysis but does not authorize a method-winner claim."
            ),
            claim_status="closed_to_method_winner_claim",
            public_reading=(
                "CQR remains an experiment-scoped practical signal; no universal "
                "best-method or production guidance is claimed."
            ),
            summary=(
                "Claim-boundary node for the completed fixed-vs-model-matched "
                "CQR synthesis."
            ),
        )
        if cqr_model_matched_manifest_json.exists():
            add_edge(
                edges,
                "report:model_matched_cqr_rerun_manifest",
                cqr_synthesis_id,
                "SUPPORTS_REPORT",
                evidence_path=str(cqr_fixed_vs_model_matched_json),
                evidence="$.source_artifacts",
            )
        for method_id in ("cqr", "cqr_model_matched"):
            add_edge(
                edges,
                cqr_synthesis_id,
                method_node_id(method_id),
                "EVALUATES_METHOD",
                evidence_path=str(cqr_fixed_vs_model_matched_json),
                evidence="$.summary.coverage_eligible_interval_score_selected_counts",
            )
        add_edge(
            edges,
            cqr_claim_id,
            cqr_synthesis_id,
            "SUPPORTED_BY",
            evidence_path=str(cqr_fixed_vs_model_matched_json),
            evidence="$.summary.can_support_method_winner_claim",
        )
        add_edge(
            edges,
            cqr_claim_id,
            cqr_control_id,
            "SUPPORTED_BY",
            evidence_path=str(cqr_fixed_vs_model_matched_json),
            evidence="$.claim_boundaries",
        )
        if "report:method_selection_inferential_audit" in nodes:
            add_edge(
                edges,
                cqr_synthesis_id,
                "report:method_selection_inferential_audit",
                "SUPPORTS_REPORT",
                evidence_path=str(cqr_fixed_vs_model_matched_json),
                evidence="$.summary",
            )
        if "report:final_selection_claim_boundary_audit" in nodes:
            add_edge(
                edges,
                cqr_claim_id,
                "report:final_selection_claim_boundary_audit",
                "SUPPORTED_BY",
                evidence_path=str(cqr_fixed_vs_model_matched_json),
                evidence="$.claim_boundaries",
            )

    add_manuscript_claim_register(
        nodes,
        edges,
        path=Path(args.manuscript_claim_register),
    )

    edges = enrich_edge_traceability(dedupe_edges(edges), nodes)
    enrich_node_observations(nodes, edges)
    payload = {
        "schema": "cpfi_regression_knowledge_graph_v1",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(
            edges, key=lambda item: (item["source"], item["relation"], item["target"])
        ),
    }
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({"status": "ok", "nodes": len(nodes), "edges": len(edges)}))


if __name__ == "__main__":
    main()
