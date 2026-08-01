# Renewal Risk Intelligence & Decision Engine

An executive-grade decision engine built for BizOps stakeholders to identify, evaluate, and mitigate customer churn risk across 30 enterprise software accounts renewing within a 90-day window (**April 15, 2026 – July 14, 2026**).

---

## 1. Executive Summary

This platform consolidates fragmented signals from product usage metrics, support ticket backlogs, NPS survey verbatims, and un-structured CSM meeting notes into a single composite **Renewal Risk Engine**.

Rather than relying on naive rule-based filters that miss cross-channel risk, this tool:
- **Surfaces At-Risk Revenue**: Ranks renewing accounts by composite risk score, isolating **9 High-Risk Accounts representing $2.33M in renewing ARR**.
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
[Raw Files]
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
2. **Step 2 — Composite Risk Engine (`src/risk_engine.py`)**: Computes a normalized 0–100 risk score across 6 weighted dimensions for all 90-day renewal accounts.
3. **Step 3 — LLM Extraction & Grounded Explanations (`src/llm_extractor.py`)**: Calls Groq LLM to extract structured signals (churn drivers, competitor threats, sentiment) and generate grounded remediation recommendations.
4. **Step 4 — Portfolio Insights Generator (`src/insights_generator.py`)**: Runs cross-dataset statistical analysis to extract portfolio-wide non-obvious root causes (e.g. SDK v3.x deprecation drop-off, trapped high-usage users).

---

## 4. How "At-Risk" is Defined: 6-Dimension Weighted Scoring Model

The composite risk score is calculated on a 0–100 scale using the following dimension weights:

| Dimension | Weight | Rationale |
| :--- | :---: | :--- |
| **Usage Trend** | **30%** | Product usage is the leading indicator of value realization. Declining MoM API calls or active user drop-offs directly precede non-renewal. |
| **Support Health** | **25%** | High P1/P2 ticket volume, unresolved open/escalated tickets, and blocking bugs represent immediate execution friction. |
| **CSM Intelligence** | **20%** | Qualitative signals (champion loss, competitor POCs, pricing disputes) capture organizational churn risks invisible to quantitative telemetry. |
| **NPS & Sentiment** | **10%** | Customer advocacy score (detractors vs. promoters) and sentiment alignment. |
| **Platform / Tech Risk** | **10%** | Technical debt risk, specifically deprecated SDK versions (v3.x) facing the April 30 sunset deadline. |
| **Contract Proximity** | **5%** | Urgency multiplier based on days remaining until contract expiration within the 90-day window. |

### Critical Override Rule
If an account exhibits **both** a severe usage drop (>15% MoM decline) AND an open blocking P1 support ticket, its risk tier is automatically overridden to **High Risk**, regardless of composite score.

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
