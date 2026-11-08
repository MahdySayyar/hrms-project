"""ساخت نقش و پایگاه اختصاصی بدون تغییر پایگاه‌های دیگر."""
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg
from dotenv import load_dotenv
from psycopg import sql

root = Path(__file__).resolve().parent.parent
load_dotenv(root / ".env")
url = urlsplit(os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1))
if url.hostname != "127.0.0.1" or url.port != 55432:
    raise RuntimeError("This setup script configures only the project-local PostgreSQL on 127.0.0.1:55432.")
username, password, database = unquote(url.username), unquote(url.password), url.path.lstrip("/")
superuser_password = (root / ".runtime/postgres-superuser.secret").read_text(encoding="utf-8").strip()
with psycopg.connect(host="127.0.0.1", port=55432, dbname="postgres", user="postgres", password=superuser_password, autocommit=True) as connection:
    if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,)).fetchone():
        connection.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Identifier(username), sql.Literal(password)))
    if not connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone():
        connection.execute(sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(sql.Identifier(database), sql.Identifier(username)))
with psycopg.connect(host="127.0.0.1", port=55432, dbname=database, user=username, password=password) as connection:
    connection.execute("SELECT 1")
print("Project database and limited application role are ready; existing data preserved.")
