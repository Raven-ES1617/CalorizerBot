from typing import Any

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text  # , JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# from sqlalchemy import func
from datetime import datetime
import os
import json

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    username = Column(String(100))
    daily_calorie_goal = Column(Integer, default=2000)
    daily_protein_goal = Column(Integer, default=150)
    daily_fat_goal = Column(Integer, default=70)
    daily_carb_goal = Column(Integer, default=250)
    created_at = Column(DateTime, default=datetime.now)


class DiaryEntry(Base):
    __tablename__ = 'diary_entries'

    entry_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    date = Column(DateTime, default=datetime.now)
    product_name = Column(String(200))
    calories = Column(Float)
    proteins = Column(Float)
    fats = Column(Float)
    carbs = Column(Float)
    estimated_weight = Column(Float)
    photo_path = Column(String(500))


class ProductCache(Base):
    __tablename__ = 'products_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_hash = Column(String(64), unique=True)
    product_name = Column(String(200))
    nutrition_data = Column(Text)  # JSON как текст
    created_at = Column(DateTime, default=datetime.now)


class FoodFactsProduct(Base):
    __tablename__ = 'food_facts_products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(500), index=True)
    product_name_lower = Column(String(500), index=True)
    barcode = Column(String(100), unique=True, nullable=True)
    brand = Column(String(200))
    categories = Column(Text)
    calories_per_100g = Column(Float)
    proteins_per_100g = Column(Float)
    fats_per_100g = Column(Float)
    carbs_per_100g = Column(Float)
    image_url = Column(String(500))
    data_source = Column(String(100), default='open_food_facts')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Database:
    def __init__(self):
        os.makedirs('data', exist_ok=True)
        self.engine = create_engine(f'sqlite:///data/nutrition_bot.db')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def get_user(self, user_id):
        user = self.session.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(user_id=user_id)
            self.session.add(user)
            self.session.commit()
        return user

    def update_user_goals(self, user_id, goals):
        user = self.get_user(user_id)
        for key, value in goals.items():
            if hasattr(user, key):
                setattr(user, key, value)
        self.session.commit()

    def add_diary_entry(self, user_id, product_data):
        entry = DiaryEntry(
            user_id=user_id,
            product_name=product_data['product_name'],
            calories=product_data['calories'],
            proteins=product_data['proteins'],
            fats=product_data['fats'],
            carbs=product_data['carbs'],
            estimated_weight=product_data.get('estimated_weight', 0)
        )
        self.session.add(entry)
        self.session.commit()
        return entry

    def get_daily_entries(self, user_id, date=None):
        if date is None:
            date = datetime.now().date()

        entries = self.session.query(DiaryEntry).filter(
            DiaryEntry.user_id == user_id,
            DiaryEntry.date >= datetime.combine(date, datetime.min.time()),
            DiaryEntry.date < datetime.combine(date, datetime.max.time())
        ).all()
        return entries

    def delete_entry(self, entry_id, user_id):
        entry = self.session.query(DiaryEntry).filter(
            DiaryEntry.entry_id == entry_id,
            DiaryEntry.user_id == user_id
        ).first()
        if entry:
            self.session.delete(entry)
            self.session.commit()
            return True
        return False

    def cache_product(self, product_hash, product_name, nutrition_data):
        import json
        cache = ProductCache(
            product_hash=product_hash,
            product_name=product_name,
            nutrition_data=json.dumps(nutrition_data)
        )
        try:
            self.session.add(cache)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            # Если запись уже существует, игнорируем ошибку
            if "UNIQUE constraint failed" not in str(e):
                raise e

    def get_cached_product(self, product_hash):
        cache: Any | None = self.session.query(ProductCache).filter(
            ProductCache.product_hash == product_hash
        ).first()
        if cache:
            return json.loads(cache.nutrition_data)
        return None

    # Новые методы для Open Food Facts
    def add_food_facts_product(self, product_data):
        """Добавляет продукт из Open Food Facts в базу"""
        try:
            # Проверяем существование по штрих-коду
            if product_data.get('barcode'):
                existing = self.session.query(FoodFactsProduct).filter(
                    FoodFactsProduct.barcode == product_data['barcode']
                ).first()
                if existing:
                    return existing

            # Или по названию (без учета регистра)
            product_name_lower = product_data['product_name'].lower()
            existing = self.session.query(FoodFactsProduct).filter(
                FoodFactsProduct.product_name_lower == product_name_lower
            ).first()
            if existing:
                return existing

            # Создаем новый продукт
            product = FoodFactsProduct(
                product_name=product_data['product_name'],
                product_name_lower=product_name_lower,
                barcode=product_data.get('barcode'),
                brand=product_data.get('brand', ''),
                categories=product_data.get('categories', ''),
                calories_per_100g=product_data['calories'] or 0,
                proteins_per_100g=product_data['proteins'] or 0,
                fats_per_100g=product_data['fats'] or 0,
                carbs_per_100g=product_data['carbs'] or 0,
                image_url=product_data.get('image_url')
            )

            self.session.add(product)
            self.session.commit()
            return product

        except Exception as e:
            self.session.rollback()
            print(f"Ошибка добавления продукта в базу: {e}")
            return None

    def search_food_facts_product(self, product_name):
        """Ищет продукт в локальной базе по названию"""
        try:
            product_name_lower = product_name.lower()

            # Ищем точное совпадение
            product = self.session.query(FoodFactsProduct).filter(
                FoodFactsProduct.product_name_lower == product_name_lower
            ).first()

            if product:
                return product

            # Ищем частичное совпадение
            products = self.session.query(FoodFactsProduct).filter(
                FoodFactsProduct.product_name_lower.contains(product_name_lower)
            ).all()

            if products:
                # Возвращаем наиболее релевантный (самое короткое название)
                return min(products, key=lambda x: len(x.product_name))

            return None

        except Exception as e:
            print(f"Ошибка поиска продукта в базе: {e}")
            return None

    def get_food_facts_stats(self):
        """Возвращает статистику по базе продуктов"""
        total_products = self.session.query(FoodFactsProduct).count()
        products_with_barcode = self.session.query(FoodFactsProduct).filter(
            FoodFactsProduct.barcode.isnot(None)
        ).count()

        return {
            'total_products': total_products,
            'products_with_barcode': products_with_barcode
        }


# Глобальная instance базы данных
db = Database()