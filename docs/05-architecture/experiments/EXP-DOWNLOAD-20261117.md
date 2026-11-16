# EXP-DOWNLOAD — اجرای نسخهٔ قابل دانلود

2026-11-17؛ درخواست مستقیم کاربر برای مخزن عمومی، کانتینرها و اجرای آسان پس از دانلود، سپس ارسال تغییرات آینده به همان مخزن. ADR-14 و اثر FR/BR/UC/طراحی پیش از launcher و تغییر Compose نوشته شدند. فایل‌های Docker قبلی از پیاده‌سازی ADR-10 بازسازی و بررسی شدند. review انسانی و Gate همچنان pending هستند.

مشکل قبل: راهنمای Docker ساخت secret را به `.venv` محلی وابسته کرده بود؛ این پوشه در Git نیست. پس از اصلاح، launcher ویندوز و Bash فقط Docker/Compose را می‌خواهند. کانتینر موقت بدون شبکه، همان initializer را با دو mount محدود اجرا می‌کند؛ `.env` و دادهٔ native mount نمی‌شوند. رمز در محل ساخته می‌شود و فقط مسیر فایل چاپ می‌شود. دو سرویس اصلی همان یک وب و PostgreSQL هستند.

آزمون از کپی تمام فایل‌های قابل انتشار در مسیر دارای فاصله انجام شد؛ `.env`، `.venv`، `.runtime` و Git در کپی اولیه نبودند. project، پورت loopback و volume مخصوص آزمون و دادهٔ seed ساختگی بودند. پس از پایان، کانتینرها و volume فقط همان project پاک شدند؛ فایل‌های raw و نسخه‌های evidence قبلی حفظ شدند.

| بررسی واقعی | نتیجه | شاهد |
|---|---|---|
| نصب تازه، ورود صحیح/غلط، CSRF، تکرار و حفظ volume | 17/17 موفق | [نسخهٔ دانلودی](../../08-testing/evidence/github-download-20261117-b.json) |
| core PostgreSQL داخل image ساخته‌شده از کپی تازه | 50/50 موفق | [core Docker](../../08-testing/evidence/core-docker-github-download-20261117-b.json) |
| پوشش بخش تصمیم درخواست | 86/89 statement، 96.629٪ | [coverage Docker](../../08-testing/evidence/coverage-docker-github-download-20261117-b.json) |
| رگرسیون هشت حوزه | 98/98 بررسی موفق | [regression](../../08-testing/evidence/regression-docker-github-download-20261117-b.json) |
| pipeline آزمون Docker، coverage و pip check | 5/5 مرحله موفق | [pipeline](../../08-testing/evidence/docker-verification-github-download-20261117-b.json) |
| core روی PostgreSQL محلی در schemaهای disposable | 50/50 موفق | [core محلی](../../08-testing/evidence/github-native-core-20261117-a.json) |
| کنترل ساختاری مهندسی | 1556 بررسی موفق | [engineering](../../08-testing/evidence/github-engineering-20261117-c.json) |
| parser نمودارهای Mermaid | 36 منبع بدون خطا | [diagrams](../../08-testing/evidence/github-diagrams-20261117-a.json) |
| فایل‌های انتشار و تاریخچه پیش از اصلاح نهایی launcher | 336 فایل و 214 blob، یافته صفر | [audit اولیه](../../08-testing/evidence/github-publication-audit-20261117-a.json) |

اجرای اول نصب تازه روی 8001 به اشغال پورت برخورد کرد؛ launcher ناموفق متوقف شد و فقط project و volume ساختگی همان آزمون پاک شدند. [شاهد شکست](../../08-testing/evidence/github-download-20261117-a-failure.json) حفظ شده است. انتخاب پورت اختیاری با پیش‌فرض 8001 پیش از کد اصلاح دوم در ADR-14 ثبت شد؛ اجرای دوم از پورت آزاد و project جدا استفاده کرد و موفق شد.

کنترل مهندسی اول دو hash قدیمی برای app/modules.py و specs/architecture.yaml یافت؛ [شکست](../../08-testing/evidence/github-engineering-20261117-a.json) حفظ شد. hashهای متن فعلی تازه شدند و metadata صریحاً می‌گوید reflection قبلی DB حفظ شده و export تازهٔ schema/row ادعا نمی‌شود. کنترل‌های بعدی موفق شدند.

این شاهد بررسی HTTP و DB است؛ آزمایش تازهٔ تصویری مرورگر یا پذیرش انسان نیست. launcher ویندوز واقعاً اجرا و Bash محلی syntax-check شد؛ اجرای کامل Linux در job Docker در GitHub Actions بررسی می‌شود و نتیجه فقط پس از اجرای واقعی قابل گزارش است. CI، گیت‌هاب و همگامی آینده باید از نتیجهٔ actual remote تأیید شوند. معماری یک پردازه و نشست حافظه‌ای، تاریخ میلادی، حقوق آموزشی و نبود migration نسخه‌دار محفوظ‌اند؛ ظرفیت 500 یا HA تأیید نشده است.
