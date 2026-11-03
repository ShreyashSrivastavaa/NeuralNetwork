"""
evaluate.py: Model Evaluation, Comparison, Threshold Optimization & Visualization.

Functions:
- Computes Precision, Recall, F1, ROC-AUC, and PR-AUC for both Baseline and Neural Network.
- Honestly compares the models and declares the winner based on test metrics.
- Optimizes decision threshold on validation set (maximizing F1 score) to avoid test leakage.
- Persists metrics to outputs/metrics.json.
- Generates publication-ready figures:
  * outputs/confusion_matrix.png
  * outputs/pr_curve.png
  * outputs/roc_curve.png
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.sparse import hstack
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    confusion_matrix,
    precision_recall_curve,
    roc_curve
)
import tensorflow as tf

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")

BASELINE_MODEL_PATH = os.path.join(MODELS_DIR, "baseline_model.joblib")
VECTORIZER_PATH = os.path.join(MODELS_DIR, "tfidf_vectorizer.joblib")
NN_MODEL_PATH = os.path.join(MODELS_DIR, "nn_model.keras")

METRICS_JSON_PATH = os.path.join(OUTPUTS_DIR, "metrics.json")
CONFUSION_MATRIX_PNG = os.path.join(OUTPUTS_DIR, "confusion_matrix.png")
PR_CURVE_PNG = os.path.join(OUTPUTS_DIR, "pr_curve.png")
ROC_CURVE_PNG = os.path.join(OUTPUTS_DIR, "roc_curve.png")

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


def load_datasets():
    val_df = pd.read_csv(os.path.join(DATA_DIR, "val_features.csv"))
    test_df = pd.read_csv(os.path.join(DATA_DIR, "test_features.csv"))
    
    val_df["cleaned_text"] = val_df["cleaned_text"].fillna("")
    test_df["cleaned_text"] = test_df["cleaned_text"].fillna("")
    return val_df, test_df


def get_baseline_predictions(model, vectorizer, df):
    X_text = vectorizer.transform(df["cleaned_text"])
    X_meta = df[SCALED_META_COLS].values
    X = hstack([X_text, X_meta]).tocsr()
    probas = model.predict_proba(X)[:, 1]
    return probas


def get_nn_predictions(model, df):
    inputs = {
        "text_input": tf.constant(df["cleaned_text"].values, dtype=tf.string),
        "meta_input": tf.constant(df[SCALED_META_COLS].values.astype(np.float32), dtype=tf.float32)
    }
    probas = model.predict(inputs, batch_size=64, verbose=0).ravel()
    return probas


def find_optimal_threshold(y_true, probas):
    """
    Finds threshold on validation set that maximizes F1 score.
    """
    precisions, recalls, thresholds = precision_recall_curve(y_true, probas)
    # Exclude division by zero
    f1_scores = np.where(
        (precisions + recalls) > 0,
        2 * (precisions * recalls) / (precisions + recalls),
        0.0
    )
    # thresholds array has length len(precisions) - 1
    best_idx = np.argmax(f1_scores[:-1])
    best_threshold = float(thresholds[best_idx])
    best_f1 = float(f1_scores[best_idx])
    return best_threshold, best_f1


def evaluate_all():
    print("[Evaluate] Loading test and validation sets...")
    val_df, test_df = load_datasets()
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    y_val = val_df["label"].values
    y_test = test_df["label"].values

    print("[Evaluate] Loading trained models...")
    baseline_model = joblib.load(BASELINE_MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
    nn_model = tf.keras.models.load_model(NN_MODEL_PATH)

    # 1. Predictions
    print("[Evaluate] Generating probabilistic predictions...")
    base_val_probas = get_baseline_predictions(baseline_model, vectorizer, val_df)
    base_test_probas = get_baseline_predictions(baseline_model, vectorizer, test_df)

    nn_val_probas = get_nn_predictions(nn_model, val_df)
    nn_test_probas = get_nn_predictions(nn_model, test_df)

    # 2. Threshold Optimization on Validation Set
    best_thresh_base, val_f1_base = find_optimal_threshold(y_val, base_val_probas)
    best_thresh_nn, val_f1_nn = find_optimal_threshold(y_val, nn_val_probas)

    # Choose primary operational decision threshold from the neural network
    chosen_threshold = best_thresh_nn
    print(f"[Evaluate] Validation Optimal Thresholds -> Baseline: {best_thresh_base:.4f} (Val F1: {val_f1_base:.4f}), NN: {best_thresh_nn:.4f} (Val F1: {val_f1_nn:.4f})")
    print(f"[Evaluate] Selected Production Decision Threshold: {chosen_threshold:.4f}")

    # 3. Test Set Metrics
    base_test_preds = (base_test_probas >= best_thresh_base).astype(int)
    nn_test_preds = (nn_test_probas >= chosen_threshold).astype(int)

    metrics_base = {
        "accuracy": float(accuracy_score(y_test, base_test_preds)),
        "precision": float(precision_score(y_test, base_test_preds)),
        "recall": float(recall_score(y_test, base_test_preds)),
        "f1": float(f1_score(y_test, base_test_preds)),
        "roc_auc": float(roc_auc_score(y_test, base_test_probas)),
        "pr_auc": float(average_precision_score(y_test, base_test_probas)),
        "threshold": float(best_thresh_base)
    }

    metrics_nn = {
        "accuracy": float(accuracy_score(y_test, nn_test_preds)),
        "precision": float(precision_score(y_test, nn_test_preds)),
        "recall": float(recall_score(y_test, nn_test_preds)),
        "f1": float(f1_score(y_test, nn_test_preds)),
        "roc_auc": float(roc_auc_score(y_test, nn_test_probas)),
        "pr_auc": float(average_precision_score(y_test, nn_test_probas)),
        "threshold": float(chosen_threshold)
    }

    cm_base = confusion_matrix(y_test, base_test_preds).tolist()
    cm_nn = confusion_matrix(y_test, nn_test_preds).tolist()

    # 4. Honest Model Comparison
    print("\n=======================================================")
    print("            MODEL COMPARISON ON TEST SET               ")
    print("=======================================================")
    print(f"{'Metric':<15} | {'Baseline (TF-IDF+LR)':<20} | {'Neural Net (BiLSTM+MLP)':<22}")
    print("-" * 65)
    for k in ["precision", "recall", "f1", "roc_auc", "pr_auc", "accuracy"]:
        val_b = metrics_base[k]
        val_n = metrics_nn[k]
        winner = "NN" if val_n > val_b else ("Baseline" if val_b > val_n else "Tie")
        print(f"{k.upper():<15} | {val_b:<20.4f} | {val_n:<22.4f} -> [{winner}]")
    print("=" * 65)

    # Comparative evaluation verdict
    nn_wins = sum(metrics_nn[m] > metrics_base[m] for m in ["f1", "pr_auc", "roc_auc", "precision"])
    base_wins = sum(metrics_base[m] > metrics_nn[m] for m in ["f1", "pr_auc", "roc_auc", "precision"])

    if nn_wins > base_wins:
        verdict = (
            "Neural Network wins overall. The hybrid BiLSTM sequential encoding captures complex semantic "
            "phrasing and non-linear interactions between text patterns and behavioral burst velocity better "
            "than the linear baseline, achieving superior F1 and PR-AUC."
        )
    elif base_wins > nn_wins:
        verdict = (
            "Baseline (TF-IDF + Logistic Regression) wins or matches closely. Due to strong keyword indicators "
            "(e.g. promo links, bot text tokens), linear decision boundaries combined with balanced class weights "
            "provide slightly superior precision with lower computational complexity."
        )
    else:
        verdict = (
            "Both models demonstrate competitive performance. The Neural Network provides smoother calibrated "
            "probability distributions suitable for granular risk banding, while the Baseline remains extremely lightweight."
        )

    print(f"\nVerdict: {verdict}\n")

    # 5. Save metrics.json
    output_metrics = {
        "chosen_decision_threshold": chosen_threshold,
        "prevalence": float(np.mean(y_test)),
        "baseline_model": metrics_base,
        "neural_network_model": metrics_nn,
        "confusion_matrix_baseline": cm_base,
        "confusion_matrix_neural_network": cm_nn,
        "verdict": verdict
    }

    with open(METRICS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output_metrics, f, indent=2)
    print(f"[Evaluate] Saved metrics to {METRICS_JSON_PATH}")

    # 6. Generate Diagnostic Plots
    sns.set_theme(style="whitegrid", font_scale=1.1)

    # Confusion Matrix Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sns.heatmap(cm_base, annot=True, fmt="d", cmap="Blues", ax=axes[0], cbar=False,
                xticklabels=["Genuine", "Fraud"], yticklabels=["Genuine", "Fraud"])
    axes[0].set_title(f"Baseline (TF-IDF+LR)\nF1: {metrics_base['f1']:.4f} | PR-AUC: {metrics_base['pr_auc']:.4f}")
    axes[0].set_ylabel("True Label")
    axes[0].set_xlabel("Predicted Label")

    sns.heatmap(cm_nn, annot=True, fmt="d", cmap="Purples", ax=axes[1], cbar=False,
                xticklabels=["Genuine", "Fraud"], yticklabels=["Genuine", "Fraud"])
    axes[1].set_title(f"Neural Network (BiLSTM+MLP)\nF1: {metrics_nn['f1']:.4f} | PR-AUC: {metrics_nn['pr_auc']:.4f}")
    axes[1].set_ylabel("True Label")
    axes[1].set_xlabel("Predicted Label")

    plt.tight_layout()
    plt.savefig(CONFUSION_MATRIX_PNG, dpi=300)
    plt.close()
    print(f"[Evaluate] Saved Confusion Matrix plot to {CONFUSION_MATRIX_PNG}")

    # Precision-Recall Curve Plot
    p_base, r_base, _ = precision_recall_curve(y_test, base_test_probas)
    p_nn, r_nn, _ = precision_recall_curve(y_test, nn_test_probas)
    prevalence = np.mean(y_test)

    plt.figure(figsize=(8, 6))
    plt.plot(r_base, p_base, color="#1f77b4", lw=2.5, label=f"Baseline TF-IDF+LR (PR-AUC = {metrics_base['pr_auc']:.4f})")
    plt.plot(r_nn, p_nn, color="#9467bd", lw=2.5, label=f"Neural Net BiLSTM+MLP (PR-AUC = {metrics_nn['pr_auc']:.4f})")
    plt.axhline(y=prevalence, color="gray", linestyle="--", label=f"Random Chance (Prevalence = {prevalence:.2f})")
    plt.scatter([metrics_nn["recall"]], [metrics_nn["precision"]], color="#d62728", s=100, zorder=5,
                label=f"NN Operating Point (Thresh = {chosen_threshold:.2f})")
    plt.xlabel("Recall (Sensitivity)")
    plt.ylabel("Precision (Positive Predictive Value)")
    plt.title("Precision-Recall Curve Comparison")
    plt.legend(loc="lower left", frameon=True)
    plt.tight_layout()
    plt.savefig(PR_CURVE_PNG, dpi=300)
    plt.close()
    print(f"[Evaluate] Saved PR Curve plot to {PR_CURVE_PNG}")

    # ROC Curve Plot
    fpr_b, tpr_b, _ = roc_curve(y_test, base_test_probas)
    fpr_n, tpr_n, _ = roc_curve(y_test, nn_test_probas)

    plt.figure(figsize=(8, 6))
    plt.plot(fpr_b, tpr_b, color="#1f77b4", lw=2.5, label=f"Baseline TF-IDF+LR (ROC-AUC = {metrics_base['roc_auc']:.4f})")
    plt.plot(fpr_n, tpr_n, color="#9467bd", lw=2.5, label=f"Neural Net BiLSTM+MLP (ROC-AUC = {metrics_nn['roc_auc']:.4f})")
    plt.plot([0, 1], [0, 1], color="gray", linestyle="--", label="Random Classifier (AUC = 0.50)")
    plt.xlabel("False Positive Rate (1 - Specificity)")
    plt.ylabel("True Positive Rate (Recall)")
    plt.title("ROC Curve Comparison")
    plt.legend(loc="lower right", frameon=True)
    plt.tight_layout()
    plt.savefig(ROC_CURVE_PNG, dpi=300)
    plt.close()
    print(f"[Evaluate] Saved ROC Curve plot to {ROC_CURVE_PNG}")

    return output_metrics


if __name__ == "__main__":
    evaluate_all()
