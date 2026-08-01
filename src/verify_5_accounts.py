import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('data/processed/account_explanations.json', 'r', encoding='utf-8') as f:
    exps = json.load(f)

check_ids = [1007, 1003, 1002, 1005, 1001]
check_map = {e['account_id']: e for e in exps}

print("=== 5-ACCOUNT MANUAL CROSS-CHECK VERIFICATION ===\n")
for aid in check_ids:
    e = check_map.get(aid)
    if e:
        print(f"🏢 [{e['account_id']}] {e['account_name']}")
        print(f"   Explanation: {e['explanation']}")
        print(f"   Recommended Action: {e['recommended_action']}\n")
