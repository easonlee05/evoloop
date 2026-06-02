import asyncio
import os
from dotenv import load_dotenv
from app.services.llm import OpenAILLM

load_dotenv()

api_key = os.getenv("API_KEY") or os.getenv("CRS_OAI_KEY") or ""
base_url = os.getenv("BASE_URL") or "https://yxai.chat/v1"

llm = OpenAILLM(api_key, base_url)
for chunk in llm.invoke_stream("PM", "Test", {"goal": "test"}):
    if isinstance(chunk, dict):
        print(f"EVENT: {chunk}")
    else:
        print(chunk[:10].replace("\n", ""), end="")
