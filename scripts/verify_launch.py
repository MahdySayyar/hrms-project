"""بررسی دسترسی واقعی بعد از پایان فرمان راه‌انداز مستقل."""
import json
import sys
from pathlib import Path

import httpx
from sqlalchemy import func, select

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from app.database import Employee, SessionLocal

with httpx.Client(timeout=5, trust_env=False) as client:
    health = client.get("http://127.0.0.1:8000/health")
    login = client.get("http://127.0.0.1:8000/login")
    protected = client.get("http://127.0.0.1:8000/employees")
with SessionLocal() as db:
    count = db.scalar(select(func.count()).select_from(Employee))
result = {"health_status": health.status_code, "health": health.json(),
          "login_status": login.status_code, "login_is_persian": 'lang="fa"' in login.text,
          "protected_status": protected.status_code, "employee_count": count}
result["passed"] = (result["health_status"] == 200 and result["health"] == {"status": "ok"}
                    and result["login_status"] == 200 and result["login_is_persian"]
                    and result["protected_status"] == 303)
(root / "artifacts/launch-fix-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
if not result["passed"]:
    raise SystemExit("Launch verification failed.")
