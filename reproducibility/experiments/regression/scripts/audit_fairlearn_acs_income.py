"""Audit Fairlearn ACS Income regression datasets.

Use a small state first for smoke audits, then a planned state panel for the
full experiment. Raw ACS data is downloaded to the Fairlearn cache and is not
committed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fairlearn.datasets import fetch_acs_income

from cpfi.regression.datasets import audit_regression_frame, render_audit_markdown
from cpfi.regression.experiment import atomic_write_json, atomic_write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", default=None)
    parser.add_argument("--state", action="append", default=None)
    parser.add_argument("--out-dir", default="experiments/regression/audits")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_states = args.state or ["WY"]
    states = sorted({state.upper() for state in raw_states})
    dataset_id = args.dataset_id or f"fairlearn_acs_income_{'_'.join(states).lower()}"
    bunch = fetch_acs_income(states=states, as_frame=True)
    df = bunch.frame.copy()
    target = bunch.target.name

    audit = audit_regression_frame(df, target=target, dataset_id=dataset_id)
    payload = audit.to_dict()
    payload["source"] = "fairlearn.datasets.fetch_acs_income"
    payload["states"] = states

    out_dir = Path(args.out_dir) / dataset_id
    atomic_write_json(out_dir / "audit.json", payload)
    atomic_write_text(out_dir / "audit.md", render_audit_markdown(payload))
    print(json.dumps({"status": "ok", "audit_path": str(out_dir / "audit.json")}))


if __name__ == "__main__":
    main()
