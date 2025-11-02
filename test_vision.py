import asyncio
# import os
from vision_processor import VisionProcessor


async def test_vision():
    """Тестирует работу vision процессора"""
    processor = VisionProcessor()

    # Проверяем наличие API ключа
    if not processor.api_key:
        print("❌ OPENROUTER_API_KEY не установлен")
        print("✅ Но бот будет использовать примерные данные")
        return

    print("✅ OPENROUTER_API_KEY найден")

    # Тестируем анализ питания (без фото)
    try:
        test_nutrition = await processor.get_nutrition_info(
            "курица отварная", 200, "варка"
        )
        print(f"✅ Тест питания прошел: {test_nutrition}")
    except Exception as e:
        print(f"❌ Тест питания не прошел: {e}")


if __name__ == "__main__":
    asyncio.run(test_vision())