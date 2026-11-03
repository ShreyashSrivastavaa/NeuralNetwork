"""
score.py: Batch Scoring, Risk Categorization, Explainability & Summary Rollup Module.

Produces clean, Power BI ready CSV outputs:
1. outputs/scored_comments.csv:
   Contains all original columns + fraud_score, predicted_label, risk_band, top_reason.
2. outputs/user_summary.csv:
   Per-user aggregated metrics (total comments, avg score, flagged count, flag rate, first/last seen).
3. outputs/daily_summary.csv:
   Daily aggregated metrics (date, total comments, flagged count, flag rate, avg score, high risk count).
All dates formatted in ISO 8601; UTF-8 encoded.
"""

import os
import json
import numpy as np
import pandas as pd
import tensorflow as tf

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "all_features.csv")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")

NN_MODEL_PATH = os.path.join(MODELS_DIR, "nn_model.keras")
METRICS_JSON_PATH = os.path.join(OUTPUTS_DIR, "metrics.json")

SCORED_COMMENTS_CSV = os.path.join(OUTPUTS_DIR, "scored_comments.csv")
USER_SUMMARY_CSV = os.path.join(OUTPUTS_DIR, "user_summary.csv")
DAILY_SUMMARY_CSV = os.path.join(OUTPUTS_DIR, "daily_summary.csv")

SCALED_META_COLS = [
    "scaled_url_count",
    "scaled_text_length",
    "scaled_word_count",
    "scaled_uppercase_ratio",
    "scaled_exclamation_ratio",
    "scaled_question_ratio",
    "scaled_duplicate_text_count",
    "scaled_comments_per_user_per_hour",
    "scaled_user_five_star_share",
    "scaled_rating_deviation",
    "scaled_rating"
]


def determine_top_reason(row, threshold: float) -> str:
    """
    Rule-based attribution engine identifying the primary driver behind a fraud flag.
    """
    score = row["fraud_score"]
    
    # Genuine cases
    if score < threshold and score < 0.40:
        return "Genuine / Low Risk"
    
    # Fraudulent / High Risk Cases
    if row.get("url_count", 0) > 0:
        return "Contains Promotional URL"
    elif row.get("duplicate_text_count", 1) >= 3:
        return "Duplicate Spam Campaign"
    elif row.get("comments_per_user_per_hour", 1) >= 4:
        return "Burst Posting Velocity"
    elif row.get("uppercase_ratio", 0.0) >= 0.35:
        return "Excessive Uppercase (Shouting)"
    elif row.get("exclamation_ratio", 0.0) >= 0.05:
        return "Excessive Punctuation"
    elif row.get("user_five_star_share", 0.0) >= 0.90 and row.get("rating", 0) == 5:
        return "Astroturfing 5-Star Pattern"
    elif row.get("rating", 0) == 1 and score >= threshold:
        return "Competitor Smear Attack"
    else:
        return "Suspicious Language & Semantic Signals"


