"""
run_all.py: End-to-End Orchestrator for Comment Fraud Detection MVP.

Executes all pipeline phases in sequence:
1. data_prep.py        - Dataset generation & text cleaning
2. features.py         - Metadata extraction & stratified splitting
3. train_baseline.py   - TF-IDF + Logistic Regression baseline
4. train_nn.py         - Multi-Input BiLSTM + Metadata Neural Network
5. evaluate.py         - Test evaluation, comparison & diagnostic plots
6. score.py            - Batch scoring, risk banding & Power BI summaries
7. pytest              - Full test suite verification
"""

import os
import sys
import time
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable


def run_step(step_name: str, script_relative_path: str, is_pytest: bool = False):
    print("\n" + "=" * 70)
    print(f"  RUNNING STAGE: {step_name}")
    print("=" * 70)
    start_time = time.time()
    
    if is_pytest:
        cmd = [PYTHON_EXE, "-m", "pytest", os.path.join(PROJECT_ROOT, script_relative_path), "-v"]
    else:
        cmd = [PYTHON_EXE, os.path.join(PROJECT_ROOT, script_relative_path)]
        
    process = subprocess.run(cmd, cwd=PROJECT_ROOT)
    elapsed = time.time() - start_time
    
    if process.returncode != 0:
        print(f"\n[ERROR] Stage '{step_name}' failed with exit code {process.returncode} after {elapsed:.2f}s.")
        sys.exit(process.returncode)
        
    print(f"[SUCCESS] Stage '{step_name}' completed in {elapsed:.2f}s.")
    return elapsed


def main():
    total_start = time.time()
    print("*" * 70)
    print("  COMMENT FRAUD DETECTION MVP — FULL END-TO-END PIPELINE")
    print("*" * 70)

    stages = [
        ("Step 1: Data Preparation & Cleaning", "src/data_prep.py", False),
        ("Step 2: Feature Engineering & Splitting", "src/features.py", False),
        ("Step 3A: Baseline Model Training (TF-IDF + LR)", "src/train_baseline.py", False),
        ("Step 3B: Neural Network Training (BiLSTM + MLP)", "src/train_nn.py", False),
        ("Step 3C & 4A: Evaluation, Thresholding & Diagnostics", "src/evaluate.py", False),
        ("Step 4B: Batch Scoring & Summary Rollups", "src/score.py", False),
        ("Step 5: Interactive Dashboard Preview Generator", "src/build_preview_html.py", False),
        ("Step 6: Automated Test Suite (PyTest)", "tests", True)
    ]

    timings = {}
    for name, path, is_test in stages:
        t = run_step(name, path, is_test)
        timings[name] = t

    total_time = time.time() - total_start
    print("\n" + "*" * 70)
    print("  PIPELINE EXECUTION SUMMARY")
    print("*" * 70)
    for name, t in timings.items():
        print(f"  - {name:<50}: {t:>6.2f}s")
    print("-" * 70)
    print(f"  Total Pipeline Wall Time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
    print("*" * 70)

    # Verify generated deliverables
    outputs_to_verify = [
        "outputs/scored_comments.csv",
        "outputs/user_summary.csv",
        "outputs/daily_summary.csv",
        "outputs/metrics.json",
        "outputs/confusion_matrix.png",
        "outputs/pr_curve.png",
        "outputs/roc_curve.png",
        "models/nn_model.keras",
        "models/baseline_model.joblib"
    ]
    
    print("\n[Verification] Checking generated deliverable files:")
    all_ok = True
    for out_rel in outputs_to_verify:
        full_path = os.path.join(PROJECT_ROOT, out_rel)
        if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
            size_kb = os.path.getsize(full_path) / 1024
            print(f"  [OK] {out_rel:<35} ({size_kb:>8.1f} KB)")
        else:
            print(f"  [MISSING/EMPTY] {out_rel}")
            all_ok = False
            
    if all_ok:
        print("\nAll pipeline deliverables verified successfully!")
    else:
        print("\nWarning: Some deliverables are missing or empty.")
        sys.exit(1)


if __name__ == "__main__":
    main()

