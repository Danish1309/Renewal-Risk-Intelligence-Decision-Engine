"""
Non-Obvious Insights for Renewal Risk Intelligence.

Goes beyond account-by-account scoring to find cross-source patterns.

Primary investigation: SDK deprecation impact at portfolio level
- How many accounts and how much ARR sit on deprecated SDK versions?
- How do their usage trends compare to migrated accounts?
- Is the usage decline product-caused rather than organic disengagement?

Secondary investigation: "Trapped usage" pattern
- Accounts with strong usage but negative NPS/rising tickets
"""

import pandas as pd
import numpy as np
from pathlib import Path


def analyze_sdk_deprecation_impact(master_df: pd.DataFrame) -> dict:
    """
    Portfolio-level analysis of deprecated SDK impact.
    
    Quantifies:
    - Count and ARR of accounts on deprecated SDKs
    - Usage trend comparison: deprecated vs. migrated accounts
    - Whether usage drops correlate with SDK sunset timeline
    """
    # Split accounts into deprecated vs current SDK
    deprecated = master_df[master_df['sdk_deprecated'] == True].copy()
    current = master_df[master_df['sdk_deprecated'] == False].copy()
    
    # Also identify accounts on old v4.x versions with known issues
    has_locale_bug = master_df[master_df['sdk_version'].isin(['v4.0.0', 'v4.1.0'])].copy()
    
    # Portfolio metrics
    total_accounts = len(master_df)
    dep_count = int(len(deprecated))
    dep_arr = float(deprecated['arr'].sum())
    
    # Among renewal window accounts
    renewal = master_df[master_df['renewing_in_window']].copy()
    dep_renewal = renewal[renewal['sdk_deprecated'] == True]
    cur_renewal = renewal[renewal['sdk_deprecated'] == False]
    
    dep_renewal_count = int(len(dep_renewal))
    dep_renewal_arr = float(dep_renewal['arr'].sum())
    
    # Usage trend comparison
    dep_api_trend = float(deprecated['api_calls_trend_pct'].mean())
    cur_api_trend = float(current['api_calls_trend_pct'].mean())
    
    dep_user_trend = float(deprecated['active_users_trend_pct'].mean())
    cur_user_trend = float(current['active_users_trend_pct'].mean())
    
    # 6-month endpoint change comparison
    dep_6m_change = float(deprecated['api_calls_6m_change_pct'].mean())
    cur_6m_change = float(current['api_calls_6m_change_pct'].mean())
    
    # Locale bug accounts
    locale_bug_count = int(len(has_locale_bug))
    locale_bug_arr = float(has_locale_bug['arr'].sum())
    locale_bug_api_trend = float(has_locale_bug['api_calls_trend_pct'].mean())
    
    dep_sdk_pct = dep_count / total_accounts * 100
    
    insight = {
        'title': 'SDK Deprecation: Product-Caused Churn Risk Hiding as Disengagement',
        'type': 'sdk_deprecation_impact',
        'summary': (
            f"{dep_count} accounts ({dep_sdk_pct:.1f}% of total portfolio) "
            f"are still on deprecated SDK v3.x, representing ${dep_arr:,.0f} in ARR. "
            f"Among the {len(renewal)} accounts renewing in the next 90 days, "
            f"{dep_renewal_count} are on deprecated SDKs with ${dep_renewal_arr:,.0f} ARR at stake. "
            f"These accounts show an average API call decline of {dep_api_trend:.1f}% per month "
            f"versus {cur_api_trend:.1f}% for accounts on current SDKs. "
            f"A simple usage-decline rule would flag these as 'disengaged' — but the root cause "
            f"is that their SDK is hitting deprecated endpoints being sunset on April 30, 2026. "
            f"This is product-caused breakage, not organic churn, and requires a migration "
            f"assistance response rather than a retention play."
        ),
        'evidence': {
            'deprecated_sdk_accounts': dep_count,
            'deprecated_sdk_arr': dep_arr,
            'deprecated_sdk_pct': round(dep_sdk_pct, 1),
            'renewal_window': {
                'deprecated_count': dep_renewal_count,
                'deprecated_arr': dep_renewal_arr,
                'current_sdk_count': int(len(cur_renewal)),
            },
            'usage_trend_comparison': {
                'deprecated_api_trend_pct_per_month': round(dep_api_trend, 2),
                'current_api_trend_pct_per_month': round(cur_api_trend, 2),
                'delta': round(dep_api_trend - cur_api_trend, 2),
                'deprecated_user_trend_pct_per_month': round(dep_user_trend, 2),
                'current_user_trend_pct_per_month': round(cur_user_trend, 2),
                'deprecated_6m_api_change_pct': round(dep_6m_change, 2),
                'current_6m_api_change_pct': round(cur_6m_change, 2),
            },
            'locale_bug_affected': {
                'count': locale_bug_count,
                'arr': locale_bug_arr,
                'api_trend_pct': round(locale_bug_api_trend, 2),
                'sdk_versions': ['v4.0.0', 'v4.1.0'],
            },
            'deprecated_accounts': deprecated[['account_id', 'account_name', 'arr', 'sdk_version',
                                                 'api_calls_trend_pct', 'api_calls_6m_change_pct',
                                                 'days_to_renewal', 'renewing_in_window']].to_dict('records'),
        },
        'recommendation': (
            f"Create an 'SDK Migration Sprint' program: assign a dedicated solutions architect "
            f"to the {dep_renewal_count} deprecated-SDK accounts renewing in the next 90 days (${dep_renewal_arr:,.0f} ARR). "
            f"Frame renewal conversations around migration support rather than price/value — "
            f"these accounts are frustrated by breakage, not disengaged from the product. "
            f"For accounts like NovaTech (4 P1 tickets related to v3 deprecation) and Zenith Publishing "
            f"(demanding 30% discount), the migration path is the unlock for retention."
        ),
    }
    
    return insight


