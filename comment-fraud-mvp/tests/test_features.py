"""
test_features.py: Tests for metadata feature extraction, bounding, and data integrity.
"""

import os
import pytest
import pandas as pd
import numpy as np
from src.features import extract_raw_features, METADATA_FEATURE_COLS

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "comment_id": "C_0001",
            "user_id": "U_001",
            "text": "Great product! Check https://example.com for more info!!",
            "cleaned_text": "great product ! check _url_ for more info !!",
            "timestamp": "2026-08-01T10:00:00Z",
            "post_id": "P_001",
            "rating": 5,
            "label": 0
        },
        {
            "comment_id": "C_0002",
            "user_id": "U_001",
            "text": "FREE MONEY CLAIM NOW AT http://t.me/scam",
            "cleaned_text": "free money claim now at _url_",
            "timestamp": "2026-08-01T10:15:00Z",
            "post_id": "P_002",
            "rating": 5,
            "label": 1
        }
    ])


def test_extract_raw_features_columns(sample_df):
    featured = extract_raw_features(sample_df)
    for col in METADATA_FEATURE_COLS:
        assert col in featured.columns, f"Missing expected feature {col}"
        assert not featured[col].isnull().any(), f"Feature {col} contains NaNs"


def test_feature_bounds(sample_df):
    featured = extract_raw_features(sample_df)
    
    # Ratios must be within [0, 1]
    assert (featured["uppercase_ratio"] >= 0.0).all() and (featured["uppercase_ratio"] <= 1.0).all()
    assert (featured["exclamation_ratio"] >= 0.0).all() and (featured["exclamation_ratio"] <= 1.0).all()
    assert (featured["user_five_star_share"] >= 0.0).all() and (featured["user_five_star_share"] <= 1.0).all()
    
    # Counts must be non-negative
    assert (featured["url_count"] >= 0).all()
    assert (featured["text_length"] > 0).all()
    assert (featured["word_count"] > 0).all()
    assert (featured["comments_per_user_per_hour"] >= 1).all()

