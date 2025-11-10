"""
db_fill_database_products.py — chunked parallel prepare + bulk insert

- Читает USDA CSV (food.csv, nutrient.csv, food_nutrient.csv) из архива
- Агрегирует основные нутриенты по fdc_id
- Параллельно (в чанках) готовит product dicts
- Пакетно вставляет новые записи в таблицу food_facts_products (bulk insert)
"""

import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd
from sqlalchemy import insert
from tqdm import tqdm

from db_database_structure import Database, Product
from dotenv import load_dotenv
import shutil

load_dotenv()


# === Настройки ===
ZIP_PATH = os.getenv("ZIP_PATH")
EXTRACT_DIR = os.getenv("EXTRACT_DIR")
MAX_WORKERS = 8
BATCH_SIZE = 2000       # вставлять пачками по N записей в БД
PREPARE_CHUNK = 200000  # сколько записей обрабатывать за один chunk (параллельно)


# ---------------- UTILS ----------------

def extract_zip(zip_path: str, extract_dir: str):
    if not os.path.exists(extract_dir):
        print("📦 Распаковка архива USDA...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        print("✅ Распаковано.")
    else:
        print("📂 Папка уже распакована.")


def find_data_folder(extract_dir: str):
    """Находит подпапку с CSV-файлами (food.csv, nutrient.csv, food_nutrient.csv)"""
    for root, dirs, files in os.walk(extract_dir):
        names = set(f.lower() for f in files)
        if {"food.csv", "nutrient.csv", "food_nutrient.csv"}.issubset(names):
            return root
    raise FileNotFoundError("Не удалось найти food.csv / nutrient.csv / food_nutrient.csv в " + extract_dir)


def _find_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ---------------- LOAD CSV ----------------

def load_usda_tables(extract_dir: str):
    data_dir = find_data_folder(extract_dir)
    print(f"📚 Загрузка CSV из {data_dir}")

    # если большие csv — можно добавить low_memory=False и dtype уточнения
    food = pd.read_csv(os.path.join(data_dir, "food.csv"))
    nutrient = pd.read_csv(os.path.join(data_dir, "nutrient.csv"))
    # предупреждение по mixed types: читаем с low_memory=False
    food_nutrient = pd.read_csv(os.path.join(data_dir, "food_nutrient.csv"), low_memory=False)

    print(f"✅ Загружено: food={len(food)}, nutrient={len(nutrient)}, food_nutrient={len(food_nutrient)}")
    return food, nutrient, food_nutrient


# ---------------- AGGREGATE NUTRIENTS ----------------

def build_nutrition_index(nutrient_df):
    id_col = _find_column(nutrient_df, ["id", "nutrient_id", "nutrientId"])
    name_col = _find_column(nutrient_df, ["name", "nutrient_name", "nutrientName"])
    if id_col is None or name_col is None:
        raise RuntimeError("Не найдены колонки id/name в nutrient.csv")
    return dict(zip(nutrient_df[id_col], nutrient_df[name_col]))


def merge_food_nutrients(food_df, nutrient_df, food_nutrient_df):
    """Собираем calories/proteins/fats/carbs для каждого fdc_id"""
    nutrient_lookup = build_nutrition_index(nutrient_df)

    fn_food_id_col = _find_column(food_nutrient_df, ["fdc_id", "fdcId", "food_id", "id"])
    fn_nutrient_id_col = _find_column(food_nutrient_df, ["nutrient_id", "nutrientId", "id"])
    fn_amount_col = _find_column(food_nutrient_df, ["amount", "value", "nutrient_value"])

    if not fn_food_id_col or not fn_nutrient_id_col or not fn_amount_col:
        raise RuntimeError("Не найдены колонки food_nutrient (fdc_id/nutrient_id/amount)")

    nutrients_by_food = {}

    print("⚙️ Агрегация нутриентов...")
    for row in tqdm(food_nutrient_df.itertuples(index=False), total=len(food_nutrient_df), desc="Индексация нутриентов"):
        try:
            fdc_val = getattr(row, fn_food_id_col)
            nut_id = getattr(row, fn_nutrient_id_col)
            amt = getattr(row, fn_amount_col)
        except AttributeError:
            continue

        try:
            fdc_id = int(fdc_val)
        except Exception:
            continue

        try:
            amount = float(amt) if (amt is not None and str(amt).strip() != "") else 0.0
        except Exception:
            amount = 0.0

        nut_name = nutrient_lookup.get(nut_id, "")
        nut_name_l = str(nut_name).lower()

        if fdc_id not in nutrients_by_food:
            nutrients_by_food[fdc_id] = {"calories": 0.0, "proteins": 0.0, "fats": 0.0, "carbs": 0.0}

        # сопоставляем по подстроке (учитывает разные формулировки)
        if "energy" in nut_name_l or "kilocal" in nut_name_l or "kcal" in nut_name_l:
            nutrients_by_food[fdc_id]["calories"] = amount
        elif "protein" in nut_name_l:
            nutrients_by_food[fdc_id]["proteins"] = amount
        elif "fat" in nut_name_l or "total lipid" in nut_name_l:
            nutrients_by_food[fdc_id]["fats"] = amount
        elif "carbohydrate" in nut_name_l:
            nutrients_by_food[fdc_id]["carbs"] = amount

    print(f"⚙️ Нутриентов собрано для {len(nutrients_by_food)} fdc_id")

    food_id_col = _find_column(food_df, ["fdc_id", "fdcId", "id", "food_id"])
    if food_id_col is None:
        raise RuntimeError("Не найден id-столбец в food.csv (ожидается fdc_id или id)")

    if food_id_col != "fdc_id":
        food_df = food_df.rename(columns={food_id_col: "fdc_id"})

    nut_rows = [{"fdc_id": fid, **vals} for fid, vals in nutrients_by_food.items()]
    nut_df = pd.DataFrame(nut_rows) if nut_rows else pd.DataFrame(columns=["fdc_id", "calories", "proteins", "fats", "carbs"])

    full = pd.merge(food_df, nut_df, on="fdc_id", how="left")
    for col in ["calories", "proteins", "fats", "carbs"]:
        full[col] = full[col].fillna(0.0)

    print(f"✅ Сформировано {len(full)} записей (food + нутриенты)")
    return full


# ---------------- PREPARE RECORD (robust) ----------------

def _safe_str(val):
    """Привести значение к строке, корректно обработав NaN/None"""
    if val is None:
        return ""
    # pandas NaN => float('nan') ; numpy.nan also
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    return str(val)


def _to_float_or_zero(val):
    try:
        if val is None:
            return 0.0
        if pd.isna(val):
            return 0.0
        return float(val)
    except Exception:
        return 0.0


def _prepare_product_record(rec: dict):
    """
    rec — dict (one row from full_df.to_dict(orient='records'))
    Возвращает словарь для вставки в БД или None если нет валидного имени
    """
    try:
        name_raw = rec.get("description") if "description" in rec else rec.get("description_en", "")
    except Exception:
        name_raw = ""

    name = _safe_str(name_raw).strip()
    if not name:
        return None

    name_lower = name.lower()
    categories = _safe_str(rec.get("food_category_id") or rec.get("food_category") or "")
    calories = _to_float_or_zero(rec.get("calories"))
    proteins = _to_float_or_zero(rec.get("proteins"))
    fats = _to_float_or_zero(rec.get("fats"))
    carbs = _to_float_or_zero(rec.get("carbs"))
    now = datetime.now()

    return {
        "product_name": name,
        "product_name_lower": name_lower,
        "categories": categories,
        "calories_per_100g": calories,
        "proteins_per_100g": proteins,
        "fats_per_100g": fats,
        "carbs_per_100g": carbs,
    }


# ---------------- BULK INSERT ----------------

def bulk_insert_products(product_dicts, batch_size=BATCH_SIZE):
    if not product_dicts:
        return 0

    db = Database()
    engine = db.engine

    # load existing lowercase names
    print("🔎 Загружаем существующие product_name_lower из БД (чтобы избежать дублей)...")
    try:
        existing = set(r[0] for r in db.session.query(Product.product_name_lower).all() if r[0])
    except Exception:
        existing = set()

    to_insert = []
    for p in product_dicts:
        pl = p["product_name_lower"]
        if pl in existing:
            continue
        existing.add(pl)
        to_insert.append(p)

    total = len(to_insert)
    if total == 0:
        print("ℹ️ Нет новых записей для вставки в этом чанке.")
        return 0

    inserted = 0
    with engine.begin() as conn:
        for i in range(0, total, batch_size):
            batch = to_insert[i:i+batch_size]
            try:
                conn.execute(insert(Product.__table__), batch)
                inserted += len(batch)
            except Exception as e:
                print(f"⚠️ Ошибка при вставке пачки ({i}..{i+batch_size}): {e}")
                # попытка поштучной вставки
                for rec in batch:
                    try:
                        conn.execute(insert(Product.__table__), rec)
                        inserted += 1
                    except Exception as e2:
                        print("Ошибка вставки записи:", rec.get("product_name", "")[:80], e2)
    print(f"✅ Вставлено {inserted} продуктов из чанка (из {len(product_dicts)} подготовленных)")
    return inserted

# ---------------- Cleanup inserted data ----------------

def cleanup_extracted_files(extract_dir: str):
    """Удаляет распакованные файлы CSV после импорта"""
    if os.path.exists(extract_dir):
        try:
            shutil.rmtree(extract_dir)
            print(f"🗑️ Удалена папка с CSV: {extract_dir}")
        except Exception as e:
            print(f"⚠️ Не удалось удалить папку {extract_dir}: {e}")

# ---------------- MAIN (chunked parallel prepare + immediate bulk insert) ----------------

def main():
    extract_zip(ZIP_PATH, EXTRACT_DIR)
    food_df, nutrient_df, food_nutrient_df = load_usda_tables(EXTRACT_DIR)
    full_df = merge_food_nutrients(food_df, nutrient_df, food_nutrient_df)

    total = len(full_df)
    print(f"🔧 Будет обработано записей: {total}")
    records_iter = full_df.to_dict(orient="records")

    inserted_total = 0

    # process by chunks to keep memory low and avoid creating 2M futures
    for start in range(0, total, PREPARE_CHUNK):
        end = min(start + PREPARE_CHUNK, total)
        chunk = records_iter[start:end] if isinstance(records_iter, list) else full_df.iloc[start:end].to_dict(orient="records")
        print(f"\n🔁 Обработка чанка {start}..{end} (size={len(chunk)}) — параллельная подготовка записей...")
        product_dicts = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            # map вернёт итератор; собираем результаты в список
            for res in tqdm(ex.map(_prepare_product_record, chunk), total=len(chunk), desc="Подготовка записей"):
                if res:
                    product_dicts.append(res)

        print(f"🗂 Готовых product dicts в чанке: {len(product_dicts)} — начинаем bulk insert")
        inserted = bulk_insert_products(product_dicts, batch_size=BATCH_SIZE)
        inserted_total += inserted

    print(f"\n🎉 Готово. Всего вставлено: {inserted_total} записей.")

    # clean up extracted CSVs
    cleanup_extracted_files(EXTRACT_DIR)


if __name__ == "__main__":
    main()
