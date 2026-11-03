"""
predict_single.py: Real-Time Inference Utility for Comment Fraud Detection.

Allows on-demand scoring of single comments or incoming streams:
- Accepts raw text and optional contextual metadata (rating, user_id, etc.)
- Computes features, scales metadata via saved feature_scaler.joblib
- Evaluates with neural network (models/nn_model.keras)
- Assigns risk band, predicted label, and top explainability reason
"""

import os
import sys
import re
import json
import argparse
import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tensorflow as tf
from src.data_prep import clean_text
from src.score import determine_top_reason

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")

NN_MODEL_PATH = os.path.join(MODELS_DIR, "nn_model.keras")
SCALER_PATH = os.path.join(MODELS_DIR, "feature_scaler.joblib")
METRICS_JSON_PATH = os.path.join(OUTPUTS_DIR, "metrics.json")

METADATA_FEATURE_COLS = [
    "url_count",
    "text_length",
    "word_count",
    "uppercase_ratio",
    "exclamation_ratio",
    "question_ratio",
    "duplicate_text_count",
    "comments_per_user_per_hour",
    "user_five_star_share",
    "rating_deviation",
    "rating"
]

SCALED_META_COLS = [f"scaled_{c}" for c in METADATA_FEATURE_COLS]


class CommentFraudPredictor:
    def __init__(self):
        if not os.path.exists(NN_MODEL_PATH):
            raise FileNotFoundError(f"Trained model not found at {NN_MODEL_PATH}. Train the model first.")
        if not os.path.exists(SCALER_PATH):
            raise FileNotFoundError(f"Feature scaler not found at {SCALER_PATH}. Run features.py first.")

        self.model = tf.keras.models.load_model(NN_MODEL_PATH)
        self.scaler = joblib.load(SCALER_PATH)

        # Load decision threshold
        self.threshold = 0.50
        if os.path.exists(METRICS_JSON_PATH):
            try:
                with open(METRICS_JSON_PATH, "r", encoding="utf-8") as f:
                    metrics = json.load(f)
                    self.threshold = float(metrics.get("chosen_decision_threshold", 0.50))
            except Exception:
                self.threshold = 0.50

        self.url_pattern = re.compile(
            r"https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.(?:com|org|net|io|me|ly|cc|online|xyz)\S*",
            re.IGNORECASE
        )

    def predict(
        self,
        text: str,
        rating: int = 5,
        duplicate_count: int = 1,
        comments_per_hour: int = 1,
        user_5star_share: float = 0.5,
        rating_deviation: float = 0.0
    ) -> dict:
        """
        Scores a single comment and returns risk assessment details.
        """
        raw_text = str(text or "")
        cleaned = clean_text(raw_text)

        # Feature Extraction
        url_count = len(self.url_pattern.findall(raw_text))
        text_length = len(raw_text)
        word_count = len(raw_text.split())

        alpha_chars = sum(1 for c in raw_text if c.isalpha())
        uppercase_ratio = sum(1 for c in raw_text if c.isupper()) / max(alpha_chars, 1) if alpha_chars > 0 else 0.0
        exclamation_ratio = raw_text.count("!") / max(len(raw_text), 1)
        question_ratio = raw_text.count("?") / max(len(raw_text), 1)

        raw_meta = pd.DataFrame([{
            "url_count": url_count,
            "text_length": text_length,
            "word_count": word_count,
            "uppercase_ratio": uppercase_ratio,
            "exclamation_ratio": exclamation_ratio,
            "question_ratio": question_ratio,
            "duplicate_text_count": duplicate_count,
            "comments_per_user_per_hour": comments_per_hour,
            "user_five_star_share": user_5star_share,
            "rating_deviation": rating_deviation,
            "rating": rating
        }])

        # Scale metadata using training scaler
        scaled_meta = self.scaler.transform(raw_meta).astype(np.float32)

        # Predict with Neural Network
        inputs = {
            "text_input": tf.constant([cleaned], dtype=tf.string),
            "meta_input": tf.constant(scaled_meta, dtype=tf.float32)
        }
        score = float(self.model.predict(inputs, verbose=0)[0][0])
        score = round(score, 4)

        # Risk Band
        if score > 0.70:
            risk_band = "High"
        elif score >= 0.40:
            risk_band = "Medium"
        else:
            risk_band = "Low"

        # Predicted label
        predicted_label = 1 if score >= self.threshold else 0

        # Top Reason attribution
        row_dict = {
            "fraud_score": score,
            "url_count": url_count,
            "duplicate_text_count": duplicate_count,
            "comments_per_user_per_hour": comments_per_hour,
            "uppercase_ratio": uppercase_ratio,
            "exclamation_ratio": exclamation_ratio,
            "user_five_star_share": user_5star_share,
            "rating": rating
        }
        top_reason = determine_top_reason(row_dict, self.threshold)

        return {
            "text": raw_text,
            "cleaned_text": cleaned,
            "fraud_score": score,
            "predicted_label": predicted_label,
            "risk_band": risk_band,
            "top_reason": top_reason,
            "decision_threshold": self.threshold,
            "metadata_features": {
                "url_count": url_count,
                "text_length": text_length,
                "word_count": word_count,
                "uppercase_ratio": round(uppercase_ratio, 4),
                "exclamation_ratio": round(exclamation_ratio, 4),
                "rating": rating,
                "duplicate_count": duplicate_count,
                "comments_per_hour": comments_per_hour
            }
        }


def main():
    parser = argparse.ArgumentParser(description="Real-Time Comment Fraud Scoring")
    parser.add_argument("--text", type=str, required=True, help="Raw comment text to evaluate")
    parser.add_argument("--rating", type=int, default=5, help="Rating given with comment (1-5)")
    parser.add_argument("--duplicate-count", type=int, default=1, help="Times this text appeared")
    parser.add_argument("--burst-rate", type=int, default=1, help="User comments in past hour")
    args = parser.parse_args()

    predictor = CommentFraudPredictor()
    result = predictor.predict(
        text=args.text,
        rating=args.rating,
        duplicate_count=args.duplicate_count,
        comments_per_hour=args.burst_rate
    )
    print("\n--- Comment Fraud Analysis Result ---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
