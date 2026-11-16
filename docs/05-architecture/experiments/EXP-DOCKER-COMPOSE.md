# EXP-DOCKER-COMPOSE — شاهد مستقل اجرای Docker

2026-11-16؛ درخواست مستقیم کاربر برای اجرای کانتینرها. ADR-10، architecture، UC-01، طراحی و مدل deployment پیش از کد این گام نوشته شدند؛ این گزارش نتیجه پس از اجرای واقعی تهیه شده است. review انسانی و Gate بازند.

پیش از اجرا Dockerfile موجود صفر بایت و daemon خاموش بود؛ هیچ کانتینر HRMS وجود نداشت. Docker Desktop با CLI روشن شد؛ image با Python 3.12 و requirements-lock ساخته شد و دو سرویس در project `hrms-docker` اجرا شدند. PostgreSQL 17.6، شبکه/volume تازه و secretهای جدید فقط runtime؛ app/قالب/static allowlist، بدون .env/داده/credential native در image. وب غیر root و یک Uvicorn PID 1 است. منابع نام و hash در evidence ثبت شده‌اند.

| بررسی | نتیجه | شاهد |
|---|---|---|
| استقرار، ورود/CSRF، volume و حفظ native | 19/19 موفق؛ دو کانتینر running/healthy | [deployment](../../08-testing/evidence/docker-deployment-20261116-a.json) |
| Core در Docker/PostgreSQL | 41/41 موفق در schema disposable | [core](../../08-testing/evidence/core-docker-20261116-b.json) |
| coverage بخش تصمیم | 86/89، 96.629٪ | [coverage](../../08-testing/evidence/coverage-docker-20261116-b.json) |
| رگرسیون هشت حوزه | 98/98 assertion موفق | [regression](../../08-testing/evidence/regression-docker-20261116-a.json) |
| secret/exec contract | 2/2 آزمون مستقیم موفق و در Core دوباره بررسی شدند | [entrypoint](../../08-testing/evidence/docker-entrypoint-20261116-a.json) |
| کنترل ساختاری و source freshness | 1438 بررسی موفق پیش از تکمیل همین گزارش | [engineering](../../08-testing/evidence/engineering-docker-20261116-a.json) |
| parse مدل‌ها | 33 منبع/نمودار بدون خطا، بدون review تصویری | [diagrams](../../08-testing/evidence/diagrams-docker-20261116-a.json) |

در اجرای verifier اول همهٔ 41 test و 98 regression و coverage/pip موفق بودند، ولی نوشتن JSON core به‌علت نبود Git در image متوقف شد؛ [pipeline ناموفق](../../08-testing/evidence/docker-verification-20261116-a.json) و log خام حفظ شدند. run_core_checks برای نبود Git اصلاح شد و commit را null و source_revision_available=false گزارش می‌کند؛ commit یا وجود checkout اختراع نمی‌شود. image ID و hash deployment در شاهد مستقل هستند. اجرای دوم، core/publication و coverage/pip را تکرار کرد و [چهار مرحلهٔ آن موفق بود](../../08-testing/evidence/docker-verification-20261116-b.json)؛ رگرسیون فعلی از اجرای اول معتبر است و دوباره اجرا نشد.

حفظ داده با sentinel ساختگی در schema یکتای جدا بررسی شد: توقف دو سرویس و شروع با همان volume، سپس مقدار sentinel صحیح بود و schema آزمایش حذف شد. حساب/seed نمونهٔ همان DB برای login صحیح/غلط، cookie rotation و logout/CSRF بررسی شد. native روی 8000 از این عملیات خارج بود و همچنان healthy است. رکورد واقعی HR، credential یا .env صادر نشد.

کانتینر verifier موقت پس از آزمون حذف شد؛ دو کانتینر کاربردی روشن مانده‌اند. [راهنمای Compose](../../../deployments/README.md) مسیر و فرمان‌ها را دارد. سایت Docker با localhost:8001 و native با 127.0.0.1:8000 باز می‌شود تا کوکی‌های دو نسخه در مرورگر تداخل نکنند.

حدود: یک وب با نشست process-local، restart نشست را از بین می‌برد؛ volume روی همین میزبان HA نیست. Docker baseline بار 500، کانتینر مشترک EXP-01، monitoring، recovery زمان‌دار یا امنیت جامع را اثبات نمی‌کند. آزمون native قبلی 57565 درخواست/یک failure/P95=2276ms بود و ظرفیت بدون خطای کاربر هنوز باز است. seed/create_all، migration نسخه‌دار نیست؛ حقوق آموزشی و تاریخ میلادی محفوظ‌اند.
