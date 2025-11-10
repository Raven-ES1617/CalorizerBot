from datetime import datetime, timedelta
from db_database_structure import db, Product


class DiaryManager:
    def __init__(self):
        self.db = db

    def add_entry_from_analysis(self, user_id, analysis_result):
        """Добавляет записи из результата анализа"""
        entries = []
        for product in analysis_result['products']:
            # Ищем продукт в БД
            product_record = self.db.session.query(Product).filter(
                Product.product_name_lower == product['product_name'].lower()
            ).first()

            if not product_record:
                # Создаем продукт, если его нет
                product_record = Product(
                    product_name=product['product_name'],
                    product_name_lower=product['product_name'].lower(),
                    calories_per_100g=product.get('calories', 0.0),
                    proteins_per_100g=product.get('proteins', 0.0),
                    fats_per_100g=product.get('fats', 0.0),
                    carbs_per_100g=product.get('carbs', 0.0),
                )
                self.db.session.add(product_record)
                self.db.session.commit()

            # Формируем запись в дневник
            entry_data = {
                'product_id': product_record.id,
                'calories': product.get('calories', 0.0),
                'proteins': product.get('proteins', 0.0),
                'fats': product.get('fats', 0.0),
                'carbs': product.get('carbs', 0.0),
                'estimated_weight': product.get('estimated_weight', 0.0)
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
            total['calories'] += entry.calories or 0
            total['proteins'] += entry.proteins or 0
            total['fats'] += entry.fats or 0
            total['carbs'] += entry.carbs or 0

            product_name = entry.product.product_name if entry.product else "Неизвестный продукт"
            entries_text.append(
                f"• {product_name} ({entry.estimated_weight} г) - {entry.calories:.1f} ккал"
            )

        calorie_percent = (total['calories'] / user.daily_calorie_goal * 100) if user.daily_calorie_goal else 0
        protein_percent = (total['proteins'] / user.daily_protein_goal * 100) if user.daily_protein_goal else 0
        fat_percent = (total['fats'] / user.daily_fat_goal * 100) if user.daily_fat_goal else 0
        carb_percent = (total['carbs'] / user.daily_carb_goal * 100) if user.daily_carb_goal else 0

        summary = (
            f"📅 **Дневник питания за {date.strftime('%d.%m.%Y')}**\n\n"
            f"**Продукты:**\n" + ("\n".join(entries_text) if entries_text else "Записей нет") +
            "\n\n"
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
                day_total['calories'] += entry.calories or 0
                day_total['proteins'] += entry.proteins or 0
                day_total['fats'] += entry.fats or 0
                day_total['carbs'] += entry.carbs or 0

            weekly_data.append({
                'date': current_date,
                'total': day_total
            })
            current_date += timedelta(days=1)

        stats_text = "📈 **Статистика за неделю:**\n\n"
        for day in weekly_data:
            stats_text += f"**{day['date'].strftime('%d.%m')}**: {day['total']['calories']:.0f} ккал\n"

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
