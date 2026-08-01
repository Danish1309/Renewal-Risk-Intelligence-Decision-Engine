# Renewal Risk Intelligence & Decision Engine

An executive-grade decision engine built for BizOps stakeholders to identify, evaluate, and mitigate customer churn risk across 30 enterprise software accounts renewing within a 90-day window (**April 15, 2026 – July 14, 2026**).

---

## 1. Executive Summary

This platform consolidates fragmented signals from product usage metrics, support ticket backlogs, NPS survey verbatims, and un-structured CSM meeting notes into a single composite **Renewal Risk Engine**.

Rather than relying on naive rule-based filters that miss cross-channel risk, this tool:
- **Surfaces At-Risk Revenue**: Ranks renewing accounts by composite risk score, isolating **11 High-Risk Accounts representing $3.27M in renewing ARR**.
- **Detects Hidden Contradictions**: Identifies accounts with high numerical NPS scores (e.g. 8.0+) whose underlying verbatims or CSM notes report severe product breakdowns (e.g. "execution has fallen off a cliff").
- **Exposes Technical & Platform Vulnerabilities**: Uncovers portfolio-wide exposure to sunsetting legacy SDKs (v3.x) facing an imminent April 30, 2026 deadline.
- **Generates Grounded LLM Action Plans**: Leverages structured LLM extractions (powered by Groq `openai/gpt-oss-120b`) to produce validated, non-hallucinated remediation playbooks for every at-risk account.

---

## 2. How to Run & Demo

### Prerequisites
- Python 3.10+ installed
- Dependencies installed via `requirements.txt`
- `.env` file configured with `GROQ_API_KEY` (OpenAI-compatible endpoint)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run End-to-End ETL & LLM Pipeline
Executes entity resolution, weighted risk scoring, structured LLM extraction, and non-obvious insight generation:
```bash
python -m src.pipeline
```

### Step 3: Run Automated Explanation Validation
Cross-checks all numerical assertions in generated explanations against raw source data:
```bash
python src/validate_explanations.py
```

### Step 4: Launch Web Dashboard
Starts the Streamlit decision engine dashboard:
```bash
streamlit run app.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your browser.

---

## 3. Architecture & Data Flow

```
[data/raw/]
├─ accounts.csv ──────────────┐
├─ usage_metrics.csv ─────────┼─► Step 1: Entity Resolution ──► Step 2: Risk Engine
├─ support_tickets.csv ───────┤   (Fuzzy Match & ID Audit)      (6-Dimension Scoring)
├─ nps_responses.csv ─────────┤                                          │
└─ csm_notes.txt ─────────────┘                                          ▼
                                                               Step 3: LLM Extraction
                                                               (Groq gpt-oss-120b)
                                                                         │
                                                                         ▼
                                                               Step 4: Portfolio Insights
                                                                         │
                                                                         ▼
                                                               Streamlit Dashboard (app.py)
