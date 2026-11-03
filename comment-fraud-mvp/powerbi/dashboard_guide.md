# Power BI Dashboard Implementation Guide: Comment Fraud Detection MVP

This guide provides complete, click-by-click instructions to build a 4-page interactive executive and operational dashboard in Power BI Desktop, connect data, configure data types, and establish automated scheduled refresh.

---

## Part 1: Get Data & Data Model Setup

### Step 1: Ingest CSV Files
1. Open **Power BI Desktop**.
2. Click **Home** > **Get Data** > **Text/CSV**.
3. Navigate to `comment-fraud-mvp/outputs/` and select:
   - `scored_comments.csv` $\rightarrow$ Click **Transform Data**.
   - Repeat for `user_summary.csv` and `daily_summary.csv`.

### Step 2: Configure Column Data Types in Power Query Editor
Ensure each column has the proper type for accurate DAX aggregations and date filtering:

#### Table 1: `ScoredComments`
- `comment_id` $\rightarrow$ **Text**
- `user_id` $\rightarrow$ **Text**
- `text` $\rightarrow$ **Text**
- `timestamp` $\rightarrow$ **Date/Time** (ISO 8601 automatically detected)
- `post_id` $\rightarrow$ **Text**
- `rating` $\rightarrow$ **Whole Number**
- `label` $\rightarrow$ **Whole Number** (0 or 1)
- `fraud_score` $\rightarrow$ **Decimal Number**
- `predicted_label` $\rightarrow$ **Whole Number** (0 or 1)
- `risk_band` $\rightarrow$ **Text**
- `top_reason` $\rightarrow$ **Text**

#### Table 2: `UserSummary`
- `user_id` $\rightarrow$ **Text**
- `total_comments` $\rightarrow$ **Whole Number**
- `avg_fraud_score` $\rightarrow$ **Decimal Number**
- `flagged_count` $\rightarrow$ **Whole Number**
- `flag_rate` $\rightarrow$ **Decimal Number / Percentage**
- `high_risk_count` $\rightarrow$ **Whole Number**
- `first_seen` $\rightarrow$ **Date/Time**
- `last_seen` $\rightarrow$ **Date/Time**

#### Table 3: `DailySummary`
- `date` $\rightarrow$ **Date**
- `total_comments` $\rightarrow$ **Whole Number**
- `flagged_comments` $\rightarrow$ **Whole Number**
- `flag_rate` $\rightarrow$ **Decimal Number / Percentage**
- `avg_fraud_score` $\rightarrow$ **Decimal Number**
- `high_risk_comments` $\rightarrow$ **Whole Number**

Click **Home** > **Close & Apply**.

### Step 3: Relationships (Model View)
1. Click the **Model View** icon on the left navigation bar.
2. Verify / Create relationships:
   - `UserSummary[user_id]` (1) $\longleftrightarrow$ `ScoredComments[user_id]` (*) [Single direction]
3. Create a dedicated **Measures Table**:
   - On the Home tab, click **Enter Data**. Name the table `_Measures` and click Load.
   - Add all DAX measures from `powerbi/dax_measures.md` inside this table for clean organization.

---

## Part 2: Building the 4 Dashboard Pages

---

### Page 1: Overview (Executive Command Center)

**Goal**: Deliver instant situational awareness of incoming comment volume, fraud prevalence, and risk trajectory.

#### 1. Header & Filters
- **Title**: "Comment Fraud Detection — Executive Overview"
- **Slicers (Top Ribbon)**:
  - Date Range Slicer (`ScoredComments[timestamp]`, Between style).
  - Risk Band Slicer (`ScoredComments[risk_band]`, Horizontal/Tile button style).

#### 2. Top KPI Cards (Multi-Row Card or New Card Visual)
Place 5 KPI Cards across the top:
1. **Total Comments**: Measure `[Total Comments]`
2. **Flagged Comments**: Measure `[Flagged Comments]`
3. **Flag Rate**: Measure `[Flag Rate]` (Conditional formatting: Red text if $> 15\%$, Amber if $> 10\%$, Green otherwise)
4. **Average Fraud Score**: Measure `[Avg Fraud Score]`
5. **Suspicious Users**: Measure `[Suspicious Users]`

#### 3. Main Trend Chart (Line Chart)
- **Visual**: Line Chart
- **X-Axis**: `DailySummary[date]` (or `ScoredComments[timestamp]` hierarchically at Date level)
- **Y-Axis**: `[Flag Rate]`
- **Secondary Y-Axis**: `[Total Comments]` (Column or Area)
- **Insight**: Displays volume spikes alongside fraud rate surges.

#### 4. Supporting Visuals
- **Donut Chart**: Risk Band Distribution
  - **Legend**: `ScoredComments[risk_band]`
  - **Values**: `[Total Comments]`
  - **Colors**: High = Coral Red (`#D9381E`), Medium = Amber Orange (`#E5A100`), Low = Forest Green (`#2E7D32`).
- **Bar Chart**: Top Fraud Reasons
  - **Y-Axis**: `ScoredComments[top_reason]`
  - **X-Axis**: `[Flagged Comments]`
  - Filter out "Genuine/Low Risk".

---

### Page 2: Risk Triage (Content Moderation Queue)

**Goal**: Empower trust & safety moderators to triage High-risk items, review suspicious texts, and drill into user behavioral history.

#### 1. Page Header & Action Controls
- **Title**: "Moderator Triage Queue — High & Medium Risk"
- **Filters**:
  - Filter on this page: `ScoredComments[risk_band]` is "High" or "Medium".
  - Slicer for `top_reason` ("Contains Promotional URL", "Burst Posting Pattern", etc.).

