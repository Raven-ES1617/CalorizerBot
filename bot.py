import os
import logging
# import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class NutritionBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_TOKEN')
        if not self.token:
            raise ValueError("TELEGRAM_TOKEN не найден в .env файле!")

        # Инициализируем компоненты
        try:
            from database import db
            from nutrition_calculator import NutritionCalculator
            from diary_manager import DiaryManager

            self.db = db
            self.nutrition_calculator = NutritionCalculator()
            self.diary_manager = DiaryManager()
            logger.info("✅ Все компоненты инициализированы")

        except Exception as e:
            logger.warning(f"⚠️ Некоторые компоненты не загружены: {e}")
            # Создаем заглушки для тестирования
            self.db = None
            self.nutrition_calculator = None
            self.diary_manager = None

        self.application = None

    def setup_handlers(self):
        """Настройка обработчиков команд"""
        # Базовые команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("test", self.test))

        # Если основные компоненты загружены, добавляем полный функционал
        if self.nutrition_calculator:
            self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
            self.application.add_handler(CommandHandler("diary", self.show_diary))
            self.application.add_handler(CommandHandler("week", self.show_weekly_stats))
            self.application.add_handler(CommandHandler("goals", self.set_goals))
            self.application.add_handler(CommandHandler("delete", self.delete_last_entry))
            logger.info("✅ Полный функционал активирован")
        else:
            logger.warning("⚠️ Бот запущен в ограниченном режиме")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user

        if self.nutrition_calculator:
            welcome_text = (
                f"Привет, {user.first_name}! 👋\n\n"
                "Я - бот для учета питания! Я могу:\n\n"
                "📸 **Анализировать фото еды**\n"
                "📊 **Рассчитывать БЖУ**\n"
                "📅 **Вести дневник питания**\n\n"
                "**Просто отправь мне фото своей еды!** 🍕🥗"
            )
        else:
            welcome_text = (
                f"Привет, {user.first_name}! 👋\n\n"
                "Бот запущен в тестовом режиме.\n"
                "Основной функционал временно недоступен."
            )

        await update.message.reply_text(welcome_text)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает справку"""
        if self.nutrition_calculator:
            help_text = (
                "📋 **Доступные команды:**\n\n"
                "📸 **Отправь фото еды** - анализ БЖУ\n"
                "/diary - Дневник за сегодня\n"
                "/week - Статистика за неделю\n"
                "/goals - Настройка целей\n"
                "/delete - Удалить запись\n"
                "/help - Справка"
            )
        else:
            help_text = (
                "📋 **Доступные команды:**\n\n"
                "/start - Начало работы\n"
                "/help - Справка\n"
                "/test - Тест бота\n\n"
                "⚠️ Основной функционал временно недоступен"
            )

        await update.message.reply_text(help_text)

    async def test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовая команда"""
        user = update.effective_user
        status = "✅ Бот работает нормально\n"

        if self.db:
            status += "✅ База данных подключена\n"
        else:
            status += "❌ База данных не подключена\n"

        if self.nutrition_calculator:
            status += "✅ AI функционал доступен\n"
        else:
            status += "❌ AI функционал недоступен\n"

        await update.message.reply_text(f"Тест бота:\n{status}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик фотографий"""
        if not self.nutrition_calculator:
            await update.message.reply_text("❌ Функционал анализа фото временно недоступен")
            return

        user_id = update.effective_user.id
        processing_message = await update.message.reply_text("🔄 Анализирую фото...")

        try:
            # Скачиваем фото
            photo_file = await update.message.photo[-1].get_file()
            photo_path = f"temp_photo_{user_id}.jpg"
            await photo_file.download_to_drive(photo_path)

            # Анализируем фото
            analysis_result = await self.nutrition_calculator.process_image(photo_path)

            # Добавляем в дневник
            if analysis_result['products']:
                self.diary_manager.add_entry_from_analysis(user_id, analysis_result)

                # Форматируем ответ
                response_text = self.nutrition_calculator.format_nutrition_response(analysis_result)
                await processing_message.edit_text(response_text)

                # Показываем дневник за сегодня
                diary_summary, _ = self.diary_manager.get_daily_summary(user_id)
                await update.message.reply_text(diary_summary)
            else:
                await processing_message.edit_text(
                    "❌ Не удалось проанализировать фото. Попробуйте другое изображение."
                )

            # Удаляем временный файл
            import os
            if os.path.exists(photo_path):
                os.remove(photo_path)

        except Exception as e:
            logger.error(f"Error processing photo: {e}")
            await processing_message.edit_text(
                "❌ Произошла ошибка при анализе фото. "
                "Попробуйте снова или отправьте другое фото."
            )

    async def show_diary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает дневник"""
        if not self.diary_manager:
            await update.message.reply_text("❌ Функционал дневника временно недоступен")
            return

        user_id = update.effective_user.id
        try:
            diary_summary, total = self.diary_manager.get_daily_summary(user_id)
            await update.message.reply_text(diary_summary)
        except Exception as e:
            logger.error(f"Error showing diary: {e}")
            await update.message.reply_text("❌ Ошибка при получении дневника")

    async def show_weekly_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику за неделю"""
        if not self.diary_manager:
            await update.message.reply_text("❌ Функционал статистики временно недоступен")
            return

        user_id = update.effective_user.id
        try:
            weekly_stats = self.diary_manager.get_weekly_stats(user_id)
            await update.message.reply_text(weekly_stats)
        except Exception as e:
            logger.error(f"Error showing weekly stats: {e}")
            await update.message.reply_text("❌ Ошибка при получении статистики")

    async def set_goals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Настройка целей"""
        if not self.db:
            await update.message.reply_text("❌ Функционал настроек временно недоступен")
            return

        await update.message.reply_text("🎯 Настройка целей будет доступна после исправления ошибок")

    async def delete_last_entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет последнюю запись"""
        if not self.diary_manager:
            await update.message.reply_text("❌ Функционал удаления временно недоступен")
            return

        await update.message.reply_text("🗑️ Удаление записей будет доступно после исправления ошибок")

    def run(self):
        """Запускает бота"""
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()

        logger.info("Бот запущен!")
        print("🤖 Бот запущен! Напишите /start в Telegram")
        self.application.run_polling()


if __name__ == "__main__":
    try:
        bot = NutritionBot()
        bot.run()
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        print(f"❌ Ошибка: {e}")