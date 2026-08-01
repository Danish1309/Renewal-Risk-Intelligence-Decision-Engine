"""
Data Loader for Renewal Risk Intelligence.

Loads all raw data sources, joins them using entity resolution results,
and produces a unified account-level dataset with aggregated signals
for downstream scoring and LLM consumption.

Reference date: April 15, 2026 (per user specification).
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta


REFERENCE_DATE = datetime(2026, 4, 15)
RENEWAL_WINDOW_DAYS = 90


def load_accounts(data_dir: str) -> pd.DataFrame:
    """Load accounts and flag those renewing within 90 days of reference date."""
    df = pd.read_csv(Path(data_dir) / 'accounts.csv')
    df['contract_end_date'] = pd.to_datetime(df['contract_end_date'])
    df['days_to_renewal'] = (df['contract_end_date'] - REFERENCE_DATE).dt.days
    df['renewing_in_window'] = (df['days_to_renewal'] >= 0) & (df['days_to_renewal'] <= RENEWAL_WINDOW_DAYS)
    return df


def load_usage_metrics(data_dir: str) -> pd.DataFrame:
    """Load usage metrics and compute per-account trend signals."""
    df = pd.read_csv(Path(data_dir) / 'usage_metrics.csv')
    df['month'] = pd.to_datetime(df['month'])
    
    # Sort by account and month for trend computation
    df = df.sort_values(['account_id', 'month'])
    
    agg = []
    for acct_id, group in df.groupby('account_id'):
        group = group.sort_values('month')
        months = group['month'].values
        
        # Core metrics
        api_calls = group['api_calls'].values
        active_users = group['active_users'].values
        content = group['content_entries_created'].values
        workflows = group['workflows_triggered'].values
        
        # Trend: linear regression slope (normalized to percentage change)
        def pct_trend(vals):
            """Compute trend as % change per month using linear regression."""
            if len(vals) < 2 or np.mean(vals) == 0:
                return 0.0
            x = np.arange(len(vals), dtype=float)
            slope = np.polyfit(x, vals, 1)[0]
            return (slope / np.mean(vals)) * 100  # % per month
        
        # Last month vs first month change
        def endpoint_change(vals):
            if vals[0] == 0:
                return 0.0
            return ((vals[-1] - vals[0]) / vals[0]) * 100
        
        # SDK version (latest)
        sdk_version = group['sdk_version'].iloc[-1]
        sdk_deprecated = sdk_version.startswith('v3.')
        
        agg.append({
            'account_id': acct_id,
            # Raw recent values
            'api_calls_last_month': int(api_calls[-1]),
            'api_calls_avg': float(np.mean(api_calls)),
            'active_users_last_month': int(active_users[-1]),
            'active_users_avg': float(np.mean(active_users)),
            'content_created_last_month': int(content[-1]),
            'workflows_last_month': int(workflows[-1]),
            # Trends (% change per month)
            'api_calls_trend_pct': round(pct_trend(api_calls), 2),
            'active_users_trend_pct': round(pct_trend(active_users), 2),
            'content_trend_pct': round(pct_trend(content), 2),
            'workflows_trend_pct': round(pct_trend(workflows), 2),
            # Endpoint changes (first to last month)
            'api_calls_6m_change_pct': round(endpoint_change(api_calls), 2),
            'active_users_6m_change_pct': round(endpoint_change(active_users), 2),
            # SDK info
            'sdk_version': sdk_version,
            'sdk_deprecated': sdk_deprecated,
        })
    
    return pd.DataFrame(agg)


def load_support_tickets(data_dir: str) -> pd.DataFrame:
    """Load support tickets and compute per-account aggregates."""
    df = pd.read_csv(Path(data_dir) / 'support_tickets.csv')
    df['created_date'] = pd.to_datetime(df['created_date'])
    
    # All accounts from accounts.csv need an entry, even if they have 0 tickets
    accounts = pd.read_csv(Path(data_dir) / 'accounts.csv')
    all_ids = set(accounts['account_id'].tolist())
    
    agg = []
    for acct_id in all_ids:
        acct_tickets = df[df['account_id'] == acct_id]
        
        if len(acct_tickets) == 0:
            agg.append({
                'account_id': acct_id,
                'ticket_count': 0,
                'p1_p2_count': 0,
                'open_escalated_count': 0,
                'avg_resolution_hours': None,
                'recent_ticket_count': 0,  # last 3 months
                'ticket_trend': 'none',
                'has_blocking_issue': False,
                'has_recurring_issue': False,
            })
            continue
        
        p1_p2 = acct_tickets[acct_tickets['priority'].isin(['P1', 'P2'])]
        open_esc = acct_tickets[acct_tickets['status'].isin(['Open', 'Escalated'])]
        
        # Recent tickets (last 3 months from reference date)
        three_months_ago = REFERENCE_DATE - timedelta(days=90)
        recent = acct_tickets[acct_tickets['created_date'] >= pd.Timestamp(three_months_ago)]
        older = acct_tickets[acct_tickets['created_date'] < pd.Timestamp(three_months_ago)]
        
        # Trend
        if len(recent) > len(older):
            trend = 'increasing'
        elif len(recent) < len(older):
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        # Check for blocking/recurring issues
        has_blocking = acct_tickets['description'].str.contains('Blocking issue', case=False, na=False).any()
        has_recurring = acct_tickets['description'].str.contains('Recurring issue', case=False, na=False).any()
        
        res_times = acct_tickets['resolution_time_hours'].dropna()
        
        agg.append({
            'account_id': acct_id,
            'ticket_count': len(acct_tickets),
            'p1_p2_count': len(p1_p2),
            'open_escalated_count': len(open_esc),
            'avg_resolution_hours': round(res_times.mean(), 1) if len(res_times) > 0 else None,
            'recent_ticket_count': len(recent),
            'ticket_trend': trend,
            'has_blocking_issue': has_blocking,
            'has_recurring_issue': has_recurring,
        })
    
    return pd.DataFrame(agg)


def load_nps(data_dir: str) -> pd.DataFrame:
    """Load NPS responses with contradiction detection."""
    df = pd.read_csv(Path(data_dir) / 'nps_responses.csv')
    
    # Detect score/verbatim contradictions
    # Positive verbatims with low scores, or negative verbatims with high scores
    positive_phrases = [
        'best', 'love', 'great', 'phenomenal', 'transformed', 'won easily',
        'would recommend',
    ]
    negative_phrases = [
        'downgrade', 'wasted', 'forever', 'done', 'fallen off', 'steep',
    ]
    
    contradictions = []
    for _, row in df.iterrows():
        comment = str(row.get('verbatim_comment', '')).lower()
        score = row['score']
        contradiction = None
        
        if score <= 4:
            # Low score — check for positive verbatim
            if any(p in comment for p in positive_phrases):
                contradiction = f"Score={score} contradicts positive verbatim"
        elif score >= 8:
            # High score — check for negative verbatim
            if any(p in comment for p in negative_phrases):
                contradiction = f"Score={score} contradicts negative verbatim"
        
        contradictions.append(contradiction)
    
    df['nps_contradiction'] = contradictions
    df['has_nps_contradiction'] = df['nps_contradiction'].notna()
    
    # Detect non-English verbatims
    def detect_language(text):
        if not isinstance(text, str) or not text.strip():
            return 'empty'
        # Simple heuristic for non-Latin scripts
        if any('\u4e00' <= c <= '\u9fff' for c in text):
            return 'zh'
        if any('\u00e0' <= c <= '\u00ff' for c in text):
            # Could be French, Spanish, etc.
            if any(w in text.lower() for w in ['est', 'mais', "l'", 'notre', 'équipe']):
                return 'fr'
            if any(w in text.lower() for w in ['es', 'pero', 'soporte', 'producto']):
                return 'es'
            return 'other'
        return 'en'
    
    df['verbatim_language'] = df['verbatim_comment'].apply(detect_language)
    
    return df


def load_changelog(data_dir: str) -> dict:
    """Parse changelog and extract key events with dates for cross-referencing."""
    with open(Path(data_dir) / 'changelog.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    events = {
        'v3_sdk_sunset_date': '2026-04-30',
        'v3_sdk_sunset_original': '2026-03-31',
        'legacy_workflow_freeze_date': '2026-02-28',
        'legacy_editor_removal': '2026-05-01',  # v4.4.0 expected May 2026
        'v4_2_0_breaking_change_date': '2025-10-15',
        'v4_2_3_locale_fix_date': '2025-11-01',
        'v4_3_0_locale_rewrite_date': '2025-12-15',
        'v4_3_1_safari_fix_date': '2026-01-20',
        'v4_3_2_timezone_fix_date': '2026-03-01',
        'deprecated_sdk_versions': ['v3.1.2', 'v3.2.0'],
        'versions_missing_locale_fix': ['v4.0.0', 'v4.1.0'],  # locale fallback bug
    }
    
    return events


def build_master_dataset(data_dir: str, output_dir: str) -> pd.DataFrame:
    """
    Build the master account-level dataset by joining all sources.
    
    Returns a DataFrame with one row per account, containing:
    - Firmographics and contract info
    - Aggregated usage trends
    - Support ticket summary
    - NPS score and verbatim
    - SDK version and deprecation status
    - Flags for data sparsity
    """
    accounts = load_accounts(data_dir)
    usage = load_usage_metrics(data_dir)
    tickets = load_support_tickets(data_dir)
    nps = load_nps(data_dir)
    
    # Rename NPS columns to avoid conflicts
    nps_cols = nps.rename(columns={
        'score': 'nps_score',
        'verbatim_comment': 'nps_verbatim',
    })
    
    # Join everything on account_id
    master = accounts.merge(usage, on='account_id', how='left')
    master = master.merge(tickets, on='account_id', how='left')
    master = master.merge(
        nps_cols[['account_id', 'nps_score', 'nps_verbatim', 'nps_contradiction',
                  'has_nps_contradiction', 'verbatim_language']],
        on='account_id', how='left'
    )
    
    # Mark data sparsity
    master['has_nps'] = master['nps_score'].notna()
    master['has_tickets'] = master['ticket_count'] > 0
    master['has_usage'] = master['api_calls_last_month'].notna()
    
    # Count available signal sources (out of 4: usage, tickets, NPS, CSM notes)
    # CSM notes will be added later after LLM extraction
    master['signal_count'] = (
        master['has_usage'].astype(int) +
        master['has_tickets'].astype(int) +
        master['has_nps'].astype(int)
    )
    
    # Save
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = Path(output_dir) / 'master_account_dataset.csv'
    master.to_csv(output_path, index=False)
    
    print(f"Master dataset built: {len(master)} accounts")
    print(f"  Renewing in 90-day window: {master['renewing_in_window'].sum()}")
    print(f"  With NPS data: {master['has_nps'].sum()}")
    print(f"  With support tickets: {master['has_tickets'].sum()}")
    print(f"  On deprecated SDK: {master['sdk_deprecated'].sum()}")
    print(f"  NPS contradictions: {master['has_nps_contradiction'].sum()}")
    print(f"  Saved to: {output_path}")
    
    return master


if __name__ == '__main__':
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/raw'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'data/processed'
    master = build_master_dataset(data_dir, output_dir)
    
    # Show accounts renewing in window
    window = master[master['renewing_in_window']].sort_values('days_to_renewal')
    print(f"\n--- Accounts renewing within {RENEWAL_WINDOW_DAYS} days ---")
    for _, row in window.iterrows():
        print(f"  {row['account_id']} | {row['account_name']:30s} | ARR: ${row['arr']:>10,} | "
              f"Renews in {row['days_to_renewal']} days | SDK: {row['sdk_version']}")
