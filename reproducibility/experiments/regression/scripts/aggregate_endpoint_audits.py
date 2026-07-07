"""Aggregate partial regression endpoint audits into one full audit report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from cpfi.regression.experiment import atomic_write_json, atomic_write_text
from experiments.regression.scripts.audit_regression_endpoints import (
    empty_method_stats,
    render_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--partial",
        action="append",
        default=[],
        help="Partial endpoint audit JSON path. May be repeated.",
    )
    parser.add_argument(
        "--glob",
        default=None,
        help="Optional glob for partial endpoint audit JSON paths.",
    )
    parser.add_argument("--out-dir", required=True, help="Output report directory.")
    parser.add_argument("--title", required=True, help="Markdown report title.")
    parser.add_argument("--output-prefix", default="endpoint_audit")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _same_or_raise(values: list[Any], label: str) -> Any:
    if not values:
        return None
    first = values[0]
    if any(value != first for value in values[1:]):
        raise ValueError(f"partial endpoint audits disagree on {label}")
    return first


def _sum_counter_dicts(values: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for value in values:
        counter.update({str(key): int(count) for key, count in value.items()})
    return dict(sorted(counter.items()))


def _subtract_counts(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    diff = Counter(left) - Counter(right)
    return dict(sorted({key: int(value) for key, value in diff.items()}.items()))


def _combine_stats(stats_list: list[dict[str, Any]]) -> dict[str, Any]:
    combined = empty_method_stats()
    for stats in stats_list:
        for key, value in stats.items():
            if key in {"max_width", "max_upper"}:
                if value is not None:
                    combined[key] = (
                        value if combined[key] is None else max(combined[key], value)
                    )
            elif key == "min_lower":
                if value is not None:
                    combined[key] = (
                        value if combined[key] is None else min(combined[key], value)
                    )
            else:
                combined[key] = int(combined.get(key, 0)) + int(value)
    return combined


def _load_partials(paths: list[Path]) -> list[dict[str, Any]]:
    if not paths:
        raise ValueError("no partial endpoint audits provided")
    sorted_paths = sorted(paths)
    payloads = [read_json(path) for path in sorted_paths]
    for path, payload in zip(sorted_paths, payloads, strict=True):
        if payload.get("audit_schema") != "cpfi_regression_endpoint_audit_v2":
            raise ValueError(f"{path} is not an endpoint audit v2 payload")
    return payloads


def aggregate_endpoint_audits(paths: list[Path]) -> dict[str, Any]:
    payloads = _load_partials(paths)
    sorted_paths = sorted(paths)
    available_counts = _same_or_raise(
        [payload.get("available_completed_method_counts", {}) for payload in payloads],
        "available completed method counts",
    )
    observed_min = _same_or_raise(
        [payload.get("observed_target_min") for payload in payloads],
        "observed target minimum",
    )
    observed_max = _same_or_raise(
        [payload.get("observed_target_max") for payload in payloads],
        "observed target maximum",
    )
    lower_floor = _same_or_raise(
        [payload.get("lower_floor") for payload in payloads],
        "lower floor",
    )
    upper_warning = _same_or_raise(
        [payload.get("upper_warning") for payload in payloads],
        "upper warning",
    )
    config = _same_or_raise([payload.get("config") for payload in payloads], "config")
    ledger = _same_or_raise([payload.get("ledger") for payload in payloads], "ledger")
    total_completed_rows = _same_or_raise(
        [payload.get("total_completed_ledger_rows") for payload in payloads],
        "total completed ledger rows",
    )

    method_summary_parts: dict[str, list[dict[str, Any]]] = {}
    for payload in payloads:
        for method, stats in payload.get("method_summary", {}).items():
            method_summary_parts.setdefault(str(method), []).append(stats)
    method_summary = {
        method: _combine_stats(stats_list)
        for method, stats_list in method_summary_parts.items()
    }

    configured_counts = _sum_counter_dicts(
        [payload.get("configured_completed_method_counts", {}) for payload in payloads]
    )
    omitted_counts = _subtract_counts(available_counts, configured_counts)
    full_method_coverage = not omitted_counts and configured_counts == available_counts
    completed_ledger_rows = sum(
        int(payload.get("completed_ledger_rows", 0)) for payload in payloads
    )
    failures = [
        failure for payload in payloads for failure in payload.get("failures", [])
    ][:50]
    payload = {
        "audit_schema": "cpfi_regression_endpoint_audit_v2",
        "method_filter": {
            "include_methods": [],
            "exclude_methods": [],
            "max_completed": None,
            "full_method_coverage": full_method_coverage,
            "aggregated_partial_count": len(payloads),
            "aggregated_partial_paths": [str(path) for path in sorted_paths],
        },
        "total_completed_ledger_rows": int(total_completed_rows),
        "filtered_completed_ledger_rows": completed_ledger_rows,
        "completed_ledger_rows": completed_ledger_rows,
        "reconstructed_runs": sum(
            int(payload.get("reconstructed_runs", 0)) for payload in payloads
        ),
        "missing_artifacts": sum(
            int(payload.get("missing_artifacts", 0)) for payload in payloads
        ),
        "reconstruction_failures": sum(
            int(payload.get("reconstruction_failures", 0)) for payload in payloads
        ),
        "observed_target_min": observed_min,
        "observed_target_max": observed_max,
        "lower_floor": lower_floor,
        "upper_warning": upper_warning,
        "available_completed_method_counts": available_counts,
        "filtered_completed_method_counts": configured_counts,
        "configured_completed_method_counts": configured_counts,
        "omitted_completed_method_counts": omitted_counts,
        "totals": _combine_stats([payload.get("totals", {}) for payload in payloads]),
        "method_summary": dict(sorted(method_summary.items())),
        "cache_stats": _sum_counter_dicts(
            [payload.get("cache_stats", {}) for payload in payloads]
        ),
        "failures": failures,
        "failure_count_total": sum(
            int(payload.get("failure_count_total", 0)) for payload in payloads
        ),
    }
    if config is not None:
        payload["config"] = config
    if ledger is not None:
        payload["ledger"] = ledger
    return payload


def collect_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(value) for value in args.partial]
    if args.glob:
        paths.extend(Path().glob(args.glob))
    return sorted(dict.fromkeys(paths))


def main() -> None:
    args = parse_args()
    paths = collect_paths(args)
    payload = aggregate_endpoint_audits(paths)
    output_prefix = str(args.output_prefix)
    if not output_prefix or "/" in output_prefix or "\\" in output_prefix:
        raise ValueError(f"invalid output prefix: {output_prefix!r}")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out_dir / f"{output_prefix}.json", payload)
    atomic_write_text(
        out_dir / f"{output_prefix}.md",
        render_markdown(args.title, payload),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "output_prefix": output_prefix,
                "full_method_coverage": payload["method_filter"][
                    "full_method_coverage"
                ],
                "completed_ledger_rows": payload["completed_ledger_rows"],
                "reconstructed_runs": payload["reconstructed_runs"],
                "reconstruction_failures": payload["reconstruction_failures"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
