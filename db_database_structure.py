# db_database_structure.py
import os
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    Text, ForeignKey
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

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

    diary_entries = relationship("DiaryEntry", back_populates="user")


class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(500), index=True)
    product_name_lower = Column(String(500), index=True)
    categories = Column(Text)

    calories_per_100g = Column(Float)
    proteins_per_100g = Column(Float)
    fats_per_100g = Column(Float)
    carbs_per_100g = Column(Float)

    diary_entries = relationship("DiaryEntry", back_populates="product")


class DiaryEntry(Base):
    __tablename__ = 'diary_entries'

    entry_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    # FIXED: correct table name here (was "food_facts_products.id" which does not exist)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

    date = Column(DateTime, default=datetime.now)
    calories = Column(Float)
    proteins = Column(Float)
    fats = Column(Float)
    carbs = Column(Float)
    estimated_weight = Column(Float)
    photo_path = Column(String(500))

    user = relationship("User", back_populates="diary_entries")
    product = relationship("Product", back_populates="diary_entries")


class Database:
    def __init__(self):
        os.makedirs('data', exist_ok=True)
        self.engine = create_engine("sqlite:///data/nutrition_bot.db")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    # ---------------- USERS ----------------

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

    # ---------------- DIARY ----------------

    def add_diary_entry(self, user_id, product_data):
        entry = DiaryEntry(
            user_id=user_id,
            product_id=product_data.get('product_id'),
            calories=product_data.get('calories'),
            proteins=product_data.get('proteins'),
            fats=product_data.get('fats'),
            carbs=product_data.get('carbs'),
            estimated_weight=product_data.get('estimated_weight', 0)
        )
        self.session.add(entry)
        self.session.commit()
        return entry

    def get_daily_entries(self, user_id, date=None):
        if date is None:
            date = datetime.now().date()

        return self.session.query(DiaryEntry).filter(
            DiaryEntry.user_id == user_id,
            DiaryEntry.date >= datetime.combine(date, datetime.min.time()),
            DiaryEntry.date < datetime.combine(date, datetime.max.time())
        ).all()

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

    # ---------------- STATS ----------------
    def get_stats(self):
        """Return basic DB stats as a dict."""
        total_products = self.session.query(Product).count()
        total_users = self.session.query(User).count()
        total_entries = self.session.query(DiaryEntry).count()
        return {
            "total_products": total_products,
            "total_users": total_users,
            "total_entries": total_entries
        }

# single shared instance used by other scripts
db = Database()
