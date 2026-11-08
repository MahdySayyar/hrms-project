"""ارتقای یک‌بارهٔ داده‌های ساخت همین مرحله؛ بدون حذف یا بازنشانی رکوردها."""
import sys
from pathlib import Path
from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import engine

with engine.begin() as connection:
    inspector = inspect(connection)
    for table in ("branches", "units", "positions", "employees"):
        if "seed_key" not in {column["name"] for column in inspector.get_columns(table)}:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN seed_key VARCHAR(32) UNIQUE"))
print("Development seed keys ready; records preserved.")