```

1. **Step 1 — Entity Resolution (`src/entity_resolution.py`)**: Normalizes account names, parses complex note headers (`date | name | CSM`), and resolves un-structured CSM notes to canonical `account_id`s with confidence scores.
2. **Step 2 — Composite Risk Engine (`src/risk_scoring.py`)**: Computes a normalized 0–100 risk score across 6 weighted dimensions for all 90-day renewal accounts.
3. **Step 3 — LLM Extraction & Grounded Explanations (`src/llm_extraction.py`)**: Calls Groq LLM to extract structured signals (churn drivers, competitor threats, sentiment) and generate grounded remediation recommendations.
4. **Step 4 — Portfolio Insights Generator (`src/insights.py`)**: Runs cross-dataset statistical analysis to extract portfolio-wide non-obvious root causes (e.g. SDK v3.x deprecation drop-off, trapped high-usage users).

---

## 4. How "At-Risk" is Defined: 6-Dimension Weighted Scoring Model

The composite risk score is calculated on a 0–100 scale using the exact dimension weights defined in [`src/risk_scoring.py`](file:///c:/Users/lenovo/Downloads/renewal_intelligence_takehome%20%20%281%29%20%281%29/renewal_intelligence_takehome/src/risk_scoring.py):

| Dimension | Weight | Rationale & Scoring Logic |
| :--- | :---: | :--- |
| **Usage Trend** | **25%** | Product usage is the primary leading indicator. Combines API call trend (60%) and active user trend (40%). $\le -20\%$ MoM decline maps to 100 risk score. |
| **Support Health** | **20%** | Evaluates P1/P2 ticket volume (40%), open/escalated ratio (30%), overall volume (15%), and blocking/recurring issue flags (15%). |
| **CSM Sentiment** | **15%** | Qualitative sentiment extracted via LLM (Negative = 80, Mixed = 55, Neutral = 35, Positive = 10) boosted by churn signals (competitor evaluation, pricing dispute, etc.). |
| **NPS Signal** | **15%** | Customer advocacy score: Detractors (0–6) map to 60–95 risk score, Passives (7–8) map to 25–40, Promoters (9–10) map to 5–10. |
| **Platform Risk** | **15%** | Technical debt and deprecation risk: Deprecated SDKs (+60 score for v3.x facing April 30 sunset) and unpatched bug versions (+15 for v4.0.0/v4.1.0 missing locale fallback fix). |
| **Contract Proximity** | **10%** | Non-linear urgency multiplier based on remaining days to renewal: $\le 14$ days (90 risk score), $\le 30$ days (70), $\le 60$ days (45), $\le 90$ days (25). |

### Risk Tiers
- **High Risk**: Composite score $\ge 65$ OR Critical Override flag triggered.
- **Medium Risk**: Composite score $\ge 40$ and $< 65$.
- **Low Risk**: Composite score $< 40$.

### Critical Override Rule
If LLM extraction detects any critical qualitative churn signal in CSM meeting notes (`competitor_evaluation`, `explicit_churn_threat`, or `migration_to_alternative`), the account's risk tier is **automatically overridden to High Risk**, regardless of its composite score.

### Low-Confidence & Contradiction Flagging
- **Low Confidence**: Triggered if missing data spans $\ge 2$ dimensions OR if $\ge 2$ cross-signal contradictions exist.
- **Contradiction Detection**: Triggers when related signals disagree by $>30$ points (e.g., high NPS with declining usage, or positive CSM sentiment alongside severe support ticket backlogs).

---

## 5. Tradeoffs & Judgment Calls

1. **NPS / Verbatim Contradictions**: Rather than silently discarding conflicting data, the pipeline flags contradictions (e.g., NPS 8.0 with "execution fell off a cliff"). The account's AI assessment explicitly addresses why sentiment and score diverge.
2. **Entity Resolution Mismatches (Harbourside Dining / Oakridge Retail 1099)**: When a note cited "Harbourside Dining" alongside `account_id: 1099` (which belongs to "Oakridge Retail"), the pipeline trusted the explicit account ID while logging the name discrepancy for auditability.
3. **LLM Extraction Disagreement Flags**: If the LLM extraction's mentioned account name disagrees with the Step 1 entity-resolution match, the system flags the entity resolution for human review rather than silently overriding it.
4. **Non-English Verbatim Translations**: Preserved original raw verbatims (Mandarin, Spanish, French) while presenting human-verified English translations inline across both the Account Roster and Trapped Users views.

---

## 6. What I'd Do With More Time

- **Interactive Scenario Simulator**: Allow BizOps managers to adjust dimension weights dynamically in the UI and recalculate risk tiers in real time.
- **Automated CSM Playbook Triggers**: Integrate Webhooks to automatically push recommended action plans into Slack or Jira when an account enters High Risk tier.
- **Time-Series Usage Sparklines**: Render interactive 6-month historical usage sparklines inside each expanded account card.

---

## 7. Production Readiness Plan

If deploying this solution into production, I would implement:

1. **Live Data Pipeline Integration**: Replace static CSV ingestion with direct, incremental sync connectors from Salesforce (ARR, Renewal Date), Zendesk (Support Tickets), Qualtrics (NPS), and Snowflake (Telemetry).
2. **Continuous LLM Evaluation Harness**: Build an automated test suite using `deepeval` or `ragas` to benchmark LLM extraction accuracy, factual grounding, and latency on every model update.
3. **Observability & Cost Management**: Add OpenTelemetry tracing and token rate-limiting for Groq API calls, caching extractions to reduce LLM costs.
4. **Human-in-the-Loop (HITL) Workflow**: Provide a CS Manager approval UI before any automated remediation plan is emailed to account teams.
