"""
data_prep.py: Data Generation, Ingestion, and Cleaning Module.

Generates or ingests a realistic dataset of comments (~5,000 comments, ~15% fraud rate)
with rich metadata (comment_id, user_id, text, timestamp, post_id, rating, label).
Features realistic edge cases (genuine comments with links/shouting/bursts, subtle fraud without URLs)
to ensure realistic decision boundaries and prevent trivial separability.
"""

import os
import re
import random
import datetime
import pandas as pd
import numpy as np

# Set deterministic random seed
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "raw_comments.csv")
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "cleaned_comments.csv")


def clean_text(raw_text: str) -> str:
    """
    Cleans raw text for NLP models:
    - Extracts href links from HTML anchors so links inside tags are preserved
    - Strips remaining HTML tags
    - Replaces URLs with placeholder token '_URL_'
    - Lowercases text
    - Normalizes punctuation and excessive whitespace
    """
    if pd.isna(raw_text) or not isinstance(raw_text, str):
        return ""
    
    # Extract href URLs before stripping HTML tags so anchor links are not lost
    text = re.sub(r'<a\s+(?:[^>]*?\s+)?href=[\'"]([^\'"]+)[\'"]', r' \1 ', raw_text, flags=re.IGNORECASE)

    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    
    # Replace URLs with normalized token
    url_pattern = r"(https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.(?:com|org|net|io|me|ly|cc|online|xyz)\S*)"
    text = re.sub(url_pattern, " _URL_ ", text, flags=re.IGNORECASE)
    
    # Lowercase
    text = text.lower()
    
    # Normalize excessive punctuation
    text = re.sub(r"!{2,}", " !! ", text)
    text = re.sub(r"\?{2,}", " ?? ", text)
    
    # Strip obscure non-ascii characters
    text = re.sub(r"[^\w\s.,!?'_-]", " ", text)
    
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_realistic_dataset(n_samples: int = 5000, fraud_ratio: float = 0.15) -> pd.DataFrame:
    """
    Generates a realistic dataset simulating real-world comment fraud challenges:
    - Genuine comments include organic links (GitHub, Wiki, Docs, YouTube), genuine shouting,
      conversational bursts, and short repeated phrases.
    - Fraud comments include link-less scams, social engineering promos, bot duplicates,
      burst spamming, and deceptive reviews.
    """
    n_fraud = int(n_samples * fraud_ratio)
    n_genuine = n_samples - n_fraud

    genuine_sentences = [
        "I've been using this for a couple weeks now and it really exceeded my expectations in terms of battery life and responsiveness.",
        "Honestly, it worked well right out of the box without any complicated configuration.",
        "Great video and analysis! Could you clarify what you meant around the 4 minute mark regarding the database configuration?",
        "Had a question about the setup: does this support python 3.11 or do we need to downgrade to 3.10?",
        "Really helpful guide, thanks for sharing all the sample code snippets in the description.",
        "To be fair, the build quality is impressive, though customer support took 48 hours to answer my ticket.",
        "My experience has been pretty mixed because the desktop app works great but the mobile sync is occasionally sluggish.",
        "Thanks for putting this together! Found the official documentation at https://docs.python.org/3/library/index.html very clear.",
        "Just received my order today, packaging was sturdy and everything arrived without any damage.",
        "Not sure why everyone is complaining, for me it delivered exactly what was advertised.",
        "After trying several alternatives, this one offers the best balance of price and performance for daily office work.",
        "Quick update after 30 days of daily use: still running smoothly with zero crashes.",
        "Does anyone know if this works with external monitors over USB-C? Appreciate any guidance.",
        "Solid performance overall, definitely worth the money in my opinion.",
        "A bit disappointed with the lack of dark mode support in the current release, but functionality is sound.",
        "The latest update fixed most of the minor audio synchronization bugs on Windows 11.",
        "Shipping took a bit longer than expected, but the product itself is high quality.",
        "I had similar issues until I checked the official repo at https://github.com/project/releases for the hotfix.",
        "YESSS FINALLY!! I HAVE BEEN WAITING FOR THIS UPDATE FOR MONTHS!!! AMAZING WORK TEAM!",
        "Thanks! Helpful as always.",
        "Agreed 100%.",
        "Interesting perspective, though I reached a different conclusion when testing under heavy load.",
        "Check out the benchmark comparison at https://en.wikipedia.org/wiki/Benchmark_(computing) for reference."
    ]

    # Fraudulent templates
    promo_domains = ["t.me/crypto_king7", "bit.ly/cashfast365", "wa.me/192837465", "profit-daily.online",
                     "claim-bonus24.xyz", "giftcard-rewards.co", "t.me/invest_fx_expert", "freeprize.cc"]

    fraud_templates = [
        # Classic link scams
        "AMAZING TRADING BOT! I made $14,500 in just 3 days using Mrs. Amanda's strategy! Contact her on WhatsApp now: {url} Don't miss this opportunity!",
        "INVESTMENT OPPORTUNITY: Earn 300% guaranteed weekly returns on Bitcoin and Ethereum. Zero risk! Telegram: {url} !! 100% Legit!",
        "CLICK HERE TO CLAIM YOUR $500 AMAZON GIFT CARD INSTANTLY >>> {url} <<< HURRY LIMITED SLOTS REMAINING!!",
        "CHECK OUT MY PROFILE FOR 70% OFF COUPON CODES FOR ALL MAJOR BRANDS! Visit {url} to save big today!!",
        "Work from home and earn $500-$1000 daily with just a smartphone! Verified payout proof at {url} Contact immediately!",
        "BEST PRODUCT EVER! 100% SATISFIED 5 STARS BUY IT NOW BEST DEAL EVER DO NOT HESITATE AAA+++ {url}",
        "DON'T WASTE MONEY HERE!! Check the real genuine solution at {url} 100x better quality and half the price!",
        "URGENT: WINNER SELECTED! You have been randomly chosen for our VIP reward. Message our coordinator at {url} within 24 hours!",
        # Link-less text scams (challenging edge cases!)
        "Send me a DM on telegram @expert_trader_robert if you want to recover lost funds or double your wallet balance safely.",
        "I was struggling financially until I met manager David on WhatsApp plus one nine one seven four eight two. Reach out to him!",
        "Earn passive income from home guaranteed fifty dollars per hour no experience required pm me for details right now.",
        "DONT BUY FROM THIS SELLER! THEY ARE THIEVES AND SCAMMERS GO TO MY INSTAGRAM BIO TO BUY REAL AUTHENTIC VERSION",
        "Selling brand new sealed items at ninety percent clearance discount send direct message on chat to purchase today only",
        "My account manager helped me withdraw ten thousand dollars within two hours text INVEST to my inbox to get started"
    ]

    n_users = 1100
    all_users = [f"U_{i:04d}" for i in range(1, n_users + 1)]
    posts = [f"P_{i:03d}" for i in range(1, 101)]

    records = []
    base_date = datetime.datetime(2026, 8, 1, 9, 0, 0)
    
    # Select subset of users as syndicate spammers, but also some normal users get compromised
    spammer_users = all_users[:80]
    normal_users = all_users[80:]

    # 1. Generate Genuine Comments
    for i in range(n_genuine):
        cid = f"C_{i+1:05d}"
        uid = random.choice(normal_users)
        pid = random.choice(posts)
        
        # Rating: natural distribution centered around 4
        rating = int(np.random.choice([1, 2, 3, 4, 5], p=[0.07, 0.11, 0.22, 0.36, 0.24]))
        
        # Realistic timestamp
        day_offset = random.uniform(0, 60)
        hour_offset = random.uniform(0, 24)
        c_time = base_date + datetime.timedelta(days=day_offset, hours=hour_offset)
        
        # Text selection
        text = random.choice(genuine_sentences)
        # Add slight organic variations
        if random.random() < 0.2:
            text = text + f" (tested on post {pid})"

        records.append({
            "comment_id": cid,
            "user_id": uid,
            "text": text,
            "timestamp": c_time.isoformat(timespec="seconds") + "Z",
            "post_id": pid,
            "rating": rating,
            "label": 0
        })

    # 2. Generate Fraud Comments
    for j in range(n_fraud):
        cid = f"C_{n_genuine + j + 1:05d}"
        # 85% spammers, 15% compromised normal users
        uid = random.choice(spammer_users) if random.random() < 0.85 else random.choice(normal_users)
        pid = random.choice(posts)
        
        template = random.choice(fraud_templates)
        if "{url}" in template:
            text = template.format(url=random.choice(promo_domains))
        else:
            text = template
            
        # Rating: mostly 5 (astroturf) or 1 (smear), but occasionally 3/4 to blend in
        rating = int(np.random.choice([1, 3, 4, 5], p=[0.20, 0.05, 0.10, 0.65]))
        
        # Timestamps: often bursty, but some casual
        if uid in spammer_users:
            bot_idx = int(uid.split("_")[1]) % 50
            burst_hour = random.choice([9, 13, 19, 23])
            minute_offset = random.uniform(0, 45)
            c_time = base_date + datetime.timedelta(days=bot_idx, hours=burst_hour, minutes=minute_offset)
        else:
            day_offset = random.uniform(0, 60)
            hour_offset = random.uniform(0, 24)
            c_time = base_date + datetime.timedelta(days=day_offset, hours=hour_offset)

        records.append({
            "comment_id": cid,
            "user_id": uid,
            "text": text,
            "timestamp": c_time.isoformat(timespec="seconds") + "Z",
            "post_id": pid,
            "rating": rating,
            "label": 1
        })

    df = pd.DataFrame(records)
    # Shuffle dataset
    df = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    return df


