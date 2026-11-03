# Power BI DAX Measures Reference: Comment Fraud Detection MVP

This document contains production-ready, copy-and-paste DAX measures designed for the Comment Fraud Detection dashboard.

Table Name Assumption in Power BI Data Model:
- **`ScoredComments`** (imported from `outputs/scored_comments.csv`)
- **`UserSummary`** (imported from `outputs/user_summary.csv`)
- **`DailySummary`** (imported from `outputs/daily_summary.csv`)
- **`ThresholdParameter`** (What-if parameter table generated in Power BI: values from 0.00 to 1.00, increment 0.01)

---

## 1. Core Volume & Fraud KPI Measures

### Total Comments
Calculates the total count of comments in the current context.
```dax
Total Comments = 
COUNTROWS('ScoredComments')
```
*Format: Whole Number (`#,##0`)*

### Flagged Comments
Calculates total comments predicted as fraud based on the trained model's decision threshold.
```dax
Flagged Comments = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[predicted_label] = 1
)
```
*Format: Whole Number (`#,##0`)*

### Genuine Comments
Count of comments classified as legitimate.
```dax
Genuine Comments = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[predicted_label] = 0
)
```
*Format: Whole Number (`#,##0`)*

### Flag Rate
The percentage of total comments flagged as fraud/spam.
```dax
Flag Rate = 
DIVIDE(
    [Flagged Comments],
    [Total Comments],
    0
)
```
*Format: Percentage (`0.0%` or `0.00%`)*

### Avg Fraud Score
Mean predictive probability (0.0 to 1.0) produced by the neural network across analyzed comments.
```dax
Avg Fraud Score = 
AVERAGE('ScoredComments'[fraud_score])
```
*Format: Decimal Number (`0.000`)*

---

## 2. Risk Band Segmentation Measures

### High Risk Count
Number of comments with `fraud_score > 0.70`.
```dax
High Risk Count = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[risk_band] = "High"
)
```
*Format: Whole Number (`#,##0`)*

### Medium Risk Count
Number of comments in the borderline/review range (`0.40 <= fraud_score <= 0.70`).
```dax
Medium Risk Count = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[risk_band] = "Medium"
)
```
*Format: Whole Number (`#,##0`)*

### Low Risk Count
Number of comments confidently evaluated as safe (`fraud_score < 0.40`).
```dax
Low Risk Count = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[risk_band] = "Low"
)
```
*Format: Whole Number (`#,##0`)*

### High Risk % of Total
Share of comments falling into the critical triage tier.
```dax
High Risk % = 
DIVIDE(
    [High Risk Count],
    [Total Comments],
    0
)
```
*Format: Percentage (`0.0%`)*

---

## 3. Entity & Behavioral Measures (Users & Posts)

### Distinct Users
Total unique user accounts submitting comments.
```dax
Distinct Users = 
DISTINCTCOUNT('ScoredComments'[user_id])
```
*Format: Whole Number (`#,##0`)*

### Suspicious Users
Count of unique users who have at least one flagged comment in the filtered dataset.
```dax
Suspicious Users = 
CALCULATE(
    DISTINCTCOUNT('ScoredComments'[user_id]),
    'ScoredComments'[predicted_label] = 1
)
```
*Format: Whole Number (`#,##0`)*

### Repeat Offender Ratio
Percentage of unique users who are flagged.
```dax
Suspicious User Rate = 
DIVIDE(
    [Suspicious Users],
    [Distinct Users],
    0
)
```
*Format: Percentage (`0.0%`)*

### Distinct Posts
Total distinct posts or articles receiving comments.
```dax
Distinct Posts = 
DISTINCTCOUNT('ScoredComments'[post_id])
```
*Format: Whole Number (`#,##0`)*

---

## 4. Evaluation & Ground Truth Quality Measures
*(Utilizes ground-truth `label` column in benchmark/test validation data)*

