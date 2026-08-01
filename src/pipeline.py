"""
Main Pipeline for Renewal Risk Intelligence.

Orchestrates the full pipeline:
1. Entity resolution
2. Data loading & master dataset creation
3. LLM extraction from CSM notes
4. Risk scoring with CSM enrichment
5. LLM explanation generation
6. Non-obvious insights
7. Final output assembly

Run: python src/pipeline.py
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.entity_resolution import resolve_all_sources
from src.data_loader import build_master_dataset
from src.llm_extraction import extract_csm_notes, generate_explanations
from src.risk_scoring import compute_risk_scores
from src.insights import generate_all_insights


RAW_DIR = 'data/raw'
PROCESSED_DIR = 'data/processed'


def run_pipeline():
    """Execute the full pipeline."""
    
    print("=" * 60)
    print("RENEWAL RISK INTELLIGENCE PIPELINE")
    print("=" * 60)
    
    # === Step 1: Entity Resolution ===
    print("\n[1/6] Entity Resolution...")
    resolution_df = resolve_all_sources(RAW_DIR)
    Path(PROCESSED_DIR).mkdir(parents=True, exist_ok=True)
    resolution_df.to_csv(Path(PROCESSED_DIR) / 'entity_resolution_log.csv', index=False)
    
    csm_only = resolution_df[resolution_df['source'] == 'csm_notes.txt']
    resolved = csm_only[csm_only['match_type'] != 'unresolved']
    print(f"  CSM notes: {len(resolved)}/{len(csm_only)} resolved")
    
    # === Step 2: Build Master Dataset ===
    print("\n[2/6] Building master dataset...")
    master_df = build_master_dataset(RAW_DIR, PROCESSED_DIR)
    
    # === Step 3: LLM Extraction from CSM Notes ===
    print("\n[3/6] LLM extraction from CSM notes...")
    csm_df = extract_csm_notes(RAW_DIR, PROCESSED_DIR)
    
    # Load extractions as list of dicts for scoring
    with open(Path(PROCESSED_DIR) / 'csm_extractions.json', 'r', encoding='utf-8') as f:
        csm_extractions = json.load(f)
    
    # === Step 4: Risk Scoring ===
    print("\n[4/6] Computing risk scores...")
    scored_df = compute_risk_scores(master_df, csm_extractions)
    scored_df.to_csv(Path(PROCESSED_DIR) / 'scored_accounts.csv', index=False)
    
    # Show renewal window summary
    renewal = scored_df[scored_df['renewing_in_window']].sort_values('risk_score', ascending=False)
    print(f"\n  Renewal window accounts by tier:")
    print(f"    High:   {len(renewal[renewal['risk_tier'] == 'High'])} accounts, "
          f"${renewal[renewal['risk_tier'] == 'High']['arr'].sum():,.0f} ARR")
    print(f"    Medium: {len(renewal[renewal['risk_tier'] == 'Medium'])} accounts, "
          f"${renewal[renewal['risk_tier'] == 'Medium']['arr'].sum():,.0f} ARR")
    print(f"    Low:    {len(renewal[renewal['risk_tier'] == 'Low'])} accounts, "
          f"${renewal[renewal['risk_tier'] == 'Low']['arr'].sum():,.0f} ARR")
    
    low_conf = renewal[renewal['confidence_level'] == 'Low Confidence']
    if len(low_conf) > 0:
        print(f"    Low Confidence: {len(low_conf)} accounts flagged")
    
    contradictions = renewal[renewal['contradiction_count'] > 0]
    if len(contradictions) > 0:
        print(f"    Contradictions: {len(contradictions)} accounts have signal contradictions")
    
    # === Step 5: Generate Explanations ===
    print("\n[5/6] Generating account explanations...")
    explanations = generate_explanations(scored_df, csm_extractions, PROCESSED_DIR)
    
    # === Step 6: Non-Obvious Insights ===
    print("\n[6/6] Generating non-obvious insights...")
    insights = generate_all_insights(scored_df, PROCESSED_DIR)
    
    # === Final Summary ===
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\nOutputs in {PROCESSED_DIR}/:")
    print(f"  entity_resolution_log.csv  — {len(resolution_df)} resolution entries")
    print(f"  master_account_dataset.csv — {len(master_df)} accounts")
    print(f"  csm_extractions.json       — {len(csm_extractions)} note extractions")
    print(f"  scored_accounts.csv        — {len(scored_df)} scored accounts")
    print(f"  account_explanations.json  — {len(explanations)} explanations")
    print(f"  insights.json              — {len(insights)} insights")
    print(f"  llm_call_log.csv           — API call log")
    
    print(f"\nTo launch the dashboard:")
    print(f"  streamlit run app.py")
    
    return scored_df, explanations, insights


if __name__ == '__main__':
    run_pipeline()
