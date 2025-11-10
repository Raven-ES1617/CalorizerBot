# vision_processor.py
import asyncio
import json
import re
import time
import logging
from typing import Dict, List, Any, Optional, Union

from deep_translator import GoogleTranslator
from db_database_structure import db, Product
from models.model_pool import ModelPool
from config import Config

# Логирование
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# default prompts
_DEFAULT_VISION_PROMPT = """
Ты — система анализа изображений еды. 
Твоя единственная задача — извлечь список всех реальных пищевых продуктов, видимых на фото, 
и вернуть их в формате JSON строго по заданной схеме.

ПРАВИЛА:
1. Ответь ТОЛЬКО в формате JSON. Без текста, описаний, пояснений или комментариев.
2. Не используй Markdown, ```json и другие разметки.
3. Все названия продуктов должны быть реальными и распространёнными (например, "яблоко", "курица", "рис").
4. Если не уверен в продукте — укажи "неизвестный продукт".
5. Для каждого продукта обязательно укажи:
   - "name": название продукта
   - "estimated_weight_g": примерный вес (в граммах, реалистично)
   - "cooking_method": способ приготовления (например, "варка", "жарка", "свежий", "выпечка")

6. Если на фото нет еды — верни {"products": []}

Формат ответа (СТРОГО):
{
  "products": [
    {
      "name": "яблоко",
      "estimated_weight_g": 120,
      "cooking_method": "свежий"
    }
  ]
}
"""

_DEFAULT_NUTRITION_PROMPT_TEMPLATE = """
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
"""


