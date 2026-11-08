# زمینهٔ جاری پروژهٔ HRMS

درخواست پایدار کاربر: نسخهٔ ساده و قابل اجرا، سپس مشاهدهٔ مشکل، راه‌حل معماری متناسب و سند واقعی هر تغییر. UI فارسی و RTL و هدف اصلی، تحلیل/طراحی/معماری است.

کد اکنون هشت حوزهٔ HR دارد. این نوبت هر 93 اسلاید چارچوب پروژه خوانده و در مدارک/spec/model/test/traceability تطبیق داده شد. نسخهٔ [زمینهٔ قبلی](history/project-context-before-framework.md) و promptهای تاریخی حفظ شده‌اند؛ محدودهٔ محدود Stage 1 در آن‌ها توصیف گذشته است.

پشته: FastAPI/Uvicorn/Jinja2/SQLAlchemy/psycopg/PostgreSQL، یک پردازهٔ محلی و نشست حافظه‌ای. فقط request review مرز داخلی مستقل دارد. Git baseline=326f77b. معیارهای فنی در [گزارش آزمون](08-testing/report.md) و معماری در [ARCH-01](05-architecture/architecture.md) ثبت‌اند.

پیش از تغییر بعدی، [نیازمندی](02-requirements/requirements.md)، UC/مدل/ADR و اثر تغییر به‌روز و سپس آزمون/کد اجرا شود. .env/credentials/دادهٔ HR صادر نشوند. آزمون و load روی schema مستقل با synthetic records؛ snapshot/evidence قدیمی overwrite نشود.

review انسانی، مشارکت/یادگیری، پذیرش NFRهای واقعی و آزمایش‌های مرحله‌ای هنوز بازند. [OPEN-01](10-final-report/remaining-work.md) قدم‌های باقی‌مانده را می‌دهد. هیچ ادعای کامل بودن Modular Monolith، HA، 500 کاربر یا همهٔ Gateها ندارد.
