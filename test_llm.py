import os
from dotenv import load_dotenv

load_dotenv()
# Set fallback env vars before importing config
if not os.environ.get("LLM_API_KEY") and os.environ.get("OPENROUTER_API_KEY"):
    os.environ["LLM_API_KEY"] = os.environ.get("OPENROUTER_API_KEY")
if not os.environ.get("LLM_MODEL") and os.environ.get("OPENROUTER_MODEL"):
    os.environ["LLM_MODEL"] = os.environ.get("OPENROUTER_MODEL")
if not os.environ.get("LLM_BASE_URL"):
    os.environ["LLM_BASE_URL"] = "https://openrouter.ai/api/v1/chat/completions"

from src.config import settings
from src.services.llm.client import LLMClient

def test_llm():
    try:
        print("Initializing LLM Client...")
        client = LLMClient()
        print(f"Provider: {client.provider}")
        print(f"Model: {client.model}")
        print(f"Base URL: {client.base_url}")
        
        system_prompt = "You are a helpful assistant. Please reply in English."
        user_prompt = "Say 'Hello, LLM is working properly!' and nothing else."
        
        print("\nSending request to LLM...")
        response = client.generate(system_prompt, user_prompt, is_json_response=False)
        print("\n=== Response from LLM ===")
        print(response)
        print("=========================")
    except Exception as e:
        print(f"\nError occurred: {e}")

if __name__ == "__main__":
    test_llm()