class VisionProcessor:
    def __init__(self):
        self.model_pool = ModelPool()
        self.request_delay = getattr(Config, "REQUEST_DELAY", 3.0)
        self.last_request_time = 0.0
        self.use_demo_data = getattr(Config, "USE_DEMO_DATA", True)
        self.use_estimated_data = getattr(Config, "USE_ESTIMATED_DATA", True)
        self.vision_prompt = getattr(Config, "VISION_PROMPT", _DEFAULT_VISION_PROMPT).strip()
        self.nutrition_prompt_template = getattr(
            Config, "NUTRITION_PROMPT_TEMPLATE", _DEFAULT_NUTRITION_PROMPT_TEMPLATE
        )

    # ------------------------
    # Асинхронный перевод через deep-translator (Google)
    # ------------------------
    async def translate_text(self, text: str, src="auto", dest="en") -> str:
        try:
            translator = await asyncio.to_thread(GoogleTranslator, source=src, target=dest)
            result = await asyncio.to_thread(translator.translate, text)
            return result.lower().strip() if result else text.lower().strip()
        except Exception as e:
            logger.warning("⚠️ Ошибка перевода '%s': %s", text, e)
            return text.lower().strip()

    # ------------------------
    # Вспомогательные функции
    # ------------------------
    async def _make_request_with_delay(self):
        now = time.time()
        since = now - self.last_request_time
        if since < self.request_delay:
            await asyncio.sleep(self.request_delay - since)
        self.last_request_time = time.time()

    def _clean_json_response(self, text: Any) -> Dict:
        if not text:
            raise ValueError("Пустой ответ AI")
        if isinstance(text, dict):
            return text
        if isinstance(text, list):
            return {"products": text}
        if not isinstance(text, str):
            raise ValueError("Неожиданный тип ответа от модели")

        txt = text.strip()
        txt = re.sub(r'^\s*```(?:json)?\s*', '', txt, flags=re.IGNORECASE)
        txt = re.sub(r'\s*```$', '', txt)
        txt = txt.strip()

        for attempt in range(3):
            try:
                return json.loads(txt)
            except json.JSONDecodeError as e:
                txt = re.sub(r',\s*([]}])', r'\1', txt)
                txt = re.sub(r'[\x00-\x1f]+', '', txt)
                if attempt == 2:
                    raise ValueError(f"Невалидный JSON: {e}\nФрагмент: {txt[:400]}")
        raise ValueError("Не удалось распарсить JSON ответ")

    def _filter_products(self, products: List[Dict]) -> List[Dict]:
        if not products:
            return []

        fake_keywords = getattr(Config, "FAKE_PRODUCT_KEYWORDS", ['углик', 'пастыр', 'иктори', 'декоратив'])
        out = []
        for p in products:
            name = (p.get('name') or p.get('product_name') or '').strip()
            if not name:
                continue
            if any(fake in name.lower() for fake in fake_keywords):
                continue

            if 'estimated_weight_g' not in p and 'estimated_weight' in p:
                p['estimated_weight_g'] = p['estimated_weight']
            if 'estimated_weight' not in p and 'estimated_weight_g' in p:
                p['estimated_weight'] = p['estimated_weight_g']
            if 'cooking_method' not in p:
                p['cooking_method'] = p.get('cooking', 'не указано')

            try:
                p['estimated_weight_g'] = float(p.get('estimated_weight_g', p.get('estimated_weight', 0))) or 0.0
            except Exception:
                p['estimated_weight_g'] = 0.0

            out.append({
                'name': name,
                'estimated_weight_g': p['estimated_weight_g'],
                'cooking_method': p['cooking_method']
            })
        return out

    def _get_demo_products(self) -> List[Dict]:
        if not self.use_demo_data:
            raise ValueError("Демо-данные отключены")
        return [
            {"name": "Булочка", "estimated_weight_g": 80, "cooking_method": "выпечка"},
            {"name": "Мясо", "estimated_weight_g": 120, "cooking_method": "жарка"},
            {"name": "Овощи", "estimated_weight_g": 100, "cooking_method": "свежие"}
        ]

    def _get_estimated_nutrition(self, product_name: str, weight: float, cooking_method: str) -> Dict:
        estimates = {
            'булочка': {'calories': 3.0, 'proteins': 0.08, 'fats': 0.04, 'carbs': 0.57},
            'хлеб': {'calories': 2.65, 'proteins': 0.09, 'fats': 0.035, 'carbs': 0.49},
            'мясо': {'calories': 2.5, 'proteins': 0.25, 'fats': 0.16, 'carbs': 0},
            'овощ': {'calories': 0.4, 'proteins': 0.015, 'fats': 0.002, 'carbs': 0.08},
            'фрукт': {'calories': 0.6, 'proteins': 0.01, 'fats': 0.003, 'carbs': 0.15},
        }
        low = product_name.lower()
        for key, vals in estimates.items():
            if key in low:
                return {k: round(v * weight, 1) for k, v in vals.items()} | {'_source': 'примерные данные'}
        return {
            'calories': round(1.5 * weight, 1),
            'proteins': round(0.1 * weight, 1),
            'fats': round(0.08 * weight, 1),
            'carbs': round(0.2 * weight, 1),
            '_source': 'дефолт'
        }

    async def _prepare_image_content(self, image_url_or_path: str) -> str:
        if image_url_or_path.startswith(('http://', 'https://')):
            return image_url_or_path
        import base64
        with open(image_url_or_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            return f"data:image/jpeg;base64,{b64}"

    # ------------------------
    # Основные методы
    # ------------------------
    async def analyze_food_image(self, image_url_or_path: str) -> List[Dict]:
        logger.info("🔍 Начинаем анализ изображения...")
        await self._make_request_with_delay()
        image_content = await self._prepare_image_content(image_url_or_path)
        payload = {
            "type": "vision_chat",
            "vision_prompt": self.vision_prompt,
            "image": image_content,
            "max_tokens": 2000,
            "temperature": 0.1
        }
        try:
            result: Optional[Union[dict, str]] = await self.model_pool.request(payload)
            if isinstance(result, dict) and "choices" in result:
                try:
                    message_content = result["choices"][0]["message"]["content"]
                    if isinstance(message_content, str):
                        result = message_content
                except Exception:
                    pass
            products_data = self._clean_json_response(result)
            products_raw = products_data.get("products", [])
            if isinstance(products_raw, dict):
                products_list = [products_raw]
            elif isinstance(products_raw, list):
                products_list = [p for p in products_raw if isinstance(p, dict)]
            else:
                return self._get_demo_products()
            filtered = self._filter_products(products_list)
            if not filtered:
                return self._get_demo_products()
            return filtered
        except Exception as e:
            logger.exception("Ошибка при анализе изображения: %s", e)
            return self._get_demo_products()

    async def get_nutrition_info(self, product_name: str, weight: float, cooking_method: str) -> Dict:
        # 1. Перевод на английский
        product_name_en = await self.translate_text(product_name)

        # 2. Поиск в локальной БД
        local = None
        try:
            local = db.session.query(Product).filter(
                Product.product_name_lower.contains(product_name_en)
            ).first()
        except Exception as e:
            logger.warning("Ошибка поиска в локальной БД: %s", e)

        if local:
            try:
                calories = round((local.calories_per_100g or 0.0) * weight / 100.0, 1)
                proteins = round((local.proteins_per_100g or 0.0) * weight / 100.0, 1)
                fats = round((local.fats_per_100g or 0.0) * weight / 100.0, 1)
                carbs = round((local.carbs_per_100g or 0.0) * weight / 100.0, 1)
                return {'calories': calories, 'proteins': proteins, 'fats': fats, 'carbs': carbs, '_source': 'local_db'}
            except Exception as e:
                logger.warning("Ошибка расчёта БЖУ из локального продукта: %s", e)

        # 3. AI fallback
        try:
            await self._make_request_with_delay()
            prompt_text = self.nutrition_prompt_template.format(
                product_name=product_name,
                weight=weight,
                cooking_method=cooking_method
            )
            ai_payload = {"type": "nutrition", "text_prompt": prompt_text, "max_tokens": 500, "temperature": 0.1}
            result: Optional[Union[dict, str]] = await self.model_pool.request(ai_payload)

            if isinstance(result, dict):
                nutrition_data = result
            else:
                nutrition_data = self._clean_json_response(result)

            if nutrition_data is None and isinstance(result, dict):
                choices = result.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content")
                    if content:
                        nutrition_data = self._clean_json_response(content)

            if nutrition_data:
                for f in ['calories', 'proteins', 'fats', 'carbs']:
                    try:
                        nutrition_data[f] = round(float(nutrition_data.get(f, 0.0)), 1)
                    except Exception:
                        nutrition_data[f] = 0.0
                nutrition_data['_source'] = 'ai'
                return nutrition_data

        except Exception as e:
            logger.warning("AI ошибка для %s: %s", product_name, e)

        # 4. Estimated fallback
        if self.use_estimated_data:
            return self._get_estimated_nutrition(product_name, weight, cooking_method)

        raise ValueError(f"Невозможно получить данные о питании для '{product_name}'")