def prepare_data():
    """
    Main orchestration function for data preparation.
    Generates or loads data, cleans text, validates schema, and writes CSVs.
    """
    print("[Data Prep] Initializing Data Pipeline...")
    os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(PROCESSED_DATA_PATH), exist_ok=True)

    print(f"[Data Prep] Generating realistic dataset with 5,000 comments (~15% fraud)...")
    raw_df = generate_realistic_dataset(n_samples=5000, fraud_ratio=0.15)
    raw_df.to_csv(RAW_DATA_PATH, index=False, encoding="utf-8")
    print(f"[Data Prep] Saved raw dataset to {RAW_DATA_PATH} ({len(raw_df)} rows)")

    # Clean text
    print("[Data Prep] Applying text cleaning and URL normalization...")
    processed_df = raw_df.copy()
    processed_df["cleaned_text"] = processed_df["text"].apply(clean_text)

    # Validate no missing values
    processed_df["rating"] = processed_df["rating"].fillna(3).astype(int)
    processed_df["label"] = processed_df["label"].fillna(0).astype(int)
    processed_df["cleaned_text"] = processed_df["cleaned_text"].fillna("")

    # Save cleaned data
    processed_df.to_csv(PROCESSED_DATA_PATH, index=False, encoding="utf-8")
    
    fraud_count = processed_df["label"].sum()
    total_count = len(processed_df)
    print(f"[Data Prep] Processed {total_count} comments successfully.")
    print(f"[Data Prep] Genuine: {total_count - fraud_count} ({(total_count - fraud_count)/total_count:.1%}) | Fraud: {fraud_count} ({fraud_count/total_count:.1%})")
    print(f"[Data Prep] Saved cleaned dataset to {PROCESSED_DATA_PATH}")
    return processed_df


if __name__ == "__main__":
    prepare_data()
