"""
LLM Client for Renewal Risk Intelligence.

Wraps the Groq API (OpenAI-compatible endpoint) with:
- Environment-based key loading (never hardcoded)
- Retry logic with exponential backoff
- Model fallback (primary → fallback)
- Call logging for cost/latency tracking
"""

import os
import time
import json
import csv
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# Model configuration
PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

# Log file for tracking API calls
LOG_DIR = Path("data/processed")


class LLMClient:
    """Groq API client with retry, fallback, and logging."""
    
    def __init__(self, log_dir: str = None):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment. "
                "Create a .env file with GROQ_API_KEY=your_key_here"
            )
        
        self.client = Groq(api_key=api_key)
        self.log_dir = Path(log_dir) if log_dir else LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "llm_call_log.csv"
        self._init_log()
    
    def _init_log(self):
        """Initialize the call log CSV if it doesn't exist."""
        if not self.log_path.exists():
            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'model', 'job_type', 'account_id',
                    'prompt_tokens', 'completion_tokens', 'total_tokens',
                    'latency_ms', 'success', 'error',
                ])
    
    def _log_call(self, model, job_type, account_id, usage, latency_ms, success, error=''):
        """Log an API call to the CSV."""
        with open(self.log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                model,
                job_type,
                account_id,
                usage.get('prompt_tokens', 0) if usage else 0,
                usage.get('completion_tokens', 0) if usage else 0,
                usage.get('total_tokens', 0) if usage else 0,
                round(latency_ms, 1),
                success,
                error,
            ])
    
    def call(
        self,
        messages: list[dict],
        job_type: str = 'generic',
        account_id: str = '',
        temperature: float = 0.1,
        max_tokens: int = 2000,
        response_format: dict = None,
        max_retries: int = 3,
    ) -> dict | None:
        """
        Make an API call with retry and model fallback.
        
        Returns the parsed response content, or None on failure.
        """
        models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
        
        for model in models_to_try:
            for attempt in range(max_retries):
                try:
                    start = time.time()
                    
                    kwargs = {
                        'model': model,
                        'messages': messages,
                        'temperature': temperature,
                        'max_tokens': max_tokens,
                    }
                    if response_format:
                        kwargs['response_format'] = response_format
                    
                    response = self.client.chat.completions.create(**kwargs)
                    
                    latency_ms = (time.time() - start) * 1000
                    content = response.choices[0].message.content
                    usage = {
                        'prompt_tokens': response.usage.prompt_tokens,
                        'completion_tokens': response.usage.completion_tokens,
                        'total_tokens': response.usage.total_tokens,
                    }
                    
                    self._log_call(model, job_type, account_id, usage, latency_ms, True)
                    return {
                        'content': content,
                        'model': model,
                        'usage': usage,
                        'latency_ms': latency_ms,
                    }
                    
                except Exception as e:
                    latency_ms = (time.time() - start) * 1000
                    error_msg = str(e)
                    self._log_call(model, job_type, account_id, None, latency_ms, False, error_msg)
                    
                    if 'rate_limit' in error_msg.lower() or '429' in error_msg:
                        # Rate limited — backoff and retry
                        wait = (2 ** attempt) * 2
                        print(f"  Rate limited on {model}, waiting {wait}s...")
                        time.sleep(wait)
                    elif attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        print(f"  Failed on {model} after {max_retries} retries: {error_msg[:100]}")
                        break  # Try fallback model
        
        return None
    
    def call_json(
        self,
        messages: list[dict],
        job_type: str = 'generic',
        account_id: str = '',
        temperature: float = 0.1,
        max_tokens: int = 2000,
        max_retries: int = 3,
    ) -> dict | None:
        """Make an API call expecting JSON response. Parses and returns the dict."""
        result = self.call(
            messages=messages,
            job_type=job_type,
            account_id=account_id,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            max_retries=max_retries,
        )
        
        if result and result['content']:
            try:
                parsed = json.loads(result['content'])
                result['parsed'] = parsed
                return result
            except json.JSONDecodeError:
                # Try to extract JSON from the response
                content = result['content']
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(content[start:end])
                        result['parsed'] = parsed
                        return result
                    except json.JSONDecodeError:
                        pass
                print(f"  Failed to parse JSON response for {job_type}/{account_id}")
        
        return None
