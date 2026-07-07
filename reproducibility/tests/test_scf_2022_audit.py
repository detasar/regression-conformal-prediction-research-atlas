import pandas as pd

from experiments.regression.scripts.audit_scf_2022_networth import (
    DATASET_ID,
    TARGET,
    build_model_frame,
    build_profile,
    signed_log1p,
)


def test_build_profile_records_scf_imputation_and_leakage_policy():
    rows = []
    for family_id in [101, 202]:
        for implicate in [1, 2, 3, 4, 5]:
            rows.append(
                {
                    "YY1": family_id,
                    "Y1": family_id * 10 + implicate,
                    "WGT": 100.0 + implicate,
                    "HHSEX": 1 if family_id == 101 else 2,
                    "AGE": 40 + implicate,
                    "AGECL": 2,
                    "EDUC": 10,
                    "EDCL": 3,
                    "MARRIED": 1,
                    "KIDS": 2 if family_id == 101 else 0,
                    "LF": 1,
                    "LIFECL": 3,
                    "FAMSTRUCT": 4,
                    "RACECL": 1 if family_id == 101 else 2,
                    "RACECL4": 1 if family_id == 101 else 3,
                    "RACECL5": 1 if family_id == 101 else 3,
                    "RACE": 1 if family_id == 101 else 3,
                    "OCCAT1": 1,
                    "OCCAT2": 2,
                    "INDCAT": 3,
                    "INCOME": 80000 + implicate * 1000,
                    "NORMINC": 75000 + implicate * 1000,
                    "WAGEINC": 70000,
                    "SAVED": 1,
                    "WSAVED": 3,
                    "FINLIT": 4,
                    "ASSET": 250000,
                    "DEBT": 50000,
                    "NETWORTH": 200000 if family_id == 101 else -10000,
                    "NWCAT": 4,
                    "NWPCTLECAT": 8,
                }
            )
    source = pd.DataFrame(rows)

    model_frame, target_filter = build_model_frame(source)
    profile = build_profile(source, header=list(source.columns))

    assert profile["dataset_id"] == DATASET_ID
    assert model_frame.shape[0] == 10
    assert target_filter["family_count"] == 2
    assert target_filter["implicate_count_profile"] == {"5": 2}
    assert "YY1" not in model_frame.columns
    assert "ASSET" not in model_frame.columns
    assert "DEBT" not in model_frame.columns
    assert "NWCAT" not in model_frame.columns
    assert TARGET in model_frame.columns
    assert "RACECL" in profile["audit"]["sensitive_candidates"]
    assert "five implicates" in profile["audit"]["survey_policy"]
    assert "NETWORTH=ASSET-DEBT" in profile["leakage_manifest"]["target_definition"]
    assert signed_log1p(pd.Series([-1, 0, 1])).tolist() == [
        -0.6931471805599453,
        0.0,
        0.6931471805599453,
    ]
