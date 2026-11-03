"""
train_baseline.py: Baseline Model Training Module.

Implements a strong, production-grade baseline:
- Text representation: TF-IDF (unigram + bigram, max 5,000 features)
- Metadata: Scaled numerical and behavioral features
- Classifier: Logistic Regression with balanced class weights
- Persists model and vectorizer artifacts in models/
"""

import os
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    classification_report
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

VECTORIZER_PATH = os.path.join(MODELS_DIR, "tfidf_vectorizer.joblib")
BASELINE_MODEL_PATH = os.path.join(MODELS_DIR, "baseline_model.joblib")

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


def load_data():
    train_df = pd.read_csv(os.path.join(DATA_DIR, "train_features.csv"))
    val_df = pd.read_csv(os.path.join(DATA_DIR, "val_features.csv"))
    test_df = pd.read_csv(os.path.join(DATA_DIR, "test_features.csv"))
    
    # Fill any missing text
    train_df["cleaned_text"] = train_df["cleaned_text"].fillna("")
    val_df["cleaned_text"] = val_df["cleaned_text"].fillna("")
    test_df["cleaned_text"] = test_df["cleaned_text"].fillna("")
    
    return train_df, val_df, test_df


def train_baseline():
    print("[Baseline] Loading datasets...")
    train_df, val_df, test_df = load_data()
    os.makedirs(MODELS_DIR, exist_ok=True)

    y_train = train_df["label"].values
    y_val = val_df["label"].values
    y_test = test_df["label"].values

    # TF-IDF Vectorization on cleaned text
    print("[Baseline] Fitting TF-IDF Vectorizer (max_features=5000, ngrams=(1,2))...")
    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), min_df=2)
    X_train_text = vectorizer.fit_transform(train_df["cleaned_text"])
    X_val_text = vectorizer.transform(val_df["cleaned_text"])
    X_test_text = vectorizer.transform(test_df["cleaned_text"])

    # Combine TF-IDF features with scaled metadata
    X_train_meta = train_df[SCALED_META_COLS].values
    X_val_meta = val_df[SCALED_META_COLS].values
    X_test_meta = test_df[SCALED_META_COLS].values

    X_train = hstack([X_train_text, X_train_meta]).tocsr()
    X_val = hstack([X_val_text, X_val_meta]).tocsr()
    X_test = hstack([X_test_text, X_test_meta]).tocsr()

    print(f"[Baseline] Feature matrix shape: Train={X_train.shape}, Test={X_test.shape}")

    # Train Logistic Regression with class_weight='balanced'
    print("[Baseline] Training LogisticRegression(class_weight='balanced', random_state=42)...")
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_train, y_train)

    # Persist artifacts
    joblib.dump(vectorizer, VECTORIZER_PATH)
    joblib.dump(model, BASELINE_MODEL_PATH)
    print(f"[Baseline] Saved TF-IDF Vectorizer to {VECTORIZER_PATH}")
    print(f"[Baseline] Saved Baseline Model to {BASELINE_MODEL_PATH}")

    # Evaluation on Test Set
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)

    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    pr_auc = average_precision_score(y_test, y_pred_proba)
    acc = accuracy_score(y_test, y_pred)

    print("\n--- Baseline Model Test Performance ---")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"ROC-AUC:   {roc_auc:.4f}")
    print(f"PR-AUC:    {pr_auc:.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred, digits=4))

    return {
        "model": model,
        "vectorizer": vectorizer,
        "test_metrics": {
            "accuracy": float(acc),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "roc_auc": float(roc_auc),
            "pr_auc": float(pr_auc)
        }
    }


if __name__ == "__main__":
    train_baseline()

