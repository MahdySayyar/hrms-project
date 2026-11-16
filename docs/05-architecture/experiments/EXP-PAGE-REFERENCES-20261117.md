# EXP-PAGE-REFERENCES — شاهد مستقل ADR-11

2026-11-17؛ معماری/صفحه‌بندی قبلی از کد بازسازی شدند، قرارداد FR/BR/UC-04 و [ADR-11](../ADRs/ADR-11-page-reference-reads.md) پیش از این اصلاح ثبت و در [snapshot طرح](../../snapshots/architecture-read-plan-20261117-a.json) حفظ شدند. نتیجه پس از اجرای واقعی نوشته شده؛ review انسانی/پذیرش NFR در انتظار است.

مسئله: `module_list` در صفحهٔ محدود، برای هر سلول مرجع `display_value`/`db.get` داشت. نقشهٔ identity ضعیف ORM آن اشیا را نگه نمی‌داشت. اصلاح `app/modules.py` شناسه‌های همان صفحهٔ مجاز را به یک `SELECT id,label IN (...)` برای هر model تبدیل کرد؛ فقط نام/عنوان لازم خوانده می‌شود. نقشه عمر همان route را دارد و cache با TTL بین درخواست‌ها نیست.

| مسیر / اندازه | SELECT قبل → بعد | میانهٔ پنج درخواست قبل → بعد |
|---|---:|---:|
| مرخصی / 1 | 4 → 4 | 22.07 → 22.66ms |
| مرخصی / 50 | 53 → 4 | 75.06 → 42.26ms |
| مرخصی / 100 | 103 → 4 | 107.82 → 44.19ms |
| تردد / 1 | 5 → 5 | 13.12 → 12.99ms |
| تردد / 50 | 103 → 5 | 72.54 → 16.01ms |
| تردد / 100 | 203 → 5 | 132.19 → 18.90ms |
| متقاضی / 1 | 4 → 4 | 7.54 → 8.06ms |
| متقاضی / 50 | 53 → 4 | 37.31 → 10.85ms |
| متقاضی / 100 | 103 → 4 | 66.63 → 11.46ms |

پروتکل: schema مستقل PostgreSQL، 10,000 پرونده/تردد/درخواست/فیش و 150 متقاضی ساختگی، همان Python/harness، یک warmup و پنج sample متوالی، login خارج زمان. [قبل](../../08-testing/evidence/architecture-reads-before-20261117-d.json)، [بعد](../../08-testing/evidence/architecture-reads-after-20261117-a.json)، [مقایسهٔ hash خروجی و workload](../../08-testing/evidence/architecture-read-comparison-20261117-a.json). HTML پس از حذف فقط CSRF تصادفی در تمام مسیرها یکسان ماند. تک‌ردیفی بهبود قطعی زمان ندارد؛ SELECTهای اضافه متناسب با تعداد سلول حذف شده‌اند.

آزمون مستقل [CatalogReferenceReads](../../../tests/test_catalog_reference_reads.py) چهار unittest TC-04-05..08 دارد: اندازهٔ 1/50/100، SELECT و projection، scope و ids صفحه، تغییر نام در request بعد، dedup مصاحبه، career/enrollment، empty/invalid page، optional حساب، منع viewer/admin-only، missing reference و escaping. در اجرای اول یک assertion آزمون فاصلهٔ SQL concat را id حساب کرد و شکست خورد؛ [شاهد ناموفق](../../08-testing/evidence/architecture-read-contracts-20261117-a.json) حفظ شد. آزمون اصلاح شد؛ [Core بعد 50/50](../../08-testing/evidence/architecture-core-after-20261117-a.json) و [98 رگرسیون](../../08-testing/evidence/architecture-regression-20261117-a.json) موفق‌اند.

schema، route، نقش/محدوده و UI تغییر نکردند؛ fallback جزئیات حفظ شده است. فرم‌های GET و dropdown حقوق هنوز مسئلهٔ مستقل‌اند. schemaهای آزمایش حذف شدند؛ source/stageهای قبلی و دادهٔ native محفوظ‌اند. بازگشت patch محدود همین بخش از snapshot است. این آزمایش ترتیبی محلی، RPS/P95/ظرفیت 500 نفر، visual QA یا HA را ثابت نمی‌کند.
