import requests
# import json
import logging
from typing import Dict, Optional, Any
from config import Config

logger = logging.getLogger(__name__)


class OpenFoodFactsAPI:
    def __init__(self):
        self.base_url = Config.OPEN_FOOD_FACTS_BASE_URL
        self.search_url = Config.OPEN_FOOD_FACTS_SEARCH_URL
        self.enabled = Config.OPEN_FOOD_FACTS_ENABLED

    def search_product(self, product_name: str, lang: str = 'ru') -> Optional[Dict]:
        """Ищет продукт в базе Open Food Facts"""
        if not self.enabled:
            logger.info("Open Food Facts отключен в настройках")
            return None

        try:
            params = {
                'search_terms': product_name,
                'json': 1,
                'page_size': 5,
                'lc': lang
            }

            response = requests.get(self.search_url, params=params, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()

            data = response.json()

            if data.get('products'):
                product = data['products'][0]
                return self._parse_product_data(product)
            else:
                logger.info(f"Продукт не найден: {product_name}")
                return None

        except Exception as e:
            logger.error(f"Ошибка поиска продукта {product_name}: {e}")
            return None

    def get_product_by_barcode(self, barcode: str) -> Optional[Dict]:
        """Получает продукт по штрих-коду"""
        if not self.enabled:
            return None

        try:
            url = f"{self.base_url}/product/{barcode}.json"
            response = requests.get(url, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()

            data = response.json()

            if data.get('product'):
                return self._parse_product_data(data['product'])
            else:
                return None

        except Exception as e:
            logger.error(f"Ошибка получения продукта по штрих-коду {barcode}: {e}")
            return None

    def _parse_product_data(self, product_data: Dict) -> Dict:
        """Парсит данные продукта из API"""
        product_name = (
                product_data.get('product_name_ru') or
                product_data.get('product_name') or
                'Неизвестный продукт'
        )

        nutriments = product_data.get('nutriments', {})

        nutrition_data = {
            'product_name': product_name,
            'calories': nutriments.get('energy-kcal_100g') or nutriments.get('energy-kcal'),
            'proteins': nutriments.get('proteins_100g'),
            'fats': nutriments.get('fat_100g'),
            'carbs': nutriments.get('carbohydrates_100g'),
            'sugars': nutriments.get('sugars_100g'),
            'fiber': nutriments.get('fiber_100g'),
            'salt': nutriments.get('salt_100g'),
            'barcode': product_data.get('code'),
            'brand': product_data.get('brands', ''),
            'categories': product_data.get('categories', ''),
            'image_url': product_data.get('image_url')
        }

        # Очищаем None значения
        for key in ['calories', 'proteins', 'fats', 'carbs']:
            if nutrition_data[key] is None:
                nutrition_data[key] = 0.0

        return nutrition_data

    def calculate_nutrition_for_weight(self, product_data: Dict, weight_grams: float) -> dict[str, str | Any] | None:
        """Пересчитывает БЖУ для указанного веса"""
        if not product_data:
            return None

        multiplier = weight_grams / 100.0

        result = {
            'calories': round(product_data['calories'] * multiplier, 1),
            'proteins': round(product_data['proteins'] * multiplier, 1),
            'fats': round(product_data['fats'] * multiplier, 1),
            'carbs': round(product_data['carbs'] * multiplier, 1),
            '_source': 'open_food_facts'
        }

        return result