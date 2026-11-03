"""
test_outputs.py: Schema, data type, and validity tests for scored outputs and Power BI tables.
"""

import os
import json
import pytest
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
SCORED_CSV = os.path.join(OUTPUTS_DIR, "scored_comments.csv")
USER_CSV = os.path.join(OUTPUTS_DIR, "user_summary.csv")
DAILY_CSV = os.path.join(OUTPUTS_DIR, "daily_summary.csv")
METRICS_JSON = os.path.join(OUTPUTS_DIR, "metrics.json")


def test_scored_comments_schema_and_types():
    assert os.path.exists(SCORED_CSV), "scored_comments.csv does not exist"
    df = pd.read_csv(SCORED_CSV)
    
    # Required columns
    expected_cols = [
        "comment_id", "user_id", "text", "timestamp", "post_id", "rating", "label",
        "fraud_score", "predicted_label", "risk_band", "top_reason"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column {col} in scored_comments.csv"
        
    # Bounds and constraints
    assert (df["fraud_score"] >= 0.0).all() and (df["fraud_score"] <= 1.0).all()
    assert set(df["predicted_label"].unique()).issubset({0, 1})
    assert set(df["risk_band"].unique()).issubset({"Low", "Medium", "High"})
    assert (df["rating"] >= 1).all() and (df["rating"] <= 5).all()
    assert df["top_reason"].isnull().sum() == 0


def test_user_summary_schema():
    assert os.path.exists(USER_CSV), "user_summary.csv does not exist"
    df = pd.read_csv(USER_CSV)
    
    expected_cols = [
        "user_id", "total_comments", "avg_fraud_score", "flagged_count",
        "high_risk_count", "first_seen", "last_seen", "flag_rate"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column {col} in user_summary.csv"
        
    # user_ids must be unique in user_summary
    assert df["user_id"].nunique() == len(df)
    assert (df["flag_rate"] >= 0.0).all() and (df["flag_rate"] <= 1.0).all()


def test_daily_summary_schema():
    assert os.path.exists(DAILY_CSV), "daily_summary.csv does not exist"
    df = pd.read_csv(DAILY_CSV)
    
    expected_cols = [
        "date", "total_comments", "flagged_comments", "high_risk_comments",
        "avg_fraud_score", "flag_rate"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column {col} in daily_summary.csv"
        
    assert (df["total_comments"] > 0).all()
    assert (df["flag_rate"] >= 0.0).all() and (df["flag_rate"] <= 1.0).all()


def test_metrics_json_and_plots():
    assert os.path.exists(METRICS_JSON), "metrics.json does not exist"
    with open(METRICS_JSON, "r", encoding="utf-8") as f:
        metrics = json.load(f)
        
    assert "chosen_decision_threshold" in metrics
    assert "baseline_model" in metrics
    assert "neural_network_model" in metrics
    assert "verdict" in metrics

    # Diagnostic plot files
    assert os.path.exists(os.path.join(OUTPUTS_DIR, "confusion_matrix.png"))
    assert os.path.exists(os.path.join(OUTPUTS_DIR, "pr_curve.png"))
    assert os.path.exists(os.path.join(OUTPUTS_DIR, "roc_curve.png"))

