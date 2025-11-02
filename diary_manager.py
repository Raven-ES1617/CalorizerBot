from datetime import datetime, timedelta
from database import db


class DiaryManager:
    def __init__(self):
        self.db = db

    def add_entry_from_analysis(self, user_id, analysis_result):
        """Добавляет записи из результата анализа"""
        entries = []
        for product in analysis_result['products']:
            entry_data = {
                'product_name': product['product_name'],
                'calories': product['calories'],
                'proteins': product['proteins'],
                'fats': product['fats'],
                'carbs': product['carbs'],
                'estimated_weight': product['estimated_weight']
            }
            entry = self.db.add_diary_entry(user_id, entry_data)
            entries.append(entry)
        return entries

    def get_daily_summary(self, user_id, date=None):
        """Возвращает сводку за день"""
        if date is None:
            date = datetime.now().date()

        entries = self.db.get_daily_entries(user_id, date)
        user = self.db.get_user(user_id)

        total = {'calories': 0, 'proteins': 0, 'fats': 0, 'carbs': 0}
        entries_text = []

        for entry in entries:
            total['calories'] += entry.calories
            total['proteins'] += entry.proteins
            total['fats'] += entry.fats
            total['carbs'] += entry.carbs

            entries_text.append(
                f"• {entry.product_name} ({entry.estimated_weight}g) - "
                f"{entry.calories:.1f} ккал"
            )

        # Проценты от цели
        calorie_percent = (total['calories'] / user.daily_calorie_goal * 100) if user.daily_calorie_goal > 0 else 0
        protein_percent = (total['proteins'] / user.daily_protein_goal * 100) if user.daily_protein_goal > 0 else 0
        fat_percent = (total['fats'] / user.daily_fat_goal * 100) if user.daily_fat_goal > 0 else 0
        carb_percent = (total['carbs'] / user.daily_carb_goal * 100) if user.daily_carb_goal > 0 else 0

        summary = (
                f"📅 **Дневник питания за {date.strftime('%d.%m.%Y')}**\n\n"
                f"**Продукты:**\n" + "\n".join(entries_text) + "\n\n"
                                                               f"**📊 Сводка:**\n"
                                                               f"🔥 Калории: {total['calories']:.1f}/{user.daily_calorie_goal} ({calorie_percent:.1f}%)\n"
                                                               f"🥚 Белки: {total['proteins']:.1f}г/{user.daily_protein_goal}г ({protein_percent:.1f}%)\n"
                                                               f"🥑 Жиры: {total['fats']:.1f}г/{user.daily_fat_goal}г ({fat_percent:.1f}%)\n"
                                                               f"🍚 Углеводы: {total['carbs']:.1f}г/{user.daily_carb_goal}г ({carb_percent:.1f}%)\n"
        )

        return summary, total

    def get_weekly_stats(self, user_id):
        """Возвращает статистику за неделю"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)

        weekly_data = []
        current_date = start_date

        while current_date <= end_date:
            entries = self.db.get_daily_entries(user_id, current_date)
            day_total = {'calories': 0, 'proteins': 0, 'fats': 0, 'carbs': 0}

            for entry in entries:
                day_total['calories'] += entry.calories
                day_total['proteins'] += entry.proteins
                day_total['fats'] += entry.fats
                day_total['carbs'] += entry.carbs

            weekly_data.append({
                'date': current_date,
                'total': day_total
            })
            current_date += timedelta(days=1)

        # Форматируем ответ
        stats_text = "📈 **Статистика за неделю:**\n\n"

        for day in weekly_data:
            stats_text += (
                f"**{day['date'].strftime('%d.%m')}**: "
                f"{day['total']['calories']:.0f} ккал\n"
            )

        # Средние значения
        avg_calories = sum(day['total']['calories'] for day in weekly_data) / len(weekly_data)
        avg_proteins = sum(day['total']['proteins'] for day in weekly_data) / len(weekly_data)
        avg_fats = sum(day['total']['fats'] for day in weekly_data) / len(weekly_data)
        avg_carbs = sum(day['total']['carbs'] for day in weekly_data) / len(weekly_data)

        stats_text += (
            f"\n**📊 Средние значения:**\n"
            f"🔥 {avg_calories:.1f} ккал/день\n"
            f"🥚 {avg_proteins:.1f}г белков/день\n"
            f"🥑 {avg_fats:.1f}г жиров/день\n"
            f"🍚 {avg_carbs:.1f}г углеводов/день"
        )

        return stats_text

    def delete_user_entry(self, user_id, entry_id):
        """Удаляет запись пользователя"""
        return self.db.delete_entry(entry_id, user_id)