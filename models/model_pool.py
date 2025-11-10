import logging
from typing import Union, Dict, Any

from .provider_gemini import GeminiProvider
from .provider_mistral import MistralProvider
from .provider_qwen import QwenProvider

logger = logging.getLogger(__name__)

class ModelPool:
    """Менеджер пула моделей с failover при ошибках.
    Теперь поддерживает .request(payload: dict) — алиас для send_request.
    """

    def __init__(self):
        self.providers = [
            MistralProvider(),
            QwenProvider(),
            GeminiProvider()
        ]

    async def request(self, payload: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """Совместимый метод — используйте в коде как model_pool.request(payload)."""
        return await self.send_request(payload)

    async def send_request(self, payload: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """Попытка отправить запрос по очереди до успешного ответа.
        При успехе возвращает либо dict (если провайдер вернул JSON), либо str.
        """
        for provider in self.providers:
            try:
                result = await provider.send_request(payload)
                logger.info(f"Запрос обработан моделью {provider.name()}")
                return result
            except Exception as e:
                logger.warning(f"Провайдер {provider.name()} не справился: {e}")
        raise Exception("Все провайдеры недоступны")
