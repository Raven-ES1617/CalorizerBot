import httpx

from config import Config, ProviderConfig
from .base_provider import BaseProvider


class MistralProvider(BaseProvider):
    def __init__(self, provider_config: ProviderConfig = None):
        if provider_config is None:
            provider_config = next((p for p in Config.PROVIDERS if p.name.lower() == "mistral"), None)
            if provider_config is None:
                raise ValueError("No provider config found for 'mistral'")

        self.api_key = provider_config.api_key
        self.model_name = provider_config.vision_model

    async def send_request(self, payload: dict) -> dict:
        """
        Supports both text-only and vision prompts for OpenRouter.
        payload keys may include:
          - text_prompt / vision_prompt
          - image (URL or data URI)
        """
        prompt = payload.get("text_prompt") or payload.get("vision_prompt") or ""
        image = payload.get("image")
        temperature = payload.get("temperature", 0.1)
        max_tokens = payload.get("max_tokens", 1000)

        # Build OpenRouter-compatible messages format
        if image:
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image}},
            ]
        else:
            content = [{"type": "text", "text": prompt}]

        json_payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=Config.REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{Config.OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=json_payload,
            )
            if response.status_code >= 400:
                # include body text for debugging if needed
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            return response.json()

    def name(self) -> str:
        return "mistral"