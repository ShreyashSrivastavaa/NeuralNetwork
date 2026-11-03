"""
train_nn.py: Neural Network Training Module (Keras Multi-Input Architecture).

Architecture:
- Text Branch: TextVectorization -> Embedding -> Bidirectional LSTM -> Dropout
- Metadata Branch: Scaled metadata features -> Dense -> Dropout
- Fusion: Concatenation -> Dense -> Dropout -> Sigmoid Output (fraud probability)

Training details:
- tf.data.Dataset pipeline for high throughput and robust dtype handling in Keras 3
- Loss: Binary Cross-Entropy
- Optimization: Adam (lr=1e-3)
- Regularization: EarlyStopping on validation PR-AUC, Dropout
- Imbalance handling: Balanced class weights
- Persistence: models/nn_model.keras
"""

import os
import random
import numpy as np
import pandas as pd
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    classification_report
)

# Set deterministic seeds
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
os.environ["PYTHONHASHSEED"] = str(SEED)
os.environ["TF_DETERMINISTIC_OPS"] = "1"

import tensorflow as tf
tf.random.set_seed(SEED)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
NN_MODEL_PATH = os.path.join(MODELS_DIR, "nn_model.keras")

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
    
    train_df["cleaned_text"] = train_df["cleaned_text"].fillna("").astype(str)
    val_df["cleaned_text"] = val_df["cleaned_text"].fillna("").astype(str)
    test_df["cleaned_text"] = test_df["cleaned_text"].fillna("").astype(str)
    
    return train_df, val_df, test_df


def build_multi_input_model(vectorizer, n_meta_features=11, vocab_size=5000):
    """
    Constructs the Keras multi-input hybrid neural network.
    """
    # 1. Text Input & Vectorization
    text_input = tf.keras.layers.Input(shape=(), dtype=tf.string, name="text_input")
    
    # Text Branch
    x_text = vectorizer(text_input)
    x_text = tf.keras.layers.Embedding(input_dim=vocab_size, output_dim=64, mask_zero=True, name="embedding")(x_text)
    x_text = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(32, dropout=0.2), name="bilstm")(x_text)
    x_text = tf.keras.layers.Dropout(0.3, name="text_dropout")(x_text)

    # 2. Metadata Input & Dense Layer
    meta_input = tf.keras.layers.Input(shape=(n_meta_features,), dtype=tf.float32, name="meta_input")
    x_meta = tf.keras.layers.Dense(24, activation="relu", name="meta_dense")(meta_input)
    x_meta = tf.keras.layers.Dropout(0.2, name="meta_dropout")(x_meta)

    # 3. Fusion Head
    fused = tf.keras.layers.concatenate([x_text, x_meta], name="fusion_concat")
    x = tf.keras.layers.Dense(32, activation="relu", name="fused_dense")(fused)
    x = tf.keras.layers.Dropout(0.3, name="fused_dropout")(x)
    output = tf.keras.layers.Dense(1, activation="sigmoid", name="fraud_score")(x)

    model = tf.keras.Model(inputs=[text_input, meta_input], outputs=output, name="CommentFraudDetectorNN")
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss=tf.keras.losses.BinaryCrossentropy(),
        metrics=[
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.AUC(name="roc_auc", curve="ROC"),
            tf.keras.metrics.AUC(name="pr_auc", curve="PR")
        ]
    )
    return model


def make_dataset(texts, meta, labels=None, batch_size=64, is_train=False):
    """
    Creates an optimized tf.data.Dataset from numpy arrays / tensors.
    """
    inputs = {
        "text_input": tf.constant(texts, dtype=tf.string),
        "meta_input": tf.constant(meta, dtype=tf.float32)
    }
    if labels is not None:
        ds = tf.data.Dataset.from_tensor_slices((inputs, tf.constant(labels, dtype=tf.float32)))
        if is_train:
            ds = ds.shuffle(buffer_size=len(texts), seed=SEED)
        ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    else:
        ds = tf.data.Dataset.from_tensor_slices(inputs).batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds


def train_neural_network():
    print("[Neural Network] Loading datasets...")
    train_df, val_df, test_df = load_data()
    os.makedirs(MODELS_DIR, exist_ok=True)

    y_train = train_df["label"].values.astype(np.float32)
    y_val = val_df["label"].values.astype(np.float32)
    y_test = test_df["label"].values.astype(np.float32)

    X_train_text = train_df["cleaned_text"].values
    X_val_text = val_df["cleaned_text"].values
    X_test_text = test_df["cleaned_text"].values

    X_train_meta = train_df[SCALED_META_COLS].values.astype(np.float32)
    X_val_meta = val_df[SCALED_META_COLS].values.astype(np.float32)
    X_test_meta = test_df[SCALED_META_COLS].values.astype(np.float32)

    print(f"[Neural Network] Samples -> Train: {len(y_train)}, Val: {len(y_val)}, Test: {len(y_test)}")
    print(f"[Neural Network] Metadata feature count: {X_train_meta.shape[1]}")

    # Initialize TextVectorization
    print("[Neural Network] Fitting TextVectorization on training corpus...")
    vocab_size = 5000
    vectorizer = tf.keras.layers.TextVectorization(
        max_tokens=vocab_size,
        output_sequence_length=80,
        name="text_vectorizer"
    )
    vectorizer.adapt(tf.constant(X_train_text, dtype=tf.string))

    # Build model
    print("[Neural Network] Building Multi-Input BiLSTM + Metadata MLP Architecture...")
    model = build_multi_input_model(
        vectorizer=vectorizer,
        n_meta_features=len(SCALED_META_COLS),
        vocab_size=vocab_size
    )

    # Compute balanced class weights
    classes = np.array([0, 1])
    cw = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight_dict = {0: float(cw[0]), 1: float(cw[1])}
    print(f"[Neural Network] Balanced class weights: {class_weight_dict}")

    # Build tf.data datasets
    train_ds = make_dataset(X_train_text, X_train_meta, y_train, batch_size=64, is_train=True)
    val_ds = make_dataset(X_val_text, X_val_meta, y_val, batch_size=64, is_train=False)
    test_ds = make_dataset(X_test_text, X_test_meta, y_test, batch_size=64, is_train=False)

    # Callbacks
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_pr_auc",
            mode="max",
            patience=5,
            restore_best_weights=True,
            verbose=1
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=1e-5,
            verbose=1
        )
    ]

    # Train model
    print("[Neural Network] Training model for up to 15 epochs (CPU)...")
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=15,
        class_weight=class_weight_dict,
        callbacks=callbacks,
        verbose=1
    )

    # Persist model
    model.save(NN_MODEL_PATH)
    print(f"[Neural Network] Successfully persisted trained model to {NN_MODEL_PATH}")

    # Test Set Evaluation
    print("\n[Neural Network] Evaluating on unseen Test Set...")
    eval_ds = make_dataset(X_test_text, X_test_meta, batch_size=64, is_train=False)
    y_pred_proba = model.predict(eval_ds, verbose=0).ravel()
    y_pred = (y_pred_proba >= 0.50).astype(int)

    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    pr_auc = average_precision_score(y_test, y_pred_proba)
    acc = accuracy_score(y_test, y_pred)

    print("\n--- Neural Network Test Performance (Threshold = 0.50) ---")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"ROC-AUC:   {roc_auc:.4f}")
    print(f"PR-AUC:    {pr_auc:.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred, digits=4))

    return {
        "model": model,
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
    train_neural_network()
