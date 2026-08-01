"""
Entity Resolution for Renewal Risk Intelligence.

Resolves account references across all data sources, with special focus on
the messy csm_notes.txt file. Produces a confidence-scored resolution log
and flags unresolved matches for manual review.

Design decisions:
- CSM notes are split on '---' delimiter and parsed for account IDs + names
- Account IDs embedded in notes (e.g., "#1007", "(1009)", "acct 1004") are
  treated as authoritative — but name mismatches are still logged
- Fuzzy matching uses rapidfuzz token_sort_ratio after name normalization
- Confidence tiers: exact_id (95+), fuzzy_high (85+), fuzzy_low (60-84), unresolved (<60)
"""

import re
import pandas as pd
from rapidfuzz import fuzz, process
from pathlib import Path


# Legal suffixes to strip during normalization — only true entity types
LEGAL_SUFFIXES = [
    r'\binc\.?\b', r'\bltd\.?\b', r'\bcorp\.?\b', r'\bllc\.?\b',
    r'\bco\.?\b',
]


def normalize_name(name: str) -> str:
    """Normalize an account name for matching: lowercase, strip punctuation and legal suffixes."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common legal suffixes
    for suffix in LEGAL_SUFFIXES:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)
    # Remove punctuation except hyphens and spaces
    name = re.sub(r'[^\w\s-]', '', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def parse_csm_notes(filepath: str) -> list[dict]:
    """
    Parse csm_notes.txt into individual note entries.
    
    Each note may contain:
    - A date (various formats)
    - An account name (sometimes misspelled)
    - An account ID (sometimes, in various formats)
    - Free-text content
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split on --- delimiters
    raw_blocks = re.split(r'\n-{3,}\n', content)
    
    notes = []
    for block in raw_blocks:
        block = block.strip()
        if not block or block.startswith('=== CSM Call Notes'):
            continue
        
        note = {
            'raw_text': block,
            'extracted_id': None,
            'extracted_name': None,
            'date_str': None,
        }
        
        # Try to extract account ID — various patterns seen in data:
        # "#1007", "(1009)", "acct 1004", "account 1016", "(acct 1004)"
        id_patterns = [
            r'#(\d{4})',
            r'\((?:acct\s*)?(\d{4})\)',
            r'(?:acct|account)\s*(\d{4})',
        ]
        for pattern in id_patterns:
            match = re.search(pattern, block, re.IGNORECASE)
            if match:
                note['extracted_id'] = int(match.group(1))
                break
        
        # Extract date from first line
        first_line = block.split('\n')[0]
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',          # 2026-03-20
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2})',  # Mar 12
            r'(\d{1,2}/\d{1,2})',             # 3/15, 04/03
            r'((?:march|april|january|february)\s+\d{1,2})',  # march 25
        ]
        for pattern in date_patterns:
            match = re.search(pattern, first_line, re.IGNORECASE)
            if match:
                note['date_str'] = match.group(1)
                break
        
        # Extract account name from first line/second line
        # Strategy: handle pipe-delimited format first, then fall back to dash-based
        name_line = first_line
        
        # Check for pipe-delimited format: "2026-03-20 | NovaTech Industries | James O."
        if '|' in name_line:
            pipe_parts = [p.strip() for p in name_line.split('|')]
            # Account name is typically the second segment (after date)
            if len(pipe_parts) >= 2:
                # Find the segment that's not a date and not a short CSM name
                for part in pipe_parts[1:]:
                    part_clean = part.strip()
                    if len(part_clean) > 3 and not re.match(r'^[A-Z][a-z]+\s+[A-Z]\.?$', part_clean):
                        name_line = part_clean
                        break
                else:
                    name_line = pipe_parts[1] if len(pipe_parts) > 1 else ''
        else:
            # Step 1: Remove date patterns FIRST (before touching dashes)
            name_line = re.sub(r'\d{4}-\d{2}-\d{2}', '', name_line)
            name_line = re.sub(r'\d{1,2}/\d{1,2}', '', name_line)
            name_line = re.sub(r'(?:march|april|january|february|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}', '', name_line, flags=re.IGNORECASE)
            
            # Step 2: Remove account ID references
            name_line = re.sub(r'#\d{4}', '', name_line)
            name_line = re.sub(r'\((?:acct\s*)?\d{4}\)', '', name_line)
            name_line = re.sub(r'(?:acct|account)\s*\d{4}', '', name_line)
            
            # Step 3: Handle double-dash separators like "-- meridian health -- priya"
            # Split on ' -- ' or '--' and take the meaningful segments
            if '--' in name_line:
                segments = re.split(r'\s*--\s*', name_line)
                segments = [s.strip() for s in segments if s.strip()]
                # If multiple segments, try to find the one that's an account name
                # (not a short CSM first name, not empty)
                name_candidates = []
                for seg in segments:
                    # Skip single short words (likely CSM names like "priya", "James O.")
                    if len(seg.split()) == 1 and len(seg) < 10:
                        continue
                    # Skip if it looks like "James O." or "Emily W." pattern
                    if re.match(r'^[A-Z][a-z]+\s+[A-Z]\.?$', seg):
                        continue
                    name_candidates.append(seg)
                if name_candidates:
                    name_line = name_candidates[0]
                elif segments:
                    name_line = segments[0]
            
            # Step 4: Strip leading dashes/separators (what's left after date removal)
            name_line = re.sub(r'^[\s\-–—:]+', '', name_line)
        
        # Clean up
        name_line = name_line.strip().strip('-–—').strip()
        # Truncate at body separator: "summit analytics - routine check-in" → "summit analytics"
        # Match ' - ' (space-dash-space) which separates name from body text
        body_sep = re.search(r'\s+[-–—]\s+', name_line)
        if body_sep:
            name_line = name_line[:body_sep.start()].strip()
        # Also truncate at period followed by space (body text start)
        if '. ' in name_line and len(name_line.split('. ')[0]) > 3:
            candidate = name_line.split('. ')[0]
            if len(candidate) < 40:
                name_line = candidate
        # Remove trailing digits that might be account numbers (e.g., "evergreen media 1015")
        bare_id_match = re.search(r'\s+(\d{4})\s*$', name_line)
        if bare_id_match:
            potential_id = int(bare_id_match.group(1))
            if 1000 <= potential_id <= 1200:
                # This looks like an account ID appended to the name
                if note['extracted_id'] is None:
                    note['extracted_id'] = potential_id
                name_line = name_line[:bare_id_match.start()].strip()
        
        # If the extracted "name" is obviously body text (contains commas, very long, 
        # or starts with lowercase and has verb-like structure), clear it
        if name_line and (len(name_line) > 60 or ',' in name_line):
            name_line = ''
        
        if name_line and len(name_line) > 2:
            note['extracted_name'] = name_line
        
        notes.append(note)
    
    return notes


