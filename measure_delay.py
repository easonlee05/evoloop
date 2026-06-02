import urllib.request
import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY") or os.getenv("CRS_OAI_KEY") or ""
url = os.getenv("BASE_URL") or "https://yxai.chat/v1"
if url.endswith("/"):
    url = url.rstrip("/")

# Using a fallback URL if the primary one fails, exactly as in the codebase
anthropic_url = f"{url}/messages"

data = {
    "model": "gpt-5.4",
    "messages": [
        {"role": "system", "content": "You are PM."},
        {"role": "user", "content": "写一段长文分析"}
    ],
    "stream": True
}
anthropic_data = {
    "model": "gpt-5.4",
    "max_tokens": 1000,
    "system": "You are PM.",
    "messages": [{"role": "user", "content": "写一段长文分析"}],
    "stream": True
}
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
anthropic_headers = dict(headers)
anthropic_headers["anthropic-version"] = "2023-06-01"

print("--- OLD METHOD (urllib) ---")
req = urllib.request.Request(anthropic_url, data=json.dumps(anthropic_data).encode("utf-8"), headers=anthropic_headers, method="POST")
start = time.time()
ttft = None
try:
    with urllib.request.urlopen(req, timeout=120) as response:
        for line in response:
            if ttft is None:
                ttft = time.time() - start
                print(f"Old TTFT (Time to First Block): {ttft:.2f}s")
except Exception as e:
    print("Old method failed or timed out:", e)
total_old = time.time() - start
print(f"Old Total Time: {total_old:.2f}s\n")

print("--- NEW METHOD (requests iter_lines) ---")
start = time.time()
ttft = None
try:
    with requests.post(anthropic_url, json=anthropic_data, headers=anthropic_headers, stream=True, timeout=120) as response:
        for line in response.iter_lines():
            if line and ttft is None:
                ttft = time.time() - start
                print(f"New TTFT (Time to First Token): {ttft:.2f}s")
except Exception as e:
    print("New method failed:", e)
total_new = time.time() - start
print(f"New Total Time: {total_new:.2f}s")
