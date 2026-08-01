# Design Decisions Log

A running log of judgment calls, tradeoffs, and dead ends during development.

---

## Decision 1: Entity Resolution Approach
**Date:** 2026-07-31  
**Context:** CSM notes reference accounts by name (sometimes misspelled), by ID (various formats), or both. Names don't always match `accounts.csv`.

**Options considered:**
1. **Strict ID-only matching** — ignore notes without explicit IDs. Simple but loses ~60% of CSM notes.
2. **Fuzzy name matching with rapidfuzz** — normalize names and compute similarity scores. 
3. **LLM-based entity resolution** — use the LLM to match names. Expensive and overkill for 27 notes.

**Decision:** Option 2 — fuzzy matching with confidence tiers.

**Implementation details:**
- Normalization strips legal suffixes (Inc, Ltd, Corp) but preserves descriptive words (Solutions, Industries) that carry matching signal. Initially stripped too many words which caused false negatives.
- Pipe-delimited note headers (`date | name | CSM`) required special parsing logic separate from dash-delimited headers.
- Double-dash separators (`-- name -- csm_name`) needed segment-by-segment evaluation to avoid consuming the account name.
- Trailing bare account IDs in note headers (e.g., "evergreen media 1015") are now captured and used for resolution.
- Body text truncation prevents extracting descriptive sentence fragments as account names.

**Key tradeoff:** Aggressive normalization (stripping more words) increases recall but risks false positives. Conservative normalization keeps precision but may miss some matches. I chose conservative after the "Summit Analytics" false negative taught me that keeping descriptive words helps more than it hurts.

**Known limitation:** The Harbourside Dining / Oakridge Retail case (account 1099) is impossible to resolve by name alone — the CSM note uses a completely wrong name. We rely on the explicit account ID and log the mismatch per policy.

---

## Decision 2: NPS Score/Verbatim Contradiction Handling
**Date:** 2026-07-31  
**Context:** Several accounts have NPS scores that contradict their verbatim comments (e.g., score=2 but "Best headless CMS on the market").

**Options considered:**
1. **Trust the score, ignore the verbatim** — treats verbatims as unreliable.
2. **Trust the verbatim, override the score** — requires sentiment analysis on every verbatim.
3. **Keep both, flag the contradiction** — let the account team investigate.

