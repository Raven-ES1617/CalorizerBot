from vision_processor import VisionProcessor
from database import db


class NutritionCalculator:
    def __init__(self):
        self.vision_processor = VisionProcessor()

    async def process_image(self, image_path):
        """Основной метод обработки изображения"""

        try:
            # 1. Анализируем изображение
            products = await self.vision_processor.analyze_food_image(image_path)
            print(f"Найдено продуктов: {len(products)}")  # Для отладки

            results = []
            total = {'calories': 0, 'proteins': 0, 'fats': 0, 'carbs': 0}

            # 2. Для каждого продукта получаем БЖУ
            for product in products:
                print(f"Обрабатываем продукт: {product}")  # Для отладки

                nutrition = await self.get_product_nutrition(
                    product['name'],
                    product['estimated_weight_g'],
                    product.get('cooking_method', 'не указано')
                )

                product_data = {
                    'product_name': product['name'],
                    'estimated_weight': product['estimated_weight_g'],
                    'cooking_method': product.get('cooking_method', 'не указано'),
                    **nutrition
                }

                results.append(product_data)

                # Суммируем общие показатели
                for key in total:
                    total[key] += nutrition.get(key, 0)

            return {
                'products': results,
                'total': total
            }

        except Exception as e:
            print(f"Ошибка в process_image: {e}")  # Для отладки
            raise

    async def get_product_nutrition(self, product_name, weight, cooking_method):
        """Получает БЖУ для продукта, используя кэш если возможно"""

        # Проверяем кэш
        product_hash = self.vision_processor.create_product_hash(
            product_name, weight, cooking_method
        )

        cached_data = db.get_cached_product(product_hash)
        if cached_data:
            print(f"Используем кэш для: {product_name}")  # Для отладки
            return cached_data

        # Если нет в кэше, запрашиваем у AI
        print(f"Запрашиваем данные для: {product_name}")  # Для отладки
        nutrition_data = await self.vision_processor.get_nutrition_info(
            product_name, weight, cooking_method
        )

        # Сохраняем в кэш
        db.cache_product(product_hash, product_name, nutrition_data)

        return nutrition_data

    def format_nutrition_response(self, analysis_result):
        """Форматирует ответ для пользователя"""

        if not analysis_result['products']:
            return "❌ Не удалось определить продукты на фото. Попробуйте другое фото."

        products_text = "📊 **Результаты анализа:**\n\n"

        for i, product in enumerate(analysis_result['products'], 1):
            products_text += (
                f"**{i}. {product['product_name']}** ({product['estimated_weight']}г)\n"
                f"   🍳 {product['cooking_method']}\n"
                f"   🔥 {product['calories']:.1f} ккал\n"
                f"   🥚 Белки: {product['proteins']:.1f}г\n"
                f"   🥑 Жиры: {product['fats']:.1f}г\n"
                f"   🍚 Углеводы: {product['carbs']:.1f}г\n\n"
            )

        total = analysis_result['total']
        products_text += (
            f"**📈 ИТОГО за прием пищи:**\n"
            f"🔥 {total['calories']:.1f} ккал\n"
            f"🥚 Белки: {total['proteins']:.1f}г\n"
            f"🥑 Жиры: {total['fats']:.1f}г\n"
            f"🍚 Углеводы: {total['carbs']:.1f}г"
        )

        return products_text