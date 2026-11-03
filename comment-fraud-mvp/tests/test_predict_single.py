"""
test_predict_single.py: Unit tests for real-time single comment inference.
"""

import pytest
from src.predict_single import CommentFraudPredictor


def test_predict_single_fraud():
    predictor = CommentFraudPredictor()
    res = predictor.predict(
        text="FREE BITCOIN GIVEAWAY!! Invest $100 earn $1000 at http://bit.ly/crypto-scam hurry limited slots!!",
        rating=5,
        duplicate_count=4,
        comments_per_hour=5
    )
    assert res["fraud_score"] > 0.70
    assert res["risk_band"] == "High"
    assert "URL" in res["top_reason"] or "Duplicate" in res["top_reason"] or "Burst" in res["top_reason"]


def test_predict_single_genuine():
    predictor = CommentFraudPredictor()
    res = predictor.predict(
        text="The setup instructions were clear and the product worked reliably right out of the box.",
        rating=4,
        duplicate_count=1,
        comments_per_hour=1
    )
    assert res["fraud_score"] < 0.40
    assert res["risk_band"] == "Low"
    assert res["predicted_label"] == 0
    assert res["top_reason"] == "Genuine / Low Risk"
