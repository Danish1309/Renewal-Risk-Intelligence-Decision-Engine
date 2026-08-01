"""
LLM Extraction for Renewal Risk Intelligence.

Job 1: Structured extraction from CSM notes — pulls entities, sentiment,
churn signals, competitor mentions as structured JSON.

Job 2: Grounded natural-language explanations for at-risk accounts.

Design decisions:
- Non-English content handled via explicit prompt instruction to translate
- Low-confidence extractions logged, not used for scoring
- Cross-validates LLM-extracted account names against entity resolution matches
  (per user requirement #6)
"""

import json
import pandas as pd
from pathlib import Path

from src.llm_client import LLMClient
from src.entity_resolution import parse_csm_notes, get_csm_note_map


CSM_EXTRACTION_PROMPT = """You are analyzing customer success manager (CSM) call notes for a B2B SaaS company. 
Extract structured information from the following note. The note may contain typos, shorthand, non-English text, or informal language.

IMPORTANT RULES:
1. If text is not in English, translate it first, then extract.
2. For sentiment, consider the overall tone toward the product/relationship, not just individual phrases.
3. For churn_signals, only include signals you are confident about. Use the predefined categories below.
4. If you cannot confidently extract a field, set confidence to "low" rather than guessing.
5. Return ONLY valid JSON with no additional text.

Predefined churn signal categories:
- competitor_evaluation: actively evaluating or running POC with a competitor
- competitor_mention: mentioned a competitor by name without active evaluation
- budget_cut: budget reductions or cost pressure mentioned
- champion_loss: key advocate/champion leaving, at risk, or role change
- explicit_churn_threat: directly stated intent to leave or not renew
- downgrade_risk: considering downgrade rather than full renewal
- missed_engagement: missed QBRs, no-shows, unresponsive
- product_frustration: significant product issues or complaints
- compliance_blocker: regulatory/compliance requirement blocking renewal
- migration_to_alternative: building internal alternative or migrating away
- pricing_dispute: unhappy with pricing or requesting significant discount
- relationship_issue: unhappy with CSM relationship or requesting change
- m_and_a_risk: merger/acquisition creating uncertainty
- executive_involvement: unusual exec involvement (often signals escalation)
- shelfware: product barely used despite being paid for

CSM Note:
---
{note_text}
---

Return a JSON object with these fields:
{{
  "account_name_mentioned": "string or null — the account name as written in the note",
  "account_id_if_stated": "integer or null — account ID if explicitly stated",
  "sentiment": "positive | neutral | negative | mixed",
  "churn_signals": ["list of signal categories from above"],
  "competitor_names": ["list of competitor company names mentioned"],
  "key_quotes": ["up to 3 verbatim quotes that capture the most important signals"],
  "action_items": ["any follow-up actions mentioned or implied"],
  "renewal_status": "at_risk | needs_attention | on_track | expanding | unknown",
  "confidence": "high | medium | low",
  "language_detected": "en | zh | es | fr | mixed",
  "summary": "1-2 sentence summary of the note's key takeaway for a BizOps team"
}}"""


EXPLANATION_PROMPT = """You are generating a brief risk assessment for a B2B SaaS account team.

CRITICAL RULES:
1. Every claim in your explanation MUST reference a specific data point from the signals below.
2. Do NOT infer or speculate beyond what the data shows.
3. If signals contradict each other, explicitly call out the contradiction.
4. End with ONE specific, actionable recommendation.
5. Keep it to 3-5 sentences.

Account: {account_name} (ID: {account_id})
ARR: ${arr:,}
Contract End Date: {contract_end_date}
Days to Renewal: {days_to_renewal}
Plan Tier: {plan_tier}
Industry: {industry}
Region: {region}

=== USAGE SIGNALS ===
API Calls Trend (6 months): {api_calls_trend_pct}% per month
Active Users Trend: {active_users_trend_pct}% per month
API Calls (last month): {api_calls_last_month:,}
Active Users (last month): {active_users_last_month}
SDK Version: {sdk_version}
SDK Deprecated: {sdk_deprecated}

=== SUPPORT SIGNALS ===
Total Tickets: {ticket_count}
P1/P2 Tickets: {p1_p2_count}
Open/Escalated: {open_escalated_count}
Has Blocking Issues: {has_blocking_issue}
Has Recurring Issues: {has_recurring_issue}
Ticket Trend: {ticket_trend}

=== NPS SIGNALS ===
NPS Score: {nps_score}
NPS Verbatim: {nps_verbatim}
NPS Contradiction: {nps_contradiction}

=== CSM INTELLIGENCE ===
{csm_summary}

=== RISK ASSESSMENT ===
Composite Risk Score: {risk_score}/100
Risk Tier: {risk_tier}
Contributing Factors: {contributing_factors}
Contradiction Flags: {contradiction_flags}

Generate a plain-English explanation for the account team. Format as JSON:
{{
  "explanation": "3-5 sentence explanation citing specific data points",
  "recommended_action": "one concrete, specific action for the account team",
  "confidence": "high | medium | low"
}}"""


