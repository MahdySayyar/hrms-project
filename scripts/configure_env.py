"""ایجاد تنظیمات محلی فقط در صورت نبودن فایل؛ هیچ تنظیم قبلی بازنویسی نمی‌شود."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env_file = root / ".env"
if env_file.exists():
    print("Existing .env preserved.")
else:
    db_password = secrets.token_urlsafe(24)
    admin_password = secrets.token_urlsafe(14)
    env_file.write_text(
        f"DATABASE_URL=postgresql+psycopg://hrms_app:{db_password}@127.0.0.1:55432/hrms_stage1\n"
        "ADMIN_USERNAME=hradmin\n"
        f"ADMIN_PASSWORD={admin_password}\n"
        "ADMIN_DISPLAY_NAME=مدیر منابع انسانی\n"
        "SESSION_HOURS=8\nCOOKIE_SECURE=false\nINSTANCE_ID=hrms-local-1\n",
        encoding="utf-8",
    )
    print("Created .env with unique local passwords. Demo login is stored there.")