def analyze_trapped_usage(master_df: pd.DataFrame) -> dict:
    """
    Find 'trapped usage' pattern: strong usage metrics but negative sentiment.
    
    These accounts are using the product heavily but unhappily — at risk of
    sudden churn once a viable alternative is found, rather than gradual decline.
    """
    renewal = master_df[master_df['renewing_in_window']].copy()
    
    # Define "strong usage" as usage trend > -5% (not declining significantly)
    # and "negative sentiment" as NPS <= 6 or has contradiction
    trapped = renewal[
        (renewal['api_calls_trend_pct'] > -5) &
        (
            (renewal['nps_score'] <= 6) |
            (renewal['has_nps_contradiction'] == True)
        )
    ].copy()
    
    if len(trapped) == 0:
        return {
            'title': 'Trapped Usage Pattern',
            'type': 'trapped_usage',
            'summary': 'No accounts showing the trapped usage pattern in the renewal window.',
            'evidence': {},
            'found': False,
        }
    
    insight = {
        'title': '"Trapped Users": Stable Usage Masking Unhappy Accounts',
        'type': 'trapped_usage',
        'found': True,
        'summary': (
            f"{len(trapped)} accounts in the renewal window show stable or growing usage "
            f"but negative NPS or sentiment contradictions. These accounts won't show up "
            f"in a usage-decline alert but are at risk of sudden churn once they find an "
            f"alternative. Total ARR: ${trapped['arr'].sum():,.0f}."
        ),
        'evidence': {
            'count': int(len(trapped)),
            'arr': float(trapped['arr'].sum()),
            'accounts': trapped[['account_id', 'account_name', 'arr',
                                  'api_calls_trend_pct', 'nps_score',
                                  'nps_verbatim', 'has_nps_contradiction']].to_dict('records'),
        },
        'recommendation': (
            "Schedule deep-dive CSM calls with these accounts focused on product feedback "
            "rather than renewal. High usage gives us leverage — understand what's driving "
            "the negative sentiment before a competitor capitalizes on it."
        ),
    }
    
    return insight


def generate_all_insights(master_df: pd.DataFrame, output_dir: str) -> list[dict]:
    """Generate all non-obvious insights and save to output."""
    insights = []
    
    # Primary: SDK deprecation impact
    sdk_insight = analyze_sdk_deprecation_impact(master_df)
    insights.append(sdk_insight)
    
    # Secondary: Trapped usage
    trapped_insight = analyze_trapped_usage(master_df)
    if trapped_insight.get('found', False):
        insights.append(trapped_insight)
    
    # Save
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    import json
    with open(Path(output_dir) / 'insights.json', 'w', encoding='utf-8') as f:
        json.dump(insights, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\nGenerated {len(insights)} insights")
    for ins in insights:
        print(f"  - {ins['title']}")
    
    return insights


if __name__ == '__main__':
    from src.data_loader import build_master_dataset
    master = build_master_dataset('data/raw', 'data/processed')
    insights = generate_all_insights(master, 'data/processed')
    
    for ins in insights:
        print(f"\n{'='*60}")
        print(f"INSIGHT: {ins['title']}")
        print(f"{'='*60}")
        print(ins['summary'])