def score_all():
    print("[Score] Starting scoring pipeline...")
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Feature dataset not found at {DATA_PATH}. Run features.py first.")

    df = pd.read_csv(DATA_PATH)
    df["cleaned_text"] = df["cleaned_text"].fillna("").astype(str)

    # Load threshold from metrics.json or fallback to 0.50
    chosen_threshold = 0.50
    if os.path.exists(METRICS_JSON_PATH):
        with open(METRICS_JSON_PATH, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)
            chosen_threshold = float(metrics_data.get("chosen_decision_threshold", 0.50))
    print(f"[Score] Using Decision Threshold: {chosen_threshold:.4f}")

    # Load Neural Network Model
    print(f"[Score] Loading Neural Network model from {NN_MODEL_PATH}...")
    model = tf.keras.models.load_model(NN_MODEL_PATH)

    # Predict probabilities
    print(f"[Score] Generating fraud scores for {len(df)} comments...")
    inputs = {
        "text_input": tf.constant(df["cleaned_text"].values, dtype=tf.string),
        "meta_input": tf.constant(df[SCALED_META_COLS].values.astype(np.float32), dtype=tf.float32)
    }
    probas = model.predict(inputs, batch_size=64, verbose=0).ravel()

    # Append model outputs
    df["fraud_score"] = np.round(probas, 4)
    df["predicted_label"] = (df["fraud_score"] >= chosen_threshold).astype(int)

    # Assign Risk Bands: Low (<0.4), Medium (0.4 to 0.7), High (>0.7)
    conditions = [
        (df["fraud_score"] < 0.40),
        (df["fraud_score"] >= 0.40) & (df["fraud_score"] <= 0.70),
        (df["fraud_score"] > 0.70)
    ]
    choices = ["Low", "Medium", "High"]
    df["risk_band"] = np.select(conditions, choices, default="Medium")

    # Assign Top Reason
    print("[Score] Computing explainability / top_reason annotations...")
    df["top_reason"] = df.apply(lambda row: determine_top_reason(row, chosen_threshold), axis=1)

    # 1. Export scored_comments.csv (Original columns + 4 scored columns)
    original_cols = ["comment_id", "user_id", "text", "timestamp", "post_id", "rating", "label"]
    export_cols = original_cols + ["fraud_score", "predicted_label", "risk_band", "top_reason"]
    
    scored_df = df[export_cols].copy()
    scored_df.to_csv(SCORED_COMMENTS_CSV, index=False, encoding="utf-8")
    print(f"[Score] Exported scored comments to {SCORED_COMMENTS_CSV} ({len(scored_df)} rows)")

    # 2. Export user_summary.csv
    print("[Score] Generating user summary rollup...")
    user_grp = scored_df.groupby("user_id")
    user_summary = user_grp.agg(
        total_comments=("comment_id", "count"),
        avg_fraud_score=("fraud_score", "mean"),
        flagged_count=("predicted_label", "sum"),
        high_risk_count=("risk_band", lambda s: (s == "High").sum()),
        first_seen=("timestamp", "min"),
        last_seen=("timestamp", "max")
    ).reset_index()

    user_summary["flag_rate"] = np.round(user_summary["flagged_count"] / user_summary["total_comments"], 4)
    user_summary["avg_fraud_score"] = np.round(user_summary["avg_fraud_score"], 4)

    # Sort descending by flagged count, then avg score
    user_summary = user_summary.sort_values(by=["flagged_count", "avg_fraud_score"], ascending=[False, False])
    user_summary.to_csv(USER_SUMMARY_CSV, index=False, encoding="utf-8")
    print(f"[Score] Exported user summary to {USER_SUMMARY_CSV} ({len(user_summary)} unique users)")

    # 3. Export daily_summary.csv
    print("[Score] Generating daily time series summary rollup...")
    scored_df["date"] = scored_df["timestamp"].str[:10]
    daily_grp = scored_df.groupby("date")
    daily_summary = daily_grp.agg(
        total_comments=("comment_id", "count"),
        flagged_comments=("predicted_label", "sum"),
        high_risk_comments=("risk_band", lambda s: (s == "High").sum()),
        avg_fraud_score=("fraud_score", "mean")
    ).reset_index()

    daily_summary["flag_rate"] = np.round(daily_summary["flagged_comments"] / daily_summary["total_comments"], 4)
    daily_summary["avg_fraud_score"] = np.round(daily_summary["avg_fraud_score"], 4)

    # Sort chronologically
    daily_summary = daily_summary.sort_values(by="date", ascending=True)
    daily_summary.to_csv(DAILY_SUMMARY_CSV, index=False, encoding="utf-8")
    print(f"[Score] Exported daily summary to {DAILY_SUMMARY_CSV} ({len(daily_summary)} days)")

    # Quick sanity check summary
    print("\n--- Scoring Summary Statistics ---")
    print(f"Total Comments:     {len(scored_df):,}")
    print(f"Flagged Comments:   {scored_df['predicted_label'].sum():,} ({scored_df['predicted_label'].mean():.2%})")
    print(f"High Risk Count:    {(scored_df['risk_band'] == 'High').sum():,}")
    print(f"Medium Risk Count:  {(scored_df['risk_band'] == 'Medium').sum():,}")
    print(f"Low Risk Count:     {(scored_df['risk_band'] == 'Low').sum():,}")
    print(f"Suspicious Users:   {len(user_summary[user_summary['flagged_count'] > 0]):,}")

    return scored_df, user_summary, daily_summary


if __name__ == "__main__":
    score_all()

