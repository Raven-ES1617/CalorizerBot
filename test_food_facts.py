from food_facts_api import OpenFoodFactsAPI
from database import db


def test_food_facts():
    api = OpenFoodFactsAPI()

    # Тестируем поиск продуктов
    test_products = ["яблоко", "хлеб", "молоко"]

    for product_name in test_products:
        print(f"🔍 Ищем: {product_name}")
        product = api.search_product(product_name)

        if product:
            print(f"✅ Найдено: {product['product_name']}")
            print(f"   Калории: {product['calories']} на 100г")

            # Сохраняем в базу
            saved = db.add_food_facts_product(product)
            if saved:
                print(f"💾 Сохранено в базу: {saved.product_name}")
        else:
            print(f"❌ Не найдено: {product_name}")

        print()


if __name__ == "__main__":
    test_food_facts()

    # Показываем статистику
    stats = db.get_food_facts_stats()
    print(f"📊 Всего продуктов в базе: {stats['total_products']}")