#### 2. Priority Moderation Table
- **Visual**: Table or Matrix visual
- **Columns**:
  1. `timestamp` (Sorted descending)
  2. `risk_band` (Conditional background color: Red for High, Yellow for Medium)
  3. `fraud_score` (Format: `0.0000`, Data Bars enabled)
  4. `top_reason`
  5. `user_id`
  6. `post_id`
  7. `rating`
  8. `text` (Allow text wrapping for full visibility)
- **Settings**: Turn on "URL Icon" or link formatting if URLs are present.

#### 3. Drill-Through Setup (User Detail Target)
1. Add a second tab or sub-panel named **"User Profile Drillthrough"**.
2. Under Visualizations > **Drill-through fields**, drag `ScoredComments[user_id]`.
3. Add visuals to this drill-through page:
   - User summary card: Total comments posted, user lifetime flag rate, first seen vs last seen.
   - User comments history table: All comments ever posted by this user across all posts.
4. **Moderator Workflow**: On Page 2, moderators right-click any row in the triage table $\rightarrow$ **Drill-through** $\rightarrow$ **User Profile Drillthrough** to inspect repeat bot behavior.

---

### Page 3: Users & Posts (Network & Entity Analysis)

**Goal**: Identify syndicated fraud networks, bot farms, and target posts undergoing astroturfing campaigns.

#### 1. Page Header & Metrics
- **Title**: "Entity Anomalies: Spammer Rings & Target Posts"
- **KPIs**: `[Distinct Users]`, `[Suspicious Users]`, `[Distinct Posts]`, `[Posts with High Fraud]`

#### 2. Top Suspicious Users (Table / Scatter Plot)
- **Visual**: Table or Bar Chart
- **Source**: `UserSummary` table
- **Columns**:
  - `user_id`
  - `total_comments`
  - `flagged_count`
  - `flag_rate`
  - `avg_fraud_score`
- **Sort**: Descending by `flagged_count` or `avg_fraud_score`.
- **Scatter Plot Alternative**:
  - **X-Axis**: `total_comments`
  - **Y-Axis**: `avg_fraud_score`
  - **Size**: `flagged_count`
  - **Details**: `user_id`
  - *Identifies extreme outliers (high volume + high spam score).*

#### 3. Posts with Abnormal Fraud Spikes (Decomposition Tree / Bar Chart)
- **Visual**: Clustered Bar Chart
- **Y-Axis**: `ScoredComments[post_id]`
- **X-Axis**: `[Flagged Comments]`
- **Tooltip**: `[Flag Rate]`, `[Total Comments]`
- **Insight**: Flags specific articles, videos, or products under coordinated review bombing or spam infiltration.

---

### Page 4: Model Performance & What-If Simulation

**Goal**: Model governance and sensitivity analysis. Evaluate precision/recall trade-offs and simulate decision threshold changes in real time.

#### 1. Confusion Matrix (Matrix Visual)
- **Rows**: `ScoredComments[label]` (Ground Truth: 0 = Genuine, 1 = Fraud)
- **Columns**: `ScoredComments[predicted_label]` (Predicted: 0 = Genuine, 1 = Fraud)
- **Values**: `[Total Comments]`
- **Metrics Display Cards**:
  - **Precision**: `[Precision]` (e.g. 96.2%)
  - **Recall**: `[Recall]` (e.g. 94.8%)
  - **F1 Score**: `[F1 Score]` (e.g. 0.955)

#### 2. What-If Threshold Parameter Slider
1. Click **Modeling** ribbon tab > **New Parameter** > **Numeric Range**.
2. Configure:
   - Name: `DecisionThreshold`
   - Data type: Decimal number
   - Minimum: `0.00`
   - Maximum: `1.00`
   - Increment: `0.01`
   - Default: `0.50`
   - Check "Add slicer to this page".
3. Add dynamic impact cards side by side:
   - `[Dynamic Flagged Count]`
   - `[Dynamic Flag Rate]`
   - `[Dynamic Precision]`
   - `[Dynamic Recall]`
4. **Interactive Simulation**: Slide threshold from 0.30 to 0.80 to observe how higher conservatism reduces false positives while capturing fewer spammers.

#### 3. Embedded ROC & Precision-Recall Curve Images
- In Power BI Desktop: Click **Insert** > **Image**.
- Select `outputs/pr_curve.png` and `outputs/roc_curve.png`.
- Position alongside the what-if parameter to present the formal offline evaluation curve.

---

## Part 3: Refresh Automation & Enterprise Deployment

### Local Desktop Refresh
- To refresh with updated predictions after retraining:
  Simply click **Home** > **Refresh** in Power BI Desktop. The engine re-reads the updated CSVs in `outputs/` and refreshes all visuals in seconds.

### Automated Scheduled Refresh via Power BI Service & Gateway
1. **Publish**: In Power BI Desktop, click **Home** > **Publish** $\rightarrow$ Select your Power BI Workspace.
2. **On-Premises Data Gateway**:
   - Download and install the **On-premises Data Gateway** (Standard Mode or Personal Mode) on the machine hosting the project folder.
   - Sign in with your Power BI organization credentials.
3. **Configure Dataset Credentials in Power BI Service**:
   - Go to `app.powerbi.com` $\rightarrow$ Your Workspace $\rightarrow$ Datasets $\rightarrow$ Click `...` on `Comment Fraud MVP` $\rightarrow$ **Settings**.
   - Under **Gateway connection**, ensure the local gateway shows status "Running".
   - Under **Data source credentials**, click **Edit Credentials** for each CSV path:
     - Authentication Method: `Windows` or `None` (for local file system).
4. **Schedule Refresh**:
   - Under **Scheduled refresh**, toggle **Keep your data up to date** to `On`.
   - Frequency: Daily or Hourly.
   - Set failure notification email to data administrators.