def extract_csm_notes(data_dir: str, output_dir: str) -> pd.DataFrame:
    """
    Extract structured signals from all CSM notes using LLM.
    Cross-validates extracted account info against entity resolution results.
    """
    client = LLMClient(log_dir=output_dir)
    notes = parse_csm_notes(str(Path(data_dir) / 'csm_notes.txt'))
    
    # Load entity resolution results for cross-validation
    er_log = pd.read_csv(Path(output_dir) / 'entity_resolution_log.csv')
    csm_er = er_log[er_log['source'] == 'csm_notes.txt'].reset_index(drop=True)
    
    results = []
    for i, note in enumerate(notes):
        print(f"  Extracting CSM note {i+1}/{len(notes)}...")
        
        messages = [
            {"role": "system", "content": "You are a precise data extraction assistant. Return only valid JSON."},
            {"role": "user", "content": CSM_EXTRACTION_PROMPT.format(note_text=note['raw_text'])},
        ]
        
        response = client.call_json(
            messages=messages,
            job_type='csm_extraction',
            account_id=str(note.get('extracted_id', 'unknown')),
            temperature=0.1,
            max_tokens=1500,
        )
        
        if response and 'parsed' in response:
            extraction = response['parsed']
            extraction['note_index'] = i
            extraction['raw_text'] = note['raw_text']
            extraction['model_used'] = response['model']
            
            # Cross-validate against entity resolution (user requirement #6)
            if i < len(csm_er):
                er_row = csm_er.iloc[i]
                er_matched_id = er_row.get('matched_account_id')
                llm_stated_id = extraction.get('account_id_if_stated')
                llm_name = extraction.get('account_name_mentioned', '')
                
                extraction['er_matched_account_id'] = er_matched_id
                extraction['er_match_type'] = er_row.get('match_type', '')
                
                # Check agreement
                if llm_stated_id and er_matched_id:
                    if int(llm_stated_id) == int(er_matched_id):
                        extraction['cross_validation'] = 'agreement'
                    else:
                        extraction['cross_validation'] = f'DISAGREEMENT: LLM says {llm_stated_id}, ER matched {er_matched_id}'
                elif er_matched_id:
                    extraction['cross_validation'] = 'er_only'
                else:
                    extraction['cross_validation'] = 'unresolved'
            
            results.append(extraction)
        else:
            results.append({
                'note_index': i,
                'raw_text': note['raw_text'],
                'confidence': 'low',
                'error': 'LLM call failed',
                'cross_validation': 'failed',
            })
    
    df = pd.DataFrame(results)
    df.to_csv(Path(output_dir) / 'csm_extractions.csv', index=False)
    
    # Also save as JSON for richer nested data
    with open(Path(output_dir) / 'csm_extractions.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"  Extracted {len(results)} CSM notes")
    agreement = sum(1 for r in results if r.get('cross_validation') == 'agreement')
    disagreement = sum(1 for r in results if 'DISAGREEMENT' in str(r.get('cross_validation', '')))
    print(f"  Cross-validation: {agreement} agreements, {disagreement} disagreements")
    
    return df


def generate_explanations(
    master_df: pd.DataFrame,
    csm_extractions: list[dict],
    output_dir: str,
) -> list[dict]:
    """
    Generate grounded natural-language explanations for at-risk accounts.
    Only processes accounts renewing within the 90-day window.
    """
    client = LLMClient(log_dir=output_dir)
    
    # Build CSM note lookup by account ID
    csm_by_account = {}
    for ext in csm_extractions:
        acct_id = ext.get('er_matched_account_id')
        if acct_id and not pd.isna(acct_id):
            acct_id = int(acct_id)
            if acct_id not in csm_by_account:
                csm_by_account[acct_id] = []
            csm_by_account[acct_id].append(ext)
    
    # Filter to renewal window accounts
    renewal_accounts = master_df[master_df['renewing_in_window']].copy()
    
    explanations = []
    for _, row in renewal_accounts.iterrows():
        acct_id = int(row['account_id'])
        print(f"  Generating explanation for {row['account_name']} ({acct_id})...")
        
        # Build CSM summary from extractions
        csm_entries = csm_by_account.get(acct_id, [])
        if csm_entries:
            csm_parts = []
            for entry in csm_entries:
                sentiment = entry.get('sentiment', 'unknown')
                signals = entry.get('churn_signals', [])
                competitors = entry.get('competitor_names', [])
                summary = entry.get('summary', '')
                csm_parts.append(
                    f"Sentiment: {sentiment}. "
                    f"Signals: {', '.join(signals) if signals else 'none'}. "
                    f"Competitors mentioned: {', '.join(competitors) if competitors else 'none'}. "
                    f"Summary: {summary}"
                )
            csm_summary = '\n'.join(csm_parts)
        else:
            csm_summary = "No CSM notes available for this account."
        
        # Format the prompt with account data
        prompt_data = {
            'account_name': row['account_name'],
            'account_id': acct_id,
            'arr': int(row['arr']),
            'contract_end_date': str(row['contract_end_date'])[:10],
            'days_to_renewal': int(row['days_to_renewal']),
            'plan_tier': row['plan_tier'],
            'industry': row['industry'],
            'region': row['region'],
            'api_calls_trend_pct': row.get('api_calls_trend_pct', 'N/A'),
            'active_users_trend_pct': row.get('active_users_trend_pct', 'N/A'),
            'api_calls_last_month': int(row.get('api_calls_last_month', 0)),
            'active_users_last_month': int(row.get('active_users_last_month', 0)),
            'sdk_version': row.get('sdk_version', 'unknown'),
            'sdk_deprecated': row.get('sdk_deprecated', False),
            'ticket_count': int(row.get('ticket_count', 0)),
            'p1_p2_count': int(row.get('p1_p2_count', 0)),
            'open_escalated_count': int(row.get('open_escalated_count', 0)),
            'has_blocking_issue': row.get('has_blocking_issue', False),
            'has_recurring_issue': row.get('has_recurring_issue', False),
            'ticket_trend': row.get('ticket_trend', 'none'),
            'nps_score': row.get('nps_score', 'N/A'),
            'nps_verbatim': row.get('nps_verbatim', 'N/A'),
            'nps_contradiction': row.get('nps_contradiction', 'None'),
            'csm_summary': csm_summary,
            'risk_score': row.get('risk_score', 'N/A'),
            'risk_tier': row.get('risk_tier', 'N/A'),
            'contributing_factors': row.get('contributing_factors', 'N/A'),
            'contradiction_flags': row.get('contradiction_flags', 'None'),
        }
        
        messages = [
            {"role": "system", "content": "You are a precise business analyst. Every claim must cite a specific data point. Return only valid JSON."},
            {"role": "user", "content": EXPLANATION_PROMPT.format(**prompt_data)},
        ]
        
        response = client.call_json(
            messages=messages,
            job_type='explanation',
            account_id=str(acct_id),
            temperature=0.2,
            max_tokens=1000,
        )
        
        if response and 'parsed' in response:
            explanation = response['parsed']
            explanation['account_id'] = acct_id
            explanation['account_name'] = row['account_name']
            explanation['model_used'] = response['model']
            explanations.append(explanation)
        else:
            explanations.append({
                'account_id': acct_id,
                'account_name': row['account_name'],
                'explanation': 'Unable to generate explanation — LLM call failed.',
                'recommended_action': 'Manual review required.',
                'confidence': 'low',
            })
    
    # Save explanations
    with open(Path(output_dir) / 'account_explanations.json', 'w', encoding='utf-8') as f:
        json.dump(explanations, f, indent=2, ensure_ascii=False)
    
    pd.DataFrame(explanations).to_csv(
        Path(output_dir) / 'account_explanations.csv', index=False
    )
    
    print(f"  Generated {len(explanations)} explanations")
    return explanations


if __name__ == '__main__':
    print("=== CSM Note Extraction ===")
    extract_csm_notes('data/raw', 'data/processed')
