# وضعیت جاری پروژه

وضعیت 2026-11-17: [شاهد ورود هم‌زمان](05-architecture/experiments/EXP-LOGIN-PROXY-20261117.md) با 500/500 لاگین و نشست دارای هویت صحیح، 830/830 probe موفق و restart صفر ثبت شد؛ زمان کل ورودها حدود 107s روی میزبان آزمون است. Docker اکنون چهار وب، proxy با affinity و PostgreSQL دارد؛ [استقرار واقعی](08-testing/evidence/login500-live-deployment-20261117-a.json) و [نصب تازه](08-testing/evidence/login500-download-20261117-a.json) موفق‌اند. core=57/57، رگرسیون=98 assertion، coverage تصمیم=96.6٪. فقط تصمیم درخواست مرز domain/service/repository دارد؛ نشست‌ها process-local و human review/Gate بازند. هدف بار ترکیبی پنج‌دقیقه‌ای یا HA از این login burst تأیید نشده است.

متن زیر وضعیت تاریخی 2026-11-16 و قبل از این اصلاح است:

به‌روزرسانی 2026-11-16؛ مبنای تاریخی زیر از 2026-11-08 است. گزارش قدیمی Stage 1 در [history](history/stage01-status.md) محفوظ است.

وب و PostgreSQL در دو کانتینر Compose با volume و secretهای مستقل اجرا شده‌اند؛ [Docker](../deployments/README.md) روی localhost:8001 است و native روی 8000 محفوظ است. هنوز یک وب در Docker داریم و HA/ظرفیت 500 برای آن تأیید نشده است. آزمایش native پنج‌دقیقه‌ای قبلی 57565 درخواست و یک failure و P95=2276ms داشت؛ burst 500 مرخصی موفق بود، اما هدف صفر خطا و معیار سرعت کامل نشده‌اند.

صفحه‌بندی، احراز هویت محدود به هر request، proxy native با چهار وب و affinity و transport aiohttp پیاده شده‌اند. POST معتبر نیز فقط مرجع انتخاب‌شده را برای گزینه‌های فرم می‌خواند. سایت اصلی هنوز یک پردازه است؛ نشست‌ها در هر وب حافظه‌ای‌اند. [گزارش‌های مستقل](05-architecture/experiments/README.md) نتیجه و شکست هر گام را ثبت می‌کنند. آزمون کامل 500 نفر پس از آخرین اصلاح در این نوبت انجام می‌شود؛ موفقیت پیشاپیش فرض نشده است.

هشت حوزهٔ HR پیاده شده‌اند؛ ورود/نقش/محدوده، audit و تاریخچه موجودند. معماری یک مونولیت و یک PostgreSQL native است. فقط workflow تصمیم درخواست به domain/service/repository منتقل و پاسخ تصمیم مخالف نهایی از 303 به 409 اصلاح شد. clock سرویس هم از ORM module جدا شد.

framework استاد: [93 اسلاید](project-framework-slide-review.md)، 25 FR/22 BR/11 NFR، سه UC کامل و مدل‌ها، ADR، design/API/schema، دو رکورد AI، traceability، تغییر CR-01، milestones و گزارش آماده‌اند. review انسانی و Gate دانشگاهی هنوز پذیرفته نشده‌اند.

شواهد تاریخی 2026-11-08: [29 آزمون و 98 assertion رگرسیون](08-testing/report.md)، 96.6٪ coverage ماژول تصمیم، load سبک 10 کاربر/1418 درخواست/خطای صفر. آزمایش‌های تازهٔ 500 نفر انجام شده‌اند ولی در این نقطه پذیرش کامل ظرفیت اثبات نشده است. خرابی زیر بار، Docker/Compose/replica/Redis/queue/gateway و HA بازند.

baseline تاریخی، Git و snapshot مستقل حفظ شده‌اند. [گزارش جاری](10-final-report/report.md) و [فهرست باز](10-final-report/remaining-work.md) مرجع وضعیت و قدم بعدند. این آمار، پذیرش همهٔ خواسته‌های استاد را اثبات نمی‌کند.
