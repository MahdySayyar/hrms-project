# وضعیت جاری پروژه

تاریخ 2026-11-08. گزارش قدیمی Stage 1 در [history](history/stage01-status.md) محفوظ است. این فایل از این نسخه، وضعیت جاری را نشان می‌دهد.

هشت حوزهٔ HR پیاده شده‌اند؛ ورود/نقش/محدوده، audit و تاریخچه موجودند. معماری یک مونولیت و یک PostgreSQL native است. فقط workflow تصمیم درخواست به domain/service/repository منتقل و پاسخ تصمیم مخالف نهایی از 303 به 409 اصلاح شد. clock سرویس هم از ORM module جدا شد.

framework استاد: [93 اسلاید](project-framework-slide-review.md)، 25 FR/22 BR/11 NFR، سه UC کامل و مدل‌ها، ADR، design/API/schema، دو رکورد AI، traceability، تغییر CR-01، milestones و گزارش آماده‌اند. review انسانی و Gate دانشگاهی هنوز پذیرفته نشده‌اند.

شواهد: [29 آزمون نهایی و 98 assertion رگرسیون](08-testing/report.md)، 96.6٪ coverage ماژول تصمیم، load سبک 10 کاربر/1418 درخواست/خطای صفر. ظرفیت 500 کاربر، خرابی زیر بار، Docker/Compose/replica/Redis/queue/gateway/monitoring و HA هنوز اجرا نشده‌اند.

baseline تاریخی، Git و snapshot مستقل حفظ شده‌اند. [گزارش جاری](10-final-report/report.md) و [فهرست باز](10-final-report/remaining-work.md) مرجع وضعیت و قدم بعدند. این آمار، پذیرش همهٔ خواسته‌های استاد را اثبات نمی‌کند.
