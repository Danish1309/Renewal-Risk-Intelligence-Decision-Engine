"""
Risk Scoring Model for Renewal Risk Intelligence.

Transparent, explainable composite scoring with 6 signal dimensions.
Each dimension is scored 0–100 (higher = riskier), then combined with
configurable weights.

Key design decisions:
- Not a black-box: every score traces to specific signals
- Contradictions between signals are flagged, not averaged away
- Low-confidence scores are marked explicitly
- "Critical override" flags can push accounts to High regardless of composite

See README.md for full rationale on weights and thresholds.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path


# === SCORING WEIGHTS ===
# NOTE: README.md Section 4 documents these weights and the critical override logic.
# Always keep README.md in sync whenever modifying weights, overrides, or tier thresholds.
WEIGHTS = {
    'usage_trend': 0.25,
    'support_health': 0.20,
    'nps_signal': 0.15,
    'csm_sentiment': 0.15,
    'contract_proximity': 0.10,
    'platform_risk': 0.15,
}


def score_usage_trend(row: pd.Series) -> dict:
    """
    Score usage trend (0-100, higher = more at-risk).
    
    Considers: API call trend, active user trend, content creation trend.
    Strong decline → high risk. Growth → low risk.
    """
    api_trend = row.get('api_calls_trend_pct', 0) or 0
    user_trend = row.get('active_users_trend_pct', 0) or 0
    
    # Combine trends (weighted: API calls 60%, active users 40%)
    combined_trend = (api_trend * 0.6) + (user_trend * 0.4)
    
    # Map trend to risk score:
    # -20% or worse per month → 100 (very high risk)
    # -10% per month → 70
    # 0% → 30 (neutral — some base risk for flat usage)
    # +10% or more → 0 (growth = low risk)
    if combined_trend <= -20:
        score = 100
    elif combined_trend <= 0:
        score = 30 + (-combined_trend / 20) * 70
    elif combined_trend <= 10:
        score = 30 - (combined_trend / 10) * 30
    else:
        score = 0
    
    score = max(0, min(100, score))
    
    details = {
        'api_calls_trend_pct': round(api_trend, 1),
        'active_users_trend_pct': round(user_trend, 1),
        'combined_trend_pct': round(combined_trend, 1),
    }
    
    return {'score': round(score, 1), 'details': details}


def score_support_health(row: pd.Series) -> dict:
    """
    Score support ticket health (0-100, higher = more at-risk).
    
    Considers: P1/P2 count, open/escalated ratio, blocking/recurring issues.
    """
    ticket_count = row.get('ticket_count', 0) or 0
    p1_p2 = row.get('p1_p2_count', 0) or 0
    open_esc = row.get('open_escalated_count', 0) or 0
    has_blocking = row.get('has_blocking_issue', False)
    has_recurring = row.get('has_recurring_issue', False)
    
    if ticket_count == 0:
        return {'score': 10, 'details': {'reason': 'No tickets (could be good or disengaged)'}}
    
    # P1/P2 severity component (40% of support score)
    severity_score = min(100, p1_p2 * 15)
    
    # Open/escalated ratio component (30%)
    open_ratio = open_esc / ticket_count if ticket_count > 0 else 0
    open_score = min(100, open_ratio * 150)
    
    # Volume component (15%)
    volume_score = min(100, ticket_count * 8)
    
    # Blocking/recurring flags (15%)
    flag_score = 0
    if has_blocking:
        flag_score += 60
    if has_recurring:
        flag_score += 40
    flag_score = min(100, flag_score)
    
    score = (severity_score * 0.40 + open_score * 0.30 + 
             volume_score * 0.15 + flag_score * 0.15)
    
    details = {
        'ticket_count': ticket_count,
        'p1_p2_count': p1_p2,
        'open_escalated': open_esc,
        'has_blocking': has_blocking,
        'has_recurring': has_recurring,
    }
    
    return {'score': round(min(100, score), 1), 'details': details}


def score_nps_signal(row: pd.Series) -> dict:
    """
    Score NPS signal (0-100, higher = more at-risk).
    
    Detractors (0-6) → high risk. Passives (7-8) → moderate. Promoters (9-10) → low.
    Missing NPS → neutral with low-confidence flag.
    """
    nps_score = row.get('nps_score')
    has_contradiction = row.get('has_nps_contradiction', False)
    
    if pd.isna(nps_score):
        return {
            'score': 40,  # Neutral — absence of signal is mildly concerning
            'details': {'reason': 'No NPS response — data gap', 'low_confidence': True},
        }
    
    nps_score = int(nps_score)
    
    # Map NPS to risk score
    if nps_score <= 2:
        score = 95
    elif nps_score <= 4:
        score = 80
    elif nps_score <= 6:
        score = 60
    elif nps_score <= 7:
        score = 40
    elif nps_score <= 8:
        score = 25
    elif nps_score <= 9:
        score = 10
    else:
        score = 5
    
    details = {
        'nps_score': nps_score,
        'nps_category': 'detractor' if nps_score <= 6 else ('passive' if nps_score <= 8 else 'promoter'),
        'has_contradiction': has_contradiction,
    }
    
    if has_contradiction:
        details['contradiction_note'] = str(row.get('nps_contradiction', ''))
    
    return {'score': round(score, 1), 'details': details}


def score_csm_sentiment(row: pd.Series, csm_data: dict | None) -> dict:
    """
    Score CSM sentiment (0-100, higher = more at-risk).
    
    Uses LLM-extracted signals from CSM notes.
    No CSM data → neutral with low-confidence flag.
    """
    if not csm_data:
        return {
            'score': 35,
            'details': {'reason': 'No CSM notes available', 'low_confidence': True},
        }
    
    # Base score from sentiment
    sentiment = csm_data.get('sentiment', 'unknown')
    sentiment_scores = {
        'positive': 10,
        'neutral': 35,
        'mixed': 55,
        'negative': 80,
        'unknown': 40,
    }
    score = sentiment_scores.get(sentiment, 40)
    
    # Boost for churn signals
    churn_signals = csm_data.get('churn_signals', [])
    critical_signals = [
        'competitor_evaluation', 'explicit_churn_threat',
        'migration_to_alternative', 'champion_loss',
    ]
    moderate_signals = [
        'budget_cut', 'pricing_dispute', 'downgrade_risk',
        'missed_engagement', 'executive_involvement',
        'compliance_blocker', 'm_and_a_risk',
    ]
    
    for signal in churn_signals:
        if signal in critical_signals:
            score += 20
        elif signal in moderate_signals:
            score += 10
        else:
            score += 5
    
    score = min(100, score)
    
    details = {
        'sentiment': sentiment,
        'churn_signals': churn_signals,
        'competitor_names': csm_data.get('competitor_names', []),
        'renewal_status': csm_data.get('renewal_status', 'unknown'),
    }
    
    return {'score': round(score, 1), 'details': details}


def score_contract_proximity(row: pd.Series) -> dict:
    """
    Score based on how close the renewal is (0-100).
    
    Closer renewals are more urgent, amplifying other risks.
    """
    days = row.get('days_to_renewal', 90)
    if pd.isna(days):
        days = 90
    days = int(days)
    
    # Non-linear: urgency increases sharply as renewal approaches
    if days <= 14:
        score = 90
    elif days <= 30:
        score = 70
    elif days <= 60:
        score = 45
    elif days <= 90:
        score = 25
    else:
        score = 10
    
    return {'score': score, 'details': {'days_to_renewal': days}}


def score_platform_risk(row: pd.Series) -> dict:
    """
    Score platform-related risk (0-100).
    
    Accounts on deprecated SDKs, missed breaking changes, or legacy
    dependencies face product-caused churn risk that pure engagement
    metrics would miss.
    """
    sdk_version = row.get('sdk_version', '')
    sdk_deprecated = row.get('sdk_deprecated', False)
    
    score = 0
    risks = []
    
    if sdk_deprecated:
        score += 60
        risks.append(f'SDK {sdk_version} is deprecated (sunset April 30, 2026)')
    
    # Check for versions missing locale fix (v4.0.0, v4.1.0)
    if sdk_version in ['v4.0.0', 'v4.1.0']:
        score += 15
        risks.append(f'SDK {sdk_version} missing locale fallback fix (patched in v4.2.3)')
    
    # Older v3.x versions on deprecated REST API
    if sdk_version.startswith('v3.'):
        score += 20
        risks.append('Using REST API v2 endpoints being sunset')
    
    score = min(100, score)
    
    return {
        'score': round(score, 1),
        'details': {
            'sdk_version': sdk_version,
            'sdk_deprecated': sdk_deprecated,
            'platform_risks': risks,
        },
    }


def detect_contradictions(scores: dict) -> list[str]:
    """
    Detect significant contradictions between signal dimensions.
    
    A contradiction is flagged when two related signals disagree by >30 points,
    suggesting the account's situation is more nuanced than any single score shows.
    """
    contradictions = []
    
    usage_score = scores['usage_trend']['score']
    nps_score_val = scores['nps_signal']['score']
    support_score = scores['support_health']['score']
    csm_score = scores['csm_sentiment']['score']
    
    # Good NPS but falling usage (silent churn pattern)
    if nps_score_val < 30 and usage_score > 60:
        contradictions.append(
            f"NPS is positive (risk={nps_score_val}) but usage is declining "
            f"(risk={usage_score}) — possible silent churn"
        )
    
    # Bad NPS but strong usage (trapped user pattern)
    if nps_score_val > 60 and usage_score < 30:
        contradictions.append(
            f"NPS is negative (risk={nps_score_val}) but usage is strong "
            f"(risk={usage_score}) — trapped/reluctant users"
        )
    
    # Positive CSM sentiment but high support ticket load
    if csm_score < 30 and support_score > 60:
        contradictions.append(
            f"CSM sentiment is positive (risk={csm_score}) but support tickets "
            f"are concerning (risk={support_score}) — CSM may not see the full picture"
        )
    
    # Negative CSM sentiment but good quantitative signals
    if csm_score > 60 and usage_score < 30 and support_score < 30:
        contradictions.append(
            f"CSM notes are negative (risk={csm_score}) but usage and support "
            f"metrics look healthy — qualitative concern without quantitative backing yet"
        )
    
    # NPS score/verbatim contradiction (from data loader)
    nps_details = scores['nps_signal']['details']
    if nps_details.get('has_contradiction'):
        contradictions.append(
            f"NPS score and verbatim comment contradict: {nps_details.get('contradiction_note', '')}"
        )
    
    return contradictions


def compute_risk_scores(
    master_df: pd.DataFrame,
    csm_extractions: list[dict],
) -> pd.DataFrame:
    """
    Compute transparent, explainable risk scores for all accounts.
    
    Returns the master DataFrame augmented with risk scores, tiers,
    and contradiction flags.
    """
    # Build CSM data lookup
    csm_by_account = {}
    for ext in csm_extractions:
        acct_id = ext.get('er_matched_account_id')
        if acct_id and not pd.isna(acct_id):
            acct_id = int(acct_id)
            csm_by_account[acct_id] = ext
    
    results = []
    for _, row in master_df.iterrows():
        acct_id = int(row['account_id'])
        csm_data = csm_by_account.get(acct_id)
        
        # Score each dimension
        scores = {
            'usage_trend': score_usage_trend(row),
            'support_health': score_support_health(row),
            'nps_signal': score_nps_signal(row),
            'csm_sentiment': score_csm_sentiment(row, csm_data),
            'contract_proximity': score_contract_proximity(row),
            'platform_risk': score_platform_risk(row),
        }
        
        # Compute weighted composite
        composite = sum(
            scores[dim]['score'] * WEIGHTS[dim]
            for dim in WEIGHTS
        )
        
        # Detect contradictions
        contradictions = detect_contradictions(scores)
        
        # Determine tier
        # Critical override: certain signals force High regardless of composite
        critical_override = False
        override_reason = ''
        
        csm_signals = (csm_data or {}).get('churn_signals', [])
        if 'competitor_evaluation' in csm_signals:
            critical_override = True
            override_reason = 'Active competitor evaluation detected in CSM notes'
        elif 'explicit_churn_threat' in csm_signals:
            critical_override = True
            override_reason = 'Explicit churn threat in CSM notes'
        elif 'migration_to_alternative' in csm_signals:
            critical_override = True
            override_reason = 'Migration to alternative solution underway'
        
        if critical_override:
            tier = 'High'
        elif composite >= 65:
            tier = 'High'
        elif composite >= 40:
            tier = 'Medium'
        else:
            tier = 'Low'
        
        # Low-confidence flag & specific reasons
        low_confidence_dims = sum(
            1 for dim in scores.values()
            if dim.get('details', {}).get('low_confidence', False)
        )
        low_conf_reasons = []
        for dim_name, info in scores.items():
            if info.get('details', {}).get('low_confidence', False):
                reason = info.get('details', {}).get('reason', f'Missing data in {dim_name}')
                low_conf_reasons.append(f"{dim_name.replace('_', ' ').title()}: {reason}")
        if len(contradictions) >= 2:
            low_conf_reasons.append(f"{len(contradictions)} cross-signal contradictions")
        
        has_low_confidence = (low_confidence_dims >= 2 or len(contradictions) >= 2)
        
        if has_low_confidence:
            confidence_level = 'Low Confidence'
        else:
            confidence_level = 'Normal'
        
        # Contributing factors (top 3 by score)
        sorted_dims = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
        contributing_factors = [
            f"{dim} ({info['score']})" for dim, info in sorted_dims[:3]
        ]
        
        results.append({
            'account_id': acct_id,
            'risk_score': round(composite, 1),
            'risk_tier': tier,
            'confidence_level': confidence_level,
            'low_confidence_reasons': ' | '.join(low_conf_reasons) if low_conf_reasons else '',
            'critical_override': critical_override,
            'override_reason': override_reason,
            'contributing_factors': '; '.join(contributing_factors),
            'contradiction_flags': ' | '.join(contradictions) if contradictions else '',
            'contradiction_count': len(contradictions),
            # Individual dimension scores
            'usage_trend_score': scores['usage_trend']['score'],
            'support_health_score': scores['support_health']['score'],
            'nps_signal_score': scores['nps_signal']['score'],
            'csm_sentiment_score': scores['csm_sentiment']['score'],
            'contract_proximity_score': scores['contract_proximity']['score'],
            'platform_risk_score': scores['platform_risk']['score'],
            # Full details as JSON
            'score_details': json.dumps({dim: info for dim, info in scores.items()}, default=str),
        })
    
    results_df = pd.DataFrame(results)
    
    # Merge back into master
    scored = master_df.merge(results_df, on='account_id', how='left')
    
    return scored


if __name__ == '__main__':
    # Quick test with dummy CSM data
    from src.data_loader import build_master_dataset
    master = build_master_dataset('data/raw', 'data/processed')
    scored = compute_risk_scores(master, [])
    
    window = scored[scored['renewing_in_window']].sort_values('risk_score', ascending=False)
    print(f"\n--- Risk Scores (top 10) ---")
    for _, row in window.head(10).iterrows():
        print(f"  {row['risk_tier']:6s} | {row['risk_score']:5.1f} | {row['account_name']:30s} | "
              f"${row['arr']:>10,} | {row['confidence_level']}")
