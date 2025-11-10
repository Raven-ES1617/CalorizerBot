# test_translation.py
import asyncio
import json
from deep_translator import GoogleTranslator

# -----------------------------
# Асинхронный перевод через deep-translator
# -----------------------------
async def translate_text(text: str, src='auto', dest='en') -> str:
    """
    Асинхронный перевод текста через deep-translator.
    """
    try:
        translated = await asyncio.to_thread(GoogleTranslator, source=src, target=dest)
        result = await asyncio.to_thread(translated.translate, text)
        return result.lower().strip()
    except Exception as e:
        print(f"⚠️ Ошибка перевода '{text}': {e}")
        return text.lower().strip()


# -----------------------------
# Функция имитации обработки БЖУ ответа модели
# -----------------------------
def process_nutrition_response(response):
    """
    Обработка ответа модели, который может быть строкой JSON или словарём.
    Возвращает dict с ключами: calories, proteins, fats, carbs
    """
    if isinstance(response, str):
        try:
            nutrition_data = json.loads(response)
        except json.JSONDecodeError:
            print("⚠️ Невалидный JSON, используем пустые значения")
            nutrition_data = {}
    elif isinstance(response, dict):
        nutrition_data = response
    else:
        nutrition_data = {}

    for f in ['calories', 'proteins', 'fats', 'carbs']:
        nutrition_data.setdefault(f, 0.0)

    return nutrition_data


# -----------------------------
# Тестовая функция
# -----------------------------
async def test_translation_and_nutrition():
    test_words = [
        "булка", "мясо", "овощи", "фрукт", "булочка для бургера", "картофель фри"
    ]

    for word in test_words:
        translated = await translate_text(word)
        print(f"{word} → {translated}")


if __name__ == "__main__":
    asyncio.run(test_translation_and_nutrition())
