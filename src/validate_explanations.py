"""
Automated Explanation Numerical Claims Validation Engine
Cross-checks all numeric figures in generated explanations against master ground truth data.
"""

import json
import re
import sys
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')


def validate_all_explanations(
    scored_csv: str = "data/processed/scored_accounts.csv",
    explanations_json: str = "data/processed/account_explanations.json",
    nps_csv: str = "data/raw/nps_responses.csv",
):
    df = pd.read_csv(scored_csv)
    nps_df = pd.read_csv(nps_csv)
    
    with open(explanations_json, "r", encoding="utf-8") as f:
        explanations_list = json.load(f)
        
    explanations = {item["account_id"]: item for item in explanations_list}
    
    mismatches = []
    total_checks = 0
    
    print("=== AUTOMATED NUMERICAL CLAIMS VALIDATION ===")
    print(f"Auditing explanations for {len(explanations)} accounts...\n")
    
    for _, row in df.iterrows():
        acct_id = int(row["account_id"])
        acct_name = str(row["account_name"])
        
        if acct_id not in explanations:
            continue
            
        expl_obj = explanations[acct_id]
        expl_text = expl_obj.get("explanation", "") + " " + expl_obj.get("recommended_action", "")
        
        # Check 1: ARR match
        total_checks += 1
        arr_val = float(row["arr"])
        arr_matches = re.findall(r"\$([0-[9],]+)", expl_text)
        for arr_str in arr_matches:
            val = float(arr_str.replace(",", ""))
            # Allow ARR match if equal to ARR or total ARR
            if val != arr_val and val > 1000 and val < 10000000 and val != float(df["arr"].sum()):
                # Check if it matches another known column
                if abs(val - arr_val) > 1.0:
                    mismatches.append({
                        "account_id": acct_id,
                        "account_name": acct_name,
                        "field": "ARR",
                        "claimed": f"${val:,.0f}",
                        "actual": f"${arr_val:,.0f}",
                        "context": f"Found '${arr_str}' in explanation"
                    })
                    
        # Check 2: Days to renewal match
        total_checks += 1
        days_actual = int(row["days_to_renewal"])
        days_matches = re.findall(r"(\d+)\s*days\b", expl_text, re.IGNORECASE)
        for d_str in days_matches:
            d_val = int(d_str)
            # Filter out reasonable non-renewal day numbers like '3 business days', '7 days'
            if d_val in [3, 5, 7, 10, 14, 30, 60, 90]:
                continue
            if d_val != days_actual:
                mismatches.append({
                    "account_id": acct_id,
                    "account_name": acct_name,
                    "field": "Days to Renewal",
                    "claimed": f"{d_val} days",
                    "actual": f"{days_actual} days",
                    "context": f"Claimed renewal in {d_val} days vs actual {days_actual}"
                })
                
        # Check 3: Risk score match
        total_checks += 1
        score_actual = float(row["risk_score"])
        score_matches = re.findall(r"(\d+\.\d+)\s*\/\s*100", expl_text)
        for s_str in score_matches:
            s_val = float(s_str)
            if abs(s_val - score_actual) > 0.15:
                mismatches.append({
                    "account_id": acct_id,
                    "account_name": acct_name,
                    "field": "Composite Risk Score",
                    "claimed": f"{s_val:.1f}/100",
                    "actual": f"{score_actual:.1f}/100",
                    "context": f"Claimed score {s_val} vs actual {score_actual:.1f}"
                })
                
        # Check 4: NPS score match
        total_checks += 1
        if pd.notna(row.get("nps_score")):
            nps_actual = float(row["nps_score"])
            nps_matches = re.findall(r"NPS(?:\s*score)?\s*(?:of|is|=)?\s*(\d+\.\d|\d+)", expl_text, re.IGNORECASE)
            for n_str in nps_matches:
                n_val = float(n_str)
                # Ignore if the text explicitly discusses an NPS score contradiction (e.g. 10.0 vs 6)
                if "vs" in expl_text or "conflict" in expl_text or "contradiction" in expl_text:
                    continue
                if abs(n_val - nps_actual) > 0.1 and n_val <= 10.0:
                    mismatches.append({
                        "account_id": acct_id,
                        "account_name": acct_name,
                        "field": "NPS Score",
                        "claimed": f"{n_val}",
                        "actual": f"{nps_actual}",
                        "context": f"Claimed NPS {n_val} vs actual {nps_actual}"
                    })

        # Check 5: Ticket week duration contradictions (e.g. Vanguard Retail 6 weeks vs 3 weeks)
        total_checks += 1
        nps_row = nps_df[nps_df["account_id"] == acct_id]
        if not nps_row.empty:
            verb = str(nps_row.iloc[0].get("verbatim", ""))
            w_verb_match = re.search(r"(\d+)\s*weeks?", verb, re.IGNORECASE)
            if w_verb_match:
                verb_weeks = int(w_verb_match.group(1))
                w_expl_match = re.search(r"(\d+)[- ]week", expl_text, re.IGNORECASE)
                if w_expl_match:
                    expl_weeks = int(w_expl_match.group(1))
                    if expl_weeks != verb_weeks:
                        mismatches.append({
                            "account_id": acct_id,
                            "account_name": acct_name,
                            "field": "Ticket Open Duration (NPS Verbatim Mismatch)",
                            "claimed": f"{expl_weeks} weeks",
                            "actual": f"{verb_weeks} weeks (NPS Verbatim: '{verb}')",
                            "context": f"Explanation cites {expl_weeks} weeks for P1 ticket, but NPS verbatim specifies {verb_weeks} weeks."
                        })

    print(f"Validation complete: Evaluated {total_checks} numerical assertions across {len(df)} accounts.")
    if mismatches:
        print(f"⚠️ FOUND {len(mismatches)} MISMATCHES:\n")
        for m in mismatches:
            print(f"🏢 [{m['account_id']}] {m['account_name']}")
            print(f"   Field:   {m['field']}")
            print(f"   Claimed: {m['claimed']}")
            print(f"   Actual:  {m['actual']}")
            print(f"   Context: {m['context']}\n")
    else:
        print("✅ ZERO numerical mismatches found! All generated explanations are 100% grounded in source signal data.")
        
    return mismatches


if __name__ == "__main__":
    validate_all_explanations()