### True Positives (TP)
Fraudulent comments correctly flagged by the model.
```dax
True Positives = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[label] = 1,
    'ScoredComments'[predicted_label] = 1
)
```
*Format: Whole Number (`#,##0`)*

### False Positives (FP)
Genuine comments wrongly flagged as fraud.
```dax
False Positives = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[label] = 0,
    'ScoredComments'[predicted_label] = 1
)
```
*Format: Whole Number (`#,##0`)*

### False Negatives (FN)
Fraudulent comments that slipped past the decision threshold.
```dax
False Negatives = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[label] = 1,
    'ScoredComments'[predicted_label] = 0
)
```
*Format: Whole Number (`#,##0`)*

### True Negatives (TN)
Genuine comments correctly left unflagged.
```dax
True Negatives = 
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[label] = 0,
    'ScoredComments'[predicted_label] = 0
)
```
*Format: Whole Number (`#,##0`)*

### Precision
Fraction of flagged comments that are truly fraudulent: $TP / (TP + FP)$.
```dax
Precision = 
VAR TP = [True Positives]
VAR FP = [False Positives]
RETURN
DIVIDE(TP, TP + FP, 0)
```
*Format: Percentage (`0.0%`)*

### Recall (Sensitivity)
Fraction of actual fraudulent comments detected: $TP / (TP + FN)$.
```dax
Recall = 
VAR TP = [True Positives]
VAR FN = [False Negatives]
RETURN
DIVIDE(TP, TP + FN, 0)
```
*Format: Percentage (`0.0%`)*

### F1 Score
Harmonic mean of precision and recall.
```dax
F1 Score = 
VAR P = [Precision]
VAR R = [Recall]
RETURN
IF(
    (P + R) = 0,
    0,
    2 * DIVIDE(P * R, P + R, 0)
)
```
*Format: Decimal Number (`0.000`)*

---

## 5. Dynamic What-If Threshold Modeling

Create a Power BI Parameter:
Modeling Tab > New Parameter > Numeric Range:
- Name: `DecisionThreshold`
- Min: `0.00`
- Max: `1.00`
- Increment: `0.01`
- Default: `0.50`

### Dynamic Flagged Count
Recalculates flagged count interactively as the user drags the threshold slider.
```dax
Dynamic Flagged Count = 
VAR Cutoff = SELECTEDVALUE('DecisionThreshold'[DecisionThreshold Value], 0.50)
RETURN
CALCULATE(
    COUNTROWS('ScoredComments'),
    'ScoredComments'[fraud_score] >= Cutoff
)
```

### Dynamic Flag Rate
```dax
Dynamic Flag Rate = 
DIVIDE(
    [Dynamic Flagged Count],
    [Total Comments],
    0
)
```

### Dynamic Precision
```dax
Dynamic Precision = 
VAR Cutoff = SELECTEDVALUE('DecisionThreshold'[DecisionThreshold Value], 0.50)
VAR TP = CALCULATE(COUNTROWS('ScoredComments'), 'ScoredComments'[label] = 1, 'ScoredComments'[fraud_score] >= Cutoff)
VAR FP = CALCULATE(COUNTROWS('ScoredComments'), 'ScoredComments'[label] = 0, 'ScoredComments'[fraud_score] >= Cutoff)
RETURN
DIVIDE(TP, TP + FP, 0)
```

### Dynamic Recall
```dax
Dynamic Recall = 
VAR Cutoff = SELECTEDVALUE('DecisionThreshold'[DecisionThreshold Value], 0.50)
VAR TP = CALCULATE(COUNTROWS('ScoredComments'), 'ScoredComments'[label] = 1, 'ScoredComments'[fraud_score] >= Cutoff)
VAR FN = CALCULATE(COUNTROWS('ScoredComments'), 'ScoredComments'[label] = 1, 'ScoredComments'[fraud_score] < Cutoff)
RETURN
DIVIDE(TP, TP + FN, 0)
```

