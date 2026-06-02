import json
import urllib.request
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY") or os.getenv("CRS_OAI_KEY") or ""
base_url = os.getenv("BASE_URL") or "https://yxai.chat/v1"
if base_url.endswith("/"):
    base_url = base_url.rstrip("/")

models = ["gpt-5.4", "gpt-5.5", "claude-sonnet-4-6", "claude-opus-4-7", "deepseek-v4-pro"]

def test_openai(model):
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10}
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return "SUCCESS: " + str(response.read().decode("utf-8")[:60])
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: " + e.read().decode("utf-8")

def test_anthropic(model):
    url = f"{base_url}/messages"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "anthropic-version": "2023-06-01"}
    data = {"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10}
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return "SUCCESS: " + str(response.read().decode("utf-8")[:60])
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: " + e.read().decode("utf-8")

for m in models:
    print(f"\n--- Model: {m} ---")
    print("OpenAI format:", test_openai(m))
    print("Anthropic format:", test_anthropic(m))
