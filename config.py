import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

    # OpenRouter
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', "https://openrouter.ai/api/v1")
    VISION_MODEL = os.getenv('VISION_MODEL', "google/gemini-flash-1.5")

    # Open Food Facts
    OPEN_FOOD_FACTS_ENABLED = os.getenv('OPEN_FOOD_FACTS_ENABLED', 'true').lower() == 'true'
    OPEN_FOOD_FACTS_BASE_URL = os.getenv('OPEN_FOOD_FACTS_BASE_URL', "https://world.openfoodfacts.org/api/v2")
    OPEN_FOOD_FACTS_SEARCH_URL = os.getenv('OPEN_FOOD_FACTS_SEARCH_URL',
                                           "https://world.openfoodfacts.org/cgi/search.pl")

    # Request settings
    REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', '3.0'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

    # Fallback settings
    USE_DEMO_DATA = os.getenv('USE_DEMO_DATA', 'true').lower() == 'false'
    USE_ESTIMATED_DATA = os.getenv('USE_ESTIMATED_DATA', 'true').lower() == 'true'

    # Prompts
    VISION_PROMPT = os.getenv('VISION_PROMPT', """
    Ты - эксперт по питанию. Проанализируй фото еды и определи КАЖДЫЙ продукт на фото.

    ВАЖНЫЕ ПРАВИЛА:
    1. Используй ТОЛЬКО РЕАЛЬНЫЕ и РАСПРОСТРАНЕННЫЕ названия продуктов
    2. Не выдумывай фантастические названия
    3. Если не уверен в названии - укажи "неизвестный продукт"
    4. Укажи примерный вес в граммах (реалистично)
    5. Укажи способ приготовления

    ВЕРНИ ТОЛЬКО JSON БЕЗ ЛЮБЫХ ДОПОЛНИТЕЛЬНЫХ ТЕКСТОВ:
    {
        "products": [
            {
                "name": "реальное название продукта",
                "estimated_weight_g": 150,
                "cooking_method": "способ приготовления"
            }
        ]
    }
    """)

    NUTRITION_PROMPT_TEMPLATE = os.getenv('NUTRITION_PROMPT_TEMPLATE', """
    Рассчитай БЖУ для продукта: {product_name}
    Вес: {weight} грамм
    Способ приготовления: {cooking_method}

    ВАЖНО: Верни ТОЛЬКО JSON без пояснений

    Формат:
    {{
        "calories": 150.5,
        "proteins": 10.5,
        "fats": 5.2,
        "carbs": 15.0
    }}
    """)