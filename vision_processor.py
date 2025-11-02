import aiohttp
import json
import hashlib
import re
import asyncio
import time
from typing import Dict, List, Optional
from config import Config
from database import db
from food_facts_api import OpenFoodFactsAPI


class VisionProcessor:
    def __init__(self):
        self.api_key = Config.OPENROUTER_API_KEY
        self.base_url = Config.OPENROUTER_BASE_URL
        self.model = Config.VISION_MODEL
        self.last_request_time = 0
        self.request_delay = Config.REQUEST_DELAY
        self.food_facts_api = OpenFoodFactsAPI()
        self.use_demo_data = Config.USE_DEMO_DATA
        self.use_estimated_data = Config.USE_ESTIMATED_DATA

    def _clean_json_response(self, text: str) -> Dict:
        """Очищает и валидирует JSON ответ от AI"""
        if not text:
            raise ValueError("Пустой ответ от AI")

        # Удаляем markdown обрамление
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        # Проверяем, что это похоже на JSON
        if not (text.startswith('{') and text.endswith('}')):
            raise ValueError(f"Ответ не является JSON: {text[:100]}...")

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Пытаемся исправить распространенные ошибки
            text = re.sub(r',\s*}', '}', text)
            text = re.sub(r',\s*]', ']', text)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                raise ValueError(f"Невалидный JSON: {e}\nТекст: {text[:200]}...")

    async def _make_request_with_delay(self):
        """Добавляет задержку между запросами чтобы избежать лимитов"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.request_delay:
            await asyncio.sleep(self.request_delay - time_since_last_request)

        self.last_request_time = time.time()

    async def analyze_food_image(self, image_url_or_path: str) -> List[Dict]:
        """Анализирует изображение еды через OpenRouter"""
        print(f"🔍 Начинаем анализ изображения...")
        print(f"📊 Настройки: API_KEY={'***' if self.api_key else 'НЕТ'}, USE_DEMO_DATA={self.use_demo_data}")

        if not self.api_key:
            print("❌ API ключ отсутствует")
            if self.use_demo_data:
                print("🔄 Переключаемся на демо-данные")
                return self._get_demo_products()
            raise ValueError("OPENROUTER_API_KEY не установлен")

        # Добавляем задержку
        await self._make_request_with_delay()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",
            "X-Title": "Nutrition Bot"
        }

        # Определяем, это URL или локальный файл
        if image_url_or_path.startswith(('http://', 'https://')):
            image_content = {"url": image_url_or_path}
            print("📸 Используем URL изображения")
        else:
            import base64
            with open(image_url_or_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode()
                image_content = {"url": f"data:image/jpeg;base64,{image_base64}"}
            print("📸 Используем локальное изображение (base64)")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": Config.VISION_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": image_content
                        }
                    ]
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.1
        }

        try:
            print(f"🚀 Отправляем запрос к {self.base_url} с моделью {self.model}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=Config.REQUEST_TIMEOUT
                ) as response:

                    print(f"📡 Получен ответ: HTTP {response.status}")

                    if response.status == 429:
                        print("❌ Лимит запросов достигнут (429)")
                        if self.use_demo_data:
                            print("🔄 Переключаемся на демо-данные из-за лимита")
                            return self._get_demo_products()
                        raise Exception("Лимит запросов достигнут")

                    if response.status != 200:
                        error_text = await response.text()
                        print(f"❌ HTTP ошибка {response.status}: {error_text}")
                        if self.use_demo_data:
                            print("🔄 Переключаемся на демо-данные из-за HTTP ошибки")
                            return self._get_demo_products()
                        raise Exception(f"HTTP ошибка: {response.status}")

                    result = await response.json()
                    print("✅ Успешно получили JSON ответ")

                    if 'error' in result:
                        print(f"❌ API ошибка: {result['error']}")
                        if self.use_demo_data:
                            print("🔄 Переключаемся на демо-данные из-за API ошибки")
                            return self._get_demo_products()
                        raise Exception(f"API ошибка: {result['error']}")

                    if not result.get('choices'):
                        print("❌ Нет choices в ответе")
                        if self.use_demo_data:
                            print("🔄 Переключаемся на демо-данные из-за отсутствия choices")
                            return self._get_demo_products()
                        raise Exception("Нет choices в ответе")

                    response_text = result['choices'][0]['message']['content']
                    print(f"📄 RAW VISION RESPONSE: {response_text}")

                    # Парсим JSON
                    products_data = self._clean_json_response(response_text)
                    print("✅ Успешно распарсили JSON")

                    if 'products' not in products_data:
                        print("❌ В ответе отсутствует ключ 'products'")
                        if self.use_demo_data:
                            print("🔄 Переключаемся на демо-данные из-за отсутствия products")
                            return self._get_demo_products()
                        raise ValueError("В ответе отсутствует ключ 'products'")

                    # Фильтруем продукты с выдуманными названиями
                    filtered_products = self._filter_products(products_data['products'])

                    if not filtered_products:
                        print("❌ Все продукты отфильтрованы")
                        if self.use_demo_data:
                            print("🔄 Переключаемся на демо-данные из-за фильтрации")
                            return self._get_demo_products()
                        raise ValueError("Все продукты отфильтрованы")

                    print(f"✅ Успешно обработали {len(filtered_products)} продуктов")
                    return filtered_products

        except Exception as e:
            print(f"❌ Исключение при анализе изображения: {e}")
            if self.use_demo_data:
                print("🔄 Переключаемся на демо-данные из-за исключения")
                return self._get_demo_products()
            raise

    def _filter_products(self, products: List[Dict]) -> List[Dict]:
        """Фильтрует продукты с выдуманными названиями"""
        filtered_products = []
        fake_keywords = ['углик', 'пастыр', 'иктори', 'декоратив']  # Можно вынести в конфиг

        for product in products:
            name = product['name'].lower()
            if any(fake in name for fake in fake_keywords):
                print(f"Пропускаем выдуманный продукт: {product['name']}")
                continue
            filtered_products.append(product)

        print(f"После фильтрации осталось продуктов: {len(filtered_products)}")
        return filtered_products

    def _get_demo_products(self) -> List[Dict]:
        """Возвращает демо-продукты когда AI недоступен"""
        if not self.use_demo_data:
            raise ValueError("Демо-данные отключены в настройках")

        demo_products = [
            {
                "name": "Булочка",
                "estimated_weight_g": 80,
                "cooking_method": "выпечка"
            },
            {
                "name": "Мясо",
                "estimated_weight_g": 120,
                "cooking_method": "жарка"
            },
            {
                "name": "Овощи",
                "estimated_weight_g": 100,
                "cooking_method": "свежие"
            }
        ]
        print("📋 Используем демо-продукты")
        return demo_products

    async def get_nutrition_info(self, product_name: str, weight: float, cooking_method: str) -> Dict:
        """Получает информацию о БЖУ для продукта"""

        # Сначала проверяем кэш
        product_hash = self.create_product_hash(product_name, weight, cooking_method)
        cached_data = db.get_cached_product(product_hash)
        if cached_data:
            print(f"✅ Используем кэш для: {product_name}")
            return cached_data

        # Пытаемся найти в локальной базе Open Food Facts
        local_product = db.search_food_facts_product(product_name)
        if local_product:
            print(f"✅ Нашли в локальной базе: {product_name}")
            nutrition_data = self._calculate_from_local_product(local_product, weight)
            db.cache_product(product_hash, product_name, nutrition_data)
            return nutrition_data

        # Пытаемся найти в онлайн базе Open Food Facts
        if self.food_facts_api.enabled:
            print(f"🔍 Ищем в Open Food Facts: {product_name}")
            food_facts_product = self.food_facts_api.search_product(product_name)
            if food_facts_product:
                print(f"✅ Нашли в Open Food Facts: {product_name}")
                db.add_food_facts_product(food_facts_product)
                nutrition_data = self.food_facts_api.calculate_nutrition_for_weight(food_facts_product, weight)
                if nutrition_data:
                    db.cache_product(product_hash, product_name, nutrition_data)
                    return nutrition_data

        # Если нет в Open Food Facts, пробуем AI (если доступен)
        if self.api_key:
            nutrition_data = await self._get_ai_nutrition_info(product_name, weight, cooking_method)
            if nutrition_data:
                return nutrition_data

        # Если все варианты не сработали, используем примерные данные
        if self.use_estimated_data:
            print(f"⚠️ Используем примерные данные для: {product_name}")
            return self._get_estimated_nutrition(product_name, weight, cooking_method)
        else:
            raise ValueError("Все источники данных недоступны")

    def _calculate_from_local_product(self, local_product, weight: float) -> Dict:
        """Рассчитывает БЖУ из локального продукта"""
        return {
            'calories': round(local_product.calories_per_100g * weight / 100, 1),
            'proteins': round(local_product.proteins_per_100g * weight / 100, 1),
            'fats': round(local_product.fats_per_100g * weight / 100, 1),
            'carbs': round(local_product.carbs_per_100g * weight / 100, 1),
            '_source': 'open_food_facts_local'
        }

    async def _get_ai_nutrition_info(self, product_name: str, weight: float, cooking_method: str) -> Optional[Dict]:
        """Получает данные о питании через AI"""
        await self._make_request_with_delay()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",
            "X-Title": "Nutrition Bot"
        }

        nutrition_prompt = Config.NUTRITION_PROMPT_TEMPLATE.format(
            product_name=product_name,
            weight=weight,
            cooking_method=cooking_method
        )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": nutrition_prompt
                }
            ],
            "max_tokens": 500,
            "temperature": 0.1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=Config.REQUEST_TIMEOUT
                ) as response:

                    if response.status == 429:
                        return None

                    if response.status != 200:
                        return None

                    result = await response.json()

                    if 'error' in result:
                        return None

                    response_text = result['choices'][0]['message']['content']
                    nutrition_data = self._clean_json_response(response_text)

                    # Проверяем обязательные поля
                    required_fields = ['calories', 'proteins', 'fats', 'carbs']
                    for field in required_fields:
                        if field not in nutrition_data:
                            nutrition_data[field] = 0.0

                    nutrition_data['_source'] = 'ai'

                    product_hash = self.create_product_hash(product_name, weight, cooking_method)
                    db.cache_product(product_hash, product_name, nutrition_data)

                    return nutrition_data

        except Exception as e:
            print(f"⚠️ Ошибка AI для {product_name}: {e}")
            return None

    def _get_estimated_nutrition(self, product_name: str, weight: float, cooking_method: str) -> Dict:
        """Упрощенные примерные данные как fallback"""
        if not self.use_estimated_data:
            raise ValueError("Примерные данные отключены")

        # Базовые оценки (можно вынести в конфиг)
        estimates = {
            'булочка': {'calories': 3.0, 'proteins': 0.08, 'fats': 0.04, 'carbs': 0.57},
            'хлеб': {'calories': 2.65, 'proteins': 0.09, 'fats': 0.035, 'carbs': 0.49},
            'мясо': {'calories': 2.5, 'proteins': 0.25, 'fats': 0.16, 'carbs': 0},
            'овощ': {'calories': 0.4, 'proteins': 0.015, 'fats': 0.002, 'carbs': 0.08},
            'фрукт': {'calories': 0.6, 'proteins': 0.01, 'fats': 0.003, 'carbs': 0.15},
        }

        product_lower = product_name.lower()
        for key, values in estimates.items():
            if key in product_lower:
                return {
                    'calories': round(values['calories'] * weight, 1),
                    'proteins': round(values['proteins'] * weight, 1),
                    'fats': round(values['fats'] * weight, 1),
                    'carbs': round(values['carbs'] * weight, 1),
                    '_source': 'примерные данные'
                }

        # Дефолтные значения
        return {
            'calories': round(1.5 * weight, 1),
            'proteins': round(0.1 * weight, 1),
            'fats': round(0.08 * weight, 1),
            'carbs': round(0.2 * weight, 1),
            '_source': 'дефолтные данные'
        }

    def create_product_hash(self, product_name: str, weight: float, cooking_method: str) -> str:
        """Создает хеш для кэширования продуктов"""
        data_string = f"{product_name}_{weight}_{cooking_method}".lower()
        return hashlib.md5(data_string.encode()).hexdigest()