def build_account_registry(accounts_df: pd.DataFrame) -> dict:
    """Build a lookup of normalized names to account IDs."""
    registry = {}
    for _, row in accounts_df.iterrows():
        normalized = normalize_name(row['account_name'])
        registry[normalized] = {
            'account_id': row['account_id'],
            'original_name': row['account_name'],
        }
    return registry


def resolve_csm_notes(
    notes: list[dict],
    accounts_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resolve CSM notes to accounts. Returns a DataFrame with resolution results.
    
    Resolution strategy:
    1. If account ID is explicitly stated → use it (exact_id match)
       BUT still check name against registry to flag mismatches
    2. If no ID → fuzzy match name against account registry
    3. Log everything with confidence scores
    """
    registry = build_account_registry(accounts_df)
    id_to_name = dict(zip(accounts_df['account_id'], accounts_df['account_name']))
    canonical_names = list(registry.keys())
    
    results = []
    for i, note in enumerate(notes):
        result = {
            'note_index': i,
            'source': 'csm_notes.txt',
            'raw_text_preview': note['raw_text'][:120].replace('\n', ' '),
            'extracted_name': note['extracted_name'],
            'extracted_id': note['extracted_id'],
            'matched_account_id': None,
            'matched_account_name': None,
            'match_type': 'unresolved',
            'confidence_score': 0,
            'name_mismatch_flag': False,
            'notes': '',
        }
        
        if note['extracted_id'] is not None:
            acct_id = note['extracted_id']
            if acct_id in id_to_name:
                result['matched_account_id'] = acct_id
                result['matched_account_name'] = id_to_name[acct_id]
                result['match_type'] = 'exact_id'
                result['confidence_score'] = 98
                
                # Check if extracted name matches the actual account name
                if note['extracted_name']:
                    actual_normalized = normalize_name(id_to_name[acct_id])
                    extracted_normalized = normalize_name(note['extracted_name'])
                    name_similarity = fuzz.token_sort_ratio(extracted_normalized, actual_normalized)
                    if name_similarity < 70:
                        result['name_mismatch_flag'] = True
                        result['notes'] = (
                            f"ID {acct_id} maps to '{id_to_name[acct_id]}' but note mentions "
                            f"'{note['extracted_name']}' (similarity: {name_similarity}%). "
                            f"Trusting account_id per policy."
                        )
            else:
                result['notes'] = f"Extracted ID {acct_id} not found in accounts registry"
                result['match_type'] = 'unresolved'
                result['confidence_score'] = 0
        
        elif note['extracted_name']:
            # Fuzzy match
            extracted_norm = normalize_name(note['extracted_name'])
            if not extracted_norm:
                result['notes'] = 'Extracted name normalizes to empty string'
                results.append(result)
                continue
                
            best_match = process.extractOne(
                extracted_norm,
                canonical_names,
                scorer=fuzz.token_sort_ratio,
            )
            
            if best_match:
                matched_norm, score, _ = best_match
                matched_info = registry[matched_norm]
                result['matched_account_id'] = matched_info['account_id']
                result['matched_account_name'] = matched_info['original_name']
                result['confidence_score'] = score
                
                if score >= 85:
                    result['match_type'] = 'fuzzy_high'
                elif score >= 60:
                    result['match_type'] = 'fuzzy_low'
                    result['notes'] = f"Low-confidence fuzzy match ({score}%). Flagged for manual review."
                else:
                    result['match_type'] = 'unresolved'
                    result['notes'] = f"Best fuzzy match score ({score}%) below threshold. Manual review required."
        else:
            result['notes'] = 'No account name or ID could be extracted from note'
        
        results.append(result)
    
    return pd.DataFrame(results)


def resolve_all_sources(data_dir: str) -> pd.DataFrame:
    """
    Run entity resolution across all data sources.
    
    CSV files (usage, tickets, NPS) join cleanly on account_id.
    CSM notes require fuzzy matching.
    Returns the full resolution log.
    """
    data_path = Path(data_dir)
    accounts_df = pd.read_csv(data_path / 'accounts.csv')
    valid_ids = set(accounts_df['account_id'].tolist())
    
    all_results = []
    
    # --- CSV sources: verify all account_ids exist in accounts.csv ---
    csv_sources = {
        'usage_metrics.csv': 'account_id',
        'support_tickets.csv': 'account_id',
        'nps_responses.csv': 'account_id',
    }
    
    for filename, id_col in csv_sources.items():
        df = pd.read_csv(data_path / filename)
        source_ids = set(df[id_col].unique())
        
        matched = source_ids & valid_ids
        unmatched = source_ids - valid_ids
        
        for aid in matched:
            all_results.append({
                'note_index': None,
                'source': filename,
                'raw_text_preview': f'account_id={aid}',
                'extracted_name': None,
                'extracted_id': aid,
                'matched_account_id': aid,
                'matched_account_name': accounts_df[accounts_df['account_id'] == aid]['account_name'].iloc[0],
                'match_type': 'exact_id',
                'confidence_score': 100,
                'name_mismatch_flag': False,
                'notes': '',
            })
        
        for aid in unmatched:
            all_results.append({
                'note_index': None,
                'source': filename,
                'raw_text_preview': f'account_id={aid}',
                'extracted_name': None,
                'extracted_id': aid,
                'matched_account_id': None,
                'matched_account_name': None,
                'match_type': 'unresolved',
                'confidence_score': 0,
                'name_mismatch_flag': False,
                'notes': f'Account ID {aid} not found in accounts.csv',
            })
    
    # --- CSM Notes: fuzzy matching ---
    notes = parse_csm_notes(str(data_path / 'csm_notes.txt'))
    csm_resolution = resolve_csm_notes(notes, accounts_df)
    all_results.extend(csm_resolution.to_dict('records'))
    
    return pd.DataFrame(all_results)


def get_csm_note_map(data_dir: str) -> dict[int, list[str]]:
    """
    Return a mapping of account_id -> list of raw CSM note texts,
    using the entity resolution results.
    """
    data_path = Path(data_dir)
    accounts_df = pd.read_csv(data_path / 'accounts.csv')
    notes = parse_csm_notes(str(data_path / 'csm_notes.txt'))
    resolution_df = resolve_csm_notes(notes, accounts_df)
    
    note_map: dict[int, list[str]] = {}
    for _, row in resolution_df.iterrows():
        if row['matched_account_id'] is not None and row['match_type'] != 'unresolved':
            acct_id = int(row['matched_account_id'])
            note_idx = int(row['note_index'])
            if acct_id not in note_map:
                note_map[acct_id] = []
            note_map[acct_id].append(notes[note_idx]['raw_text'])
    
    return note_map


if __name__ == '__main__':
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/raw'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'data/processed'
    
    print("Running entity resolution...")
    resolution_df = resolve_all_sources(data_dir)
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = Path(output_dir) / 'entity_resolution_log.csv'
    resolution_df.to_csv(output_path, index=False)
    
    # Summary
    print(f"\nTotal resolution entries: {len(resolution_df)}")
    print(f"\nBy source:")
    print(resolution_df.groupby('source')['match_type'].value_counts().to_string())
    
    print(f"\nName mismatches flagged:")
    mismatches = resolution_df[resolution_df['name_mismatch_flag'] == True]
    for _, row in mismatches.iterrows():
        print(f"  {row['notes']}")
    
    print(f"\nUnresolved entries:")
    unresolved = resolution_df[resolution_df['match_type'] == 'unresolved']
    for _, row in unresolved.iterrows():
        print(f"  [{row['source']}] {row['raw_text_preview'][:80]} — {row['notes']}")
    
    print(f"\nFuzzy-low (manual review needed):")
    fuzzy_low = resolution_df[resolution_df['match_type'] == 'fuzzy_low']
    for _, row in fuzzy_low.iterrows():
        print(f"  '{row['extracted_name']}' → {row['matched_account_name']} ({row['confidence_score']}%)")
    
    print(f"\nResolution log saved to: {output_path}")
