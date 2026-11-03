"""
test_data_prep.py: Unit and integration tests for data preparation and text cleaning.
"""

import os
import pytest
import pandas as pd
from src.data_prep import clean_text, generate_realistic_dataset, prepare_data

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_clean_text_html_stripping():
    raw = "<p>Check this out <b>bold</b> and <a href='http://spam.com'>link</a></p>"
    cleaned = clean_text(raw)
    assert "<p>" not in cleaned
    assert "<b>" not in cleaned
    assert "<a" not in cleaned
    assert "_url_" in cleaned


def test_clean_text_url_normalization():
    raw = "Invest with us at https://t.me/crypto_fast or www.scamdeal.xyz today!"
    cleaned = clean_text(raw)
    assert "https://t.me/crypto_fast" not in cleaned
    assert "_url_" in cleaned


def test_clean_text_empty_and_none():
    assert clean_text("") == ""
    assert clean_text(None) == ""


def test_dataset_generation_schema_and_balance():
    df = generate_realistic_dataset(n_samples=500, fraud_ratio=0.15)
    expected_cols = {"comment_id", "user_id", "text", "timestamp", "post_id", "rating", "label"}
    assert expected_cols.issubset(set(df.columns))
    assert len(df) == 500
    
    # Check no missing values
    assert df["comment_id"].isnull().sum() == 0
    assert df["text"].isnull().sum() == 0
    assert df["label"].isnull().sum() == 0
    
    # Check fraud balance (~15%)
    fraud_rate = df["label"].mean()
    assert 0.12 <= fraud_rate <= 0.18

    # Check rating range [1, 5]
    assert df["rating"].min() >= 1
    assert df["rating"].max() <= 5

