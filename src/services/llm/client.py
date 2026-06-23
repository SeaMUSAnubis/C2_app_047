import json
from typing import Any

import httpx

from src.config import settings


class LLMClient:
    def __init__(self):
        self.provider = settings.llm_provider
        self.base_url = settings.llm_base_url
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds
        self.max_retries = settings.llm_max_retries
        self.temperature = settings.llm_temperature
        self.enabled = settings.llm_enabled

    def generate(self, system_prompt: str, user_prompt: str, is_json_response: bool = True) -> str:
        if not self.enabled:
            raise ValueError("LLM is disabled via configuration.")
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not set.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": 1500,
        }

        if is_json_response and self.provider == "openai_compatible":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = self.base_url
        if not url:
            if self.provider == "openai_compatible":
                url = "https://api.openai.com/v1/chat/completions"
            else:
                # Default fallback or error
                url = "https://openrouter.ai/api/v1/chat/completions"
        
        # specific openrouter headers
        if "openrouter" in url.lower():
            headers["HTTP-Referer"] = "http://localhost:5173"
            headers["X-Title"] = "Vespionage UEBA"

        retries = 0
        while retries <= self.max_retries:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    
                    if "error" in data:
                        raise ValueError(f"Provider error: {data['error']}")
                    
                    if "choices" not in data or not data["choices"]:
                        raise ValueError("No choices returned in response.")
                    
                    return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                retries += 1
                if retries > self.max_retries:
                    raise Exception(f"Failed after {self.max_retries} retries. Error: {str(e)}")
        
        raise Exception("LLM generation failed.")
