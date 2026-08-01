"""
Print formatted output summary of the assignment.
"""
import pandas as pd
import json
import sys
import io
from pathlib import Path

# Force UTF-8 output encoding for Windows terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print("=" * 80)
print("             RENEWAL RISK INTELLIGENCE — EXECUTIVE OUTPUT SUMMARY             ")
print("=" * 80)

# --- 1. ENTITY RESOLUTION ---
print("\n" + "—"*40)
print("1. ENTITY RESOLUTION RESULTS")
print("—"*40)
er = pd.read_csv('data/processed/entity_resolution_log.csv')
csm_er = er[er['source'] == 'csm_notes.txt']
print(f"Total CSM Notes Processed: {len(csm_er)}/27")
print(f"Match Breakdown:")
for match_type, count in csm_er['match_type'].value_counts().items():
    print(f"  - {match_type:15s}: {count}")

mismatches = er[er['name_mismatch_flag'] == True]
print(f"\nName Mismatches Flagged:")
for _, row in mismatches.iterrows():
    print(f"  [FLAG] {row['notes']}")

# --- 2. RISK SCORES & TIERING ---
print("\n" + "-"*40)
print("2. RENEWAL RISK TIERING (NEXT 90 DAYS: APR 15 – JUL 14, 2026)")
print("-" * 40)
scored = pd.read_csv('data/processed/scored_accounts.csv')
renewal = scored[scored['renewing_in_window'] == True].sort_values('risk_score', ascending=False)

total_arr = renewal['arr'].sum()
print(f"Total Accounts Renewing in Window: {len(renewal)} | Total ARR at Risk: ${total_arr:,.0f}\n")

headers = f"{'ID':<6} | {'Account Name':<28} | {'ARR ($)':<12} | {'Renews In':<10} | {'Score':<6} | {'Tier':<8} | {'Confidence':<15} | {'Contradictions'}"
print(headers)
print("-" * len(headers))

for _, r in renewal.iterrows():
    acct_id = str(r['account_id'])
    name = str(r['account_name'])
    arr = f"${r['arr']:,}"
    days = f"{int(r['days_to_renewal'])} days"
    score = f"{r['risk_score']:.1f}"
    tier = str(r['risk_tier'])
    conf = str(r['confidence_level'])
    flags = str(r['contradiction_flags']) if pd.notna(r['contradiction_flags']) else ""
    if len(flags) > 35:
        flags = flags[:32] + "..."
    
    print(f"{acct_id:<6} | {name:<28} | {arr:>12} | {days:<10} | {score:>6} | {tier:<8} | {conf:<15} | {flags}")

# --- 3. GROUNDED EXPLANATIONS ---
print("\n" + "-"*40)
print("3. SAMPLE GROUNDED LLM EXPLANATIONS (GROQ API)")
print("-" * 40)
with open('data/processed/account_explanations.json', 'r', encoding='utf-8') as f:
    exps = json.load(f)

for exp in exps[:4]:
    print(f"\nAccount: {exp['account_name']} (ID: {exp['account_id']})")
    print(f"   Explanation: {exp['explanation']}")
    print(f"   Action: {exp['recommended_action']}")

# --- 4. NON-OBVIOUS INSIGHT ---
print("\n" + "-"*40)
print("4. NON-OBVIOUS PORTFOLIO INSIGHTS")
print("-" * 40)
with open('data/processed/insights.json', 'r', encoding='utf-8') as f:
    insights = json.load(f)

for ins in insights:
    print(f"\nTITLE: {ins['title']}")
    print(f"   Summary: {ins['summary']}")
    print(f"   Recommendation: {ins['recommendation']}")

print("\n" + "=" * 80)
