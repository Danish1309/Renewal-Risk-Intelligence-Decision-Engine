"""
Verify available Groq models — run once to confirm which models are active.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
models = client.models.list()

print("Available Groq models:")
print("-" * 60)
for m in sorted(models.data, key=lambda x: x.id):
    print(f"  {m.id}")

# Check our target models
target_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
print("\n--- Target model availability ---")
available_ids = {m.id for m in models.data}
for t in target_models:
    status = "✓ AVAILABLE" if t in available_ids else "✗ NOT FOUND"
    print(f"  {t}: {status}")
