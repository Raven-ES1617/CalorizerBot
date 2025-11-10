from foodfacts.vision_processor import VisionProcessor


class NutritionCalculator:
    def __init__(self):
        self.vision_processor = VisionProcessor()

    async def process_image(self, image_path):
        """
        Основной метод обработки изображения:
        - анализ изображения
        - получение БЖУ для каждого продукта
        - суммирование общих показателей
        """
        try:
            # 1. Анализируем изображение
            products = await self.vision_processor.analyze_food_image(image_path)
            print(f"Найдено продуктов: {len(products)}")  # Для отладки

            results = []
            total = {'calories': 0, 'proteins': 0, 'fats': 0, 'carbs': 0}

            # 2. Для каждого продукта получаем БЖУ
            for product in products:
                print(f"Обрабатываем продукт: {product}")  # Для отладки

                nutrition = await self.vision_processor.get_nutrition_info(
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

    def format_nutrition_response(self, analysis_result):
        """
        Форматирует ответ для пользователя
        """
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
