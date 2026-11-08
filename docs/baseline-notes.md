# یادداشت معماری و baseline جاری

نسخهٔ اولیهٔ این سند در [history](history/stage01-baseline-notes.md) محفوظ است. baseline کاربردی پیش از framework در commit 326f77b و snapshot baseline-before-framework-20261108 حفظ شد؛ Stage 1 archive قدیمی تغییر نکرد.

واقعیت فعلی: یک FastAPI/Uvicorn با Jinja2، SQLAlchemy و PostgreSQL محلی، نشست memory. main.py و modules.py اکثر قواعد را مستقیم اجرا می‌کنند. فقط تصمیم درخواست مرز Domain/Service/Repository دارد؛ [ARCH-01](05-architecture/architecture.md).

نقش‌های admin/hr/viewer، scope شعبه/واحد، audit و assignment history موجودند؛ بنابراین محدودیت‌های «فقط یک نقش» و «بدون تاریخچه» در سند اولیه دیگر وضعیت جاری نیستند. گزارش دوره و محاسبهٔ اولیهٔ حقوق تاریخی هنوز از مقادیر جاری استفاده می‌کنند.

[CR-01](10-final-report/changes/CR-01.md) یک اصلاح واقعی با spec و تست قبل/بعد دارد؛ این اصلاح بهبود RPS یا رفع اشباع کاربران نیست. [EXP-00](08-testing/report.md) بار سبک native را اندازه گرفت؛ [EXP-01..09](05-architecture/progressive-experiments.md) مسیر container، جداسازی، replica/failure، نشست/cache، gateway و worker آینده است.

برای هر آزمایش، topology/commit/data/load/duration/resources/commands/raw metrics/failure/limits ثبت و پس از تغییر، همان بار تکرار شود. خود snapshot یا نصب ابزار، اجرای experiment نیست.
