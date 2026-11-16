# TEST-REPORT-01 — نتایج واقعی و محدودیت‌ها

تاریخ 2026-11-08؛ PostgreSQL واقعی و دادهٔ ساختگی. خروجی تاریخی بازنویسی نشده است.

به‌روزرسانی 2026-11-16: [گزارش Docker](../05-architecture/experiments/EXP-DOCKER-COMPOSE.md)، 41 آزمون اصلی روی PostgreSQL کانتینر، 98 بررسی رگرسیون و پوشش بخش تصمیم 96.629٪؛ استقرار/ورود/CSRF/volume پس از stop/start در 19 بررسی موفق بود. مدارک تاریخی زیر حفظ شده‌اند. آزمون یا تصویر تازهٔ مرورگر با این بررسی‌های HTTP ادعا نمی‌شود.

| بررسی | نتیجه | شاهد |
|---|---|---|
| اتصال اولیهٔ DB | محیط unavailable؛ صفر آزمون | [core-environment-unavailable](evidence/core-environment-unavailable.json) |
| قرارداد Core قبل CR-01 | 16 از 17 موفق؛ فقط opposite final decision شکست | [core-before](evidence/core-before.json) |
| Core پس از CR-01 | 17 از 17 موفق | [core-after](evidence/core-after.json) |
| قواعد مستقل پس از CR-01 | 10 از 10 موفق | [unit-after](evidence/unit-after.json) |
| مرز داخلی پس از CR-01 | 2 از 2 موفق | [boundaries-after](evidence/boundaries-after.json) |
| رگرسیون 8 حوزه بعد CR-01 | 98 از 98 assertion موفق | [full-smoke-after](evidence/full-smoke-after.json) |
| Core + domain + مرز پس از TRF-02 | 29 از 29 آزمون موفق | [all-tests-final](evidence/all-tests-final.json) |
| statement coverage ماژول تصمیم | 86/89، معادل 96.6٪ | [coverage](evidence/coverage-request-workflow.json) |
| parse نمودارها پس از اصلاح syntax | بدون خطا؛ parse گرامر، نه review تصویری | [diagrams-final](evidence/diagrams-final.json) |
| کنترل ساختاری نهایی | 1334 بررسی، بدون خطا؛ YAML/شناسه/پیوند/code symbol/spec/API/schema و freshness | [engineering-release](evidence/engineering-release.json) |
| parse نمودارهای نسخهٔ نهایی | 31 منبع/نمودار، بدون خطا | [diagrams-release](evidence/diagrams-release.json) |

98 assertion رگرسیون پیش از اصلاح کوچک clock اجرا شدند؛ 29 آزمون پس از آن، گردش Core و مرز تغییرکرده را بررسی کردند. نتایج 45 smoke و 11 browser قبلی تاریخی‌اند و تست جدید مرورگر به حساب نیامده‌اند.

کنترل نهایی وابستگی‌ها با `python -m pip check` موفق بود؛ `node --check scripts/browser_check.cjs` نیز تنها syntax اسکریپت تاریخی را بررسی کرد و مرورگر را اجرا نکرد. کنترل ساختاری یا parse نمودار، پذیرش انسانی یا بازبینی تصویری نیست. Git برای patchهای ثبت‌شده و SVGهای مرجع با hash بایتی، تبدیل پایان خط انجام نمی‌دهد.

## قبل و بعدِ اصلاح

قبل: approve موفق، سپس opposite reject پاسخ 303؛ رکورد قبلی حفظ می‌شد ولی HTTP موفق، تعارض را مبهم نشان می‌داد. TC-02-05 انتظار 409 داشت و شکست خورد. بعد: 409 صریح، همان تصمیم و تنها یک audit. same decision retry همچنان 303 و بدون نوشتن دوباره است.

قفل employee باعث می‌شود دو approval هم‌پوشان در آزمون موازی فقط یک برنده داشته باشند؛ خطای درج audit تمام تصمیم را rollback می‌کند. این دو تضمین از نسخهٔ قبل حفظ شدند و به عنوان قابلیت تازه یا افزایش RPS معرفی نمی‌شوند.

## آزمایش native کوچک

[شاهد Locust](evidence/native-load.json): یک وب native و PostgreSQL محلی، 100 پروندهٔ ساختگی، 10 کاربر authenticated، نرخ spawn برابر 5 در ثانیه، زمان هدف 20 ثانیه. 1418 workload request شامل 1116 خواندن و 302 نوشتن؛ نسبت مشاهده‌شدهٔ خواندن 78.7٪. خطا صفر، P50=38ms، P95=210ms، P99=560ms و RPS حدود 71.15.

صدک‌ها از ادغام bucketهای Locust و بدون setup/login محاسبه شدند؛ RPS بر پنجرهٔ حدود 19.93 ثانیه‌ای شامل setup تقسیم شده است. هدف وزن taskها 80/20 است، نه الزام اینکه در نمونهٔ تصادفی کوتاه دقیقاً همین نسبت رخ دهد. peak authenticated users واقعاً 10 و spawning_complete ثبت شد.

این آزمایش روی میزبان مشترک اجرا شده و CPU/RAM/DB connections را اندازه نگرفته است. کانتینر مشترک نیست؛ baseline ظرفیت 500 کاربر، HA، بار ورود اشباع یا بهبود performance حاصل از refactor نیست. nfr_500_users_verified صریحاً false است.

## موارد باز

پذیرش انسانی، پوشش کامل Extended، scan جامع OWASP و vulnerability، آزمون طولانی 500 کاربر، مقایسهٔ توپولوژی و resources، failover/replica/cache/queue، timed restore و usability باقی‌اند. تکرار آزمون بدون تغییر/ابهام تازه ضرورت ندارد؛ هر اجرای آینده شاهد با نام مستقل می‌سازد.
