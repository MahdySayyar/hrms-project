# TEST-STRATEGY-01 — آزمون از specification

Core: UC-01 ورود/دسترسی، UC-02 ثبت/تصمیم، UC-03 محاسبه/snapshot. هر rule به نمونهٔ موفق، شکست و مرز معنادار وصل می‌شود؛ همهٔ ruleهای Extended هنوز پوشش مستقل مثبت/منفی کامل ندارند.

| سطح | ابزار و محل | هدف و حد اعتبار |
|---|---|---|
| قواعد | unittest، tests/test_request_rules.py | 10 آزمون state/نقش/notes؛ بدون HTTP/DB |
| Core integration / HTTP | TestClient + PostgreSQL، tests/test_core_workflows.py | 17 آزمون جریان و خطا؛ شامل هم‌زمانی و rollback |
| مرز معماری | AST، tests/test_architecture_boundaries.py | 2 کنترل وابستگی؛ تنها ماژول تصمیم |
| رگرسیون کل حوزه‌ها | scripts/run_isolated_smoke.py | 98 بررسی HTTP و DB واقعی روی دادهٔ ساختگی |
| بار | Locust، tests/performance/locustfile.py | وزن 4 خواندن/1 نوشتن؛ synthetic employee status؛ lab localhost دارای marker |
| coverage | coverage، app/request_workflow | اندازه‌گیری statement package تصمیم؛ دامنه دقیق در گزارش |
| ساختار مدارک | scripts/check_engineering.py | YAML بدون duplicate، شناسه/پیوند، code symbol و همخوانی DB/model |
| مرورگر و پذیرش انسانی | CUA و جلسهٔ review آینده | سوابق تاریخی 11 بررسی کامل موجود؛ بازبینی انسانی جدید ثبت نشده |

برای integration، PostgresSandbox یک schema با UUID می‌سازد، search_path اتصال را به همان schema محدود و پس از آزمون فقط همان schema را حذف می‌کند. رکورد production تغییر نمی‌کند. لوکاست یک وب روی port مستقل و credentials ساختگی دارد و پیش از write، /instance را تأیید می‌کند. اجرای چند workload هم‌زمان برای مقایسهٔ عملکرد مجاز نیست.

نتیجهٔ اولیهٔ اتصال ناموفق DB در core-environment-unavailable ثبت شده: صفر آزمون؛ شکست business rule نیست. سپس DB پروژه با راه‌انداز موجود روشن و آزمون قبل/بعد اجرا شد.

فرمان‌های تکرار از ریشهٔ پروژه در [README](../../README.md) است. خروجی evidence مسیر جدید می‌خواهد و historical file بازنویسی نمی‌شود. دادهٔ raw/log در artifacts محلی است؛ JSON امن در docs/08-testing/evidence وارد Git می‌شود.

حدود: آزمون 2-thread تضمین همهٔ interleavingها نیست؛ تست load کوتاه پذیرش 500 کاربر نیست؛ پوشش statement جای branch/security review نیست؛ scan کامل OWASP، dependency vulnerability scan، TLS، شکست شبکه، HA و user study انجام نشده‌اند.
