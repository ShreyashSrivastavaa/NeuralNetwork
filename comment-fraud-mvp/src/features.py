"""
features.py: Feature Engineering and Dataset Splitting Module.

Extracts rich linguistic, behavioral, and metadata features:
- URL count
- Text length & word count
- Exclamation and question mark ratios
- Uppercase letter ratio
- Duplicate text frequency
- Comments per user per hour (burst velocity)
- Share of 5-star ratings per user
- Post rating deviation

Strictly adheres to ML best practices:
- Stratified train / validation / test split (70 / 15 / 15) with fixed seed (42).
- StandardScaler is fit ONLY on the training split and applied to val/test splits.
"""

import os
import re
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "cleaned_comments.csv")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
SCALER_PATH = os.path.join(MODELS_DIR, "feature_scaler.joblib")

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


def extract_raw_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all metadata and behavioral features from raw and cleaned comments.
    """
    df = df.copy()
    
    # 1. URL Count in raw text
    url_pattern = re.compile(r"https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.(?:com|org|net|io|me|ly|cc|online|xyz)\S*", re.IGNORECASE)
    df["url_count"] = df["text"].apply(lambda t: len(url_pattern.findall(str(t))))

    # 2. Text Length and Word Count
    df["text_length"] = df["text"].apply(lambda t: len(str(t)))
    df["word_count"] = df["text"].apply(lambda t: len(str(t).split()))

    # 3. Uppercase Ratio (uppercase letters / total alphabet characters)
    def get_uppercase_ratio(t: str) -> float:
        s = str(t)
        alpha_count = sum(1 for c in s if c.isalpha())
        if alpha_count == 0:
            return 0.0
        return sum(1 for c in s if c.isupper()) / alpha_count
    df["uppercase_ratio"] = df["text"].apply(get_uppercase_ratio)

    # 4. Punctuation Ratios
    df["exclamation_ratio"] = df["text"].apply(lambda t: str(t).count("!") / max(len(str(t)), 1))
    df["question_ratio"] = df["text"].apply(lambda t: str(t).count("?") / max(len(str(t)), 1))

    # 5. Duplicate text frequency (count of identical cleaned text occurrences)
    text_counts = df["cleaned_text"].value_counts()
    df["duplicate_text_count"] = df["cleaned_text"].map(text_counts).fillna(1).astype(int)

    # 6. Comments per user per hour (Burst Velocity)
    # Parse ISO timestamps
    df["dt"] = pd.to_datetime(df["timestamp"])
    
    # Sort temporarily by user and dt
    sorted_df = df.sort_values(by=["user_id", "dt"]).reset_index()
    
    # For each comment, compute count of comments by same user within 1 hour [dt - 1h, dt]
    user_bursts = []
    for uid, user_group in sorted_df.groupby("user_id"):
        times = user_group["dt"].values
        for t in times:
            t_dt = pd.to_datetime(t)
            # Count comments within 1 hour prior or contemporaneous
            count_in_hour = np.sum((times >= (t_dt - pd.Timedelta(hours=1)).to_datetime64()) & (times <= t))
            user_bursts.append(int(count_in_hour))
            
    sorted_df["comments_per_user_per_hour"] = user_bursts
    # Restore original ordering
    df = sorted_df.sort_values("index").drop(columns=["index"])

    # 7. Share of 5-star ratings per user
    user_5star_share = df.groupby("user_id")["rating"].apply(lambda s: (s == 5).mean())
    df["user_five_star_share"] = df["user_id"].map(user_5star_share).fillna(0.0)

    # 8. Post rating deviation
    post_avg_rating = df.groupby("post_id")["rating"].mean()
    df["rating_deviation"] = (df["rating"] - df["post_id"].map(post_avg_rating)).abs().fillna(0.0)

    return df


def engineer_and_split_features():
    """
    Loads cleaned data, computes features, performs stratified 70/15/15 train/val/test split,
    fits StandardScaler on train metadata features only, transforms val/test,
    and persists all datasets and the scaler.
    """
    print("[Features] Extracting features from cleaned comments...")
    df = pd.read_csv(PROCESSED_DATA_PATH)
    featured_df = extract_raw_features(df)

    # Stratified Split: 70% Train, 30% Temporary (15% Val, 15% Test)
    print("[Features] Performing stratified 70/15/15 train/val/test split (seed=42)...")
    train_df, temp_df = train_test_split(
        featured_df,
        test_size=0.30,
        random_state=42,
        stratify=featured_df["label"]
    )
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        random_state=42,
        stratify=temp_df["label"]
    )

    print(f"[Features] Splits created: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

    # Fit scaler on training set metadata features only (No Data Leakage!)
    print("[Features] Fitting StandardScaler on training metadata features...")
    scaler = StandardScaler()
    scaler.fit(train_df[METADATA_FEATURE_COLS])
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(scaler, SCALER_PATH)
    print(f"[Features] Saved feature scaler to {SCALER_PATH}")

    # Add scaled feature columns for modeling
    scaled_col_names = [f"scaled_{c}" for c in METADATA_FEATURE_COLS]
    
    train_df = train_df.copy()
    val_df = val_df.copy()
    test_df = test_df.copy()
    featured_df = featured_df.copy()

    train_df[scaled_col_names] = scaler.transform(train_df[METADATA_FEATURE_COLS])
    val_df[scaled_col_names] = scaler.transform(val_df[METADATA_FEATURE_COLS])
    test_df[scaled_col_names] = scaler.transform(test_df[METADATA_FEATURE_COLS])
    featured_df[scaled_col_names] = scaler.transform(featured_df[METADATA_FEATURE_COLS])

    # Save to disk
    train_path = os.path.join(PROJECT_ROOT, "data", "processed", "train_features.csv")
    val_path = os.path.join(PROJECT_ROOT, "data", "processed", "val_features.csv")
    test_path = os.path.join(PROJECT_ROOT, "data", "processed", "test_features.csv")
    all_path = os.path.join(PROJECT_ROOT, "data", "processed", "all_features.csv")

    train_df.to_csv(train_path, index=False, encoding="utf-8")
    val_df.to_csv(val_path, index=False, encoding="utf-8")
    test_df.to_csv(test_path, index=False, encoding="utf-8")
    featured_df.to_csv(all_path, index=False, encoding="utf-8")

    print(f"[Features] Saved train features to {train_path}")
    print(f"[Features] Saved val features to {val_path}")
    print(f"[Features] Saved test features to {test_path}")
    print(f"[Features] Saved all features to {all_path}")
    return train_df, val_df, test_df, featured_df


if __name__ == "__main__":
    engineer_and_split_features()

