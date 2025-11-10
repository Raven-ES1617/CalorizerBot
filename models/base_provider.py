from abc import ABC, abstractmethod
from typing import Dict, Any, Union

class BaseProvider(ABC):
    """Абстрактный класс для любого провайдера LLM/Vision"""

    @abstractmethod
    async def send_request(self, payload: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """Отправить запрос к модели и получить JSON-ответ или строку."""
        pass

    @abstractmethod
    def name(self) -> str:
        """Возвращает уникальное имя провайдера"""
        pass
