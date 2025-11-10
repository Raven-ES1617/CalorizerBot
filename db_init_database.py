# db_init_database.py
from db_database_structure import db

def init_database():
    """Инициализирует базу данных и создает таблицы"""
    print("✅ База данных инициализирована")
    stats = db.get_stats()
    print(f"📊 Статистика базы: {stats['total_products']} продуктов")

if __name__ == "__main__":
    init_database()