**Decision:** Option 3 — per user instruction. Both the score and verbatim are preserved. The contradiction is flagged as a visible badge in the UI and mentioned in the LLM explanation. The score is used for risk calculation (since it's the structured signal) but the contradiction flag prevents the system from being overconfident in that signal.

**Rationale:** These contradictions could be data entry errors, survey fatigue, or genuinely complex situations (e.g., a user who loves the product concept but rates it poorly due to a recent bad experience). Only a human can disambiguate.

---

## Decision 3: Risk Score Weights
**Date:** 2026-07-31  
**Context:** The composite risk score needs weights for each signal dimension.

**Weight allocation:**
| Signal | Weight | Rationale |
|--------|--------|-----------|
| Usage Trend | 25% | Strongest leading indicator — declining usage is the most reliable predictor of churn |
| Support Health | 20% | High-severity unresolved tickets indicate active friction |
| Platform Risk | 15% | Product-caused churn risk (deprecated SDKs) that pure engagement metrics miss |
| CSM Sentiment | 15% | Captures qualitative context (competitor evaluations, champion loss) unavailable in structured data |
| NPS Signal | 15% | Lagging indicator — reflects past experience, not current trajectory |
| Contract Proximity | 10% | Urgency multiplier — closer renewals need faster action |

**Key tradeoff:** Platform Risk (15%) is unusually high for a B2B scoring model, but the data shows 8 accounts on deprecated SDKs with significantly worse usage trends. Without this dimension, these accounts would be flagged generically as "declining usage" rather than correctly identified as "product-caused breakage requiring migration support."

**What I'd change with historical data:** Calibrate weights against actual churn outcomes. The current weights are informed judgments, not trained coefficients.

---

## Decision 4: LLM Model Selection
**Date:** 2026-07-31  
**Context:** Groq offers multiple models. Need one for reasoning-heavy extraction and explanations.

**Models verified available:**
- `openai/gpt-oss-120b` — largest, best for complex extraction
- `openai/gpt-oss-20b` — smaller, faster, cheaper fallback
- `llama-3.3-70b-versatile` — available but user directed to use gpt-oss-20b as fallback instead

**Decision:** Primary: `openai/gpt-oss-120b`, Fallback: `openai/gpt-oss-20b`. Automatic fallback on rate limits or errors.

---

## Decision 5: Reference Date
**Date:** 2026-07-31  
**Context:** Need a "today" for computing 90-day renewal window.

**Decision:** April 15, 2026 — the latest CSM note dates are early April 2026, and usage data runs through March 2026. This gives a realistic window covering May–July 2026 renewals.

**Result:** 30 accounts fall within the 90-day window, representing ~$13M in ARR.

---

## Decision 6: Non-Obvious Insight Approach
**Date:** 2026-07-31  
**Context:** Need to go beyond account-by-account scoring. User specifically requested portfolio-level analysis of SDK deprecation impact, not just restating one CSM note.

**Decision:** Two-pronged analysis:
1. **SDK deprecation portfolio impact** — quantify how many accounts and how much ARR sit on deprecated v3.x SDKs, compare their usage trends to migrated accounts, and show this is product-caused decline masquerading as disengagement.
2. **Trapped usage pattern** — find accounts with stable/growing usage but negative NPS or sentiment contradictions, indicating unhappy users who haven't found an alternative yet.

**Why this matters:** A simple usage-decline rule would flag deprecated SDK accounts as "disengaged" and recommend a generic retention play. The correct response is migration assistance — completely different playbook. This is the kind of insight that requires cross-referencing changelog events with usage data and CSM notes.

---

## Decision 7: Contradiction Detection Thresholds
**Date:** 2026-07-31  
**Context:** When do we flag signal contradictions?

**Decision:** Flag when related signal dimensions differ by >30 risk points. Specific patterns:
- Good NPS (risk<30) + declining usage (risk>60) → "silent churn"
- Bad NPS (risk>60) + strong usage (risk<30) → "trapped users"
- Positive CSM (risk<30) + bad support (risk>60) → "CSM blind spot"
- Negative CSM (risk>60) + good metrics (both<30) → "qualitative concern without quantitative backing"

**Rationale:** 30 points is roughly 1 tier's worth of difference. Smaller gaps are normal noise; larger gaps suggest the account's situation is genuinely complex.

---

## Decision 8: LLM Cross-Validation (User Requirement #6)
**Date:** 2026-07-31  
**Context:** User requested cross-checking the LLM's extracted account_name and account_id against entity resolution results.

**Implementation:** After LLM extraction, compare:
- LLM's `account_id_if_stated` against entity resolution's `matched_account_id`
- Agreement → increases confidence
- Disagreement → flagged for review
- Results logged in `csm_extractions.json` with `cross_validation` field

---

## Dead Ends

### Attempted: Stripping "Solutions", "Industries" from names
Initially included `\bsolutions\b`, `\bindustries\b`, `\bgroup\b` in the legal suffix stripping. This caused "NovaTech Industries" to normalize to "novatech" and "BrightPath Solutions" to "brightpath" — losing signal that helps fuzzy matching. Reverted to only stripping true legal entity suffixes.

### Attempted: First-dash prefix removal for all note formats
Used `re.sub(r'^.*?[-–—]\s*', '', name_line, count=1)` to strip date prefixes. This also consumed the account name in cases like "3/22 summit analytics - routine check-in" where the first dash comes AFTER the name. Fixed by removing dates first, then only stripping leading separators.

---

## Decision 9: Automated Explanation Numerical Validation Engine
**Date:** 2026-07-31  
**Context:** Manual auditing exposed a hallucination/conflation error where Vanguard Retail's explanation stated a "six-week open P1 ticket" (from CSM notes) instead of its ground-truth NPS verbatim ("3 weeks").

**Decision:** Built an automated numerical assertions validation script (`src/validate_explanations.py`).
- Parses every generated explanation across all 30 accounts.
- Extracts all regex numeric claims (ARR, Days to Renewal, Composite Risk Score, NPS Score, Ticket Open Durations).
- Programmatically asserts each claim against raw CSV ground truth (`scored_accounts.csv`, `nps_responses.csv`).
- Fixed Vanguard Retail (1005) and BluePeak Software (1014) assertions.
- Validation script confirmed **0 mismatches** across all 150 numerical assertions.

## Decision 10: Near-Monochrome Dark SaaS Redesign (Efferd / Zentra Aesthetics)
**Date:** 2026-07-31  
**Context:** Needed a high-contrast executive visual aesthetic matching modern dark SaaS decision tools without sacrificing readability or risk scanning.

**Key Choices:**
1. **Restrained Accent Language**: Near-monochrome slate background (`#0b0f19`) with color reserved exclusively for risk status (`#f43f5e` Rose, `#f59e0b` Amber, `#10b981` Emerald).
2. **Rounded-Pill Control Language**: Extended `border-radius: 20px` to inputs, multiselects, dropdowns, and button controls.
3. **Soft Card Elevation**: Replaced hard panels with backdrop-blur glass cards (`backdrop-filter: blur(14px)`), subtle borders (`rgba(255, 255, 255, 0.08)`), and soft 25px shadow drops.
4. **Multilingual Verbatim Support**: Provided English translations inline for all non-English verbatims (Mandarin, Spanish, French) across Roster and Trapped Users views.

---

## Decision 11: Priority Accounts Visualization & Custom KPI Cards
**Date:** 2026-07-31  
**Context:** Per stakeholder preference, restored the high-clarity Plotly horizontal bar chart for "Top 10 Priority Accounts by Risk Score" while preserving executive custom KPI cards.

**Key Choices:**
1. **Plotly Top 10 Bar Chart Restoration**: Restored the original Plotly horizontal bar chart featuring color-coded risk tiers, outside risk score labels, interactive tooltips, and explicit `🚨` Critical Override badges.
2. **Custom KPI Metric Cards**: Preserved custom HTML cards featuring `font-size: 44px` headline numbers, `background: linear-gradient(145deg, #14161f, #0a0b10)`, generous 24px padding, and `.kpi-card:hover` translateY lift.
3. **Inter Global Typography**: Applied Inter font (`font-family: 'Inter', sans-serif`) and `#0a0b10` dark base color across all components.
