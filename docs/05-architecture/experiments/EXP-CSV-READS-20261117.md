# EXP-CSV-READS — شاهد مستقل ADR-12

2026-11-17؛ رفتار قبلی CSV از کد بازسازی شد. FR-23/BR، UC-11، SEQ-11 و [ADR-12](../ADRs/ADR-12-projected-csv-reads.md) پیش از کد در [snapshot طرح](../../snapshots/architecture-read-plan-20261117-a.json) ثبت شدند؛ نتیجه پس از اجرا نوشته شده و review انسانی در انتظار است.

query قبلی تمام Employee ORM و `.all()` را نگه می‌داشت، با ستون‌هایی مثل national_id/phone/email که در export نیستند. query تازه در `app/modules.py#export_employees` هشت ستون واقعی را project و cursor را در batchهای 500 مصرف می‌کند. تعداد در پیمایش شمرده و cursor پیش از audit/commit بسته می‌شود. پاسخ کامل buffered می‌ماند تا شکست audit، CSV موفق به کاربر تحویل ندهد.

| معیار، 10,000 پروندهٔ ساختگی | قبل | بعد |
|---|---:|---:|
| SELECT هر request، با auth | 2 | 2 |
| میانهٔ پنج نمونهٔ گرم | 243.07ms | 132.92ms |
| اوج allocation پایتون، sample جدا با tracemalloc | 28,714,758 bytes | 10,005,596 bytes |
| بایت پاسخ | 1,419,001 | 1,419,001 |

کاهش allocation حدود 65.16٪ است؛ تمام بایت‌های CSV hash یکسان داشتند و auditهای تعداد ردیف درست بودند. [قبل](../../08-testing/evidence/architecture-reads-before-20261117-d.json)، [بعد](../../08-testing/evidence/architecture-reads-after-20261117-a.json) و [مقایسهٔ ماشینی](../../08-testing/evidence/architecture-read-comparison-20261117-a.json) workload/harness یکسان و حذف schema را ثبت می‌کنند. داده فقط synthetic و requestها متوالی TestClient بودند؛ کاهش RSS کل یا ظرفیت بار از این اندازه‌گیری استنتاج نمی‌شود.

سه آزمون TC-11-01..03 در [ReportReads](../../../tests/test_report_reads.py): BOM و هشت عنوان، فرمول/فاصله/کاما/نقل‌قول، ترتیب/وضعیت، scope و audit دقیق، 1008 ردیف بیش از یک batch، query بدون ستون‌های خصوصی، export خالی، منع viewer و تزریق failure audit با 500 و بدون CSV موفق. [Core 50/50](../../08-testing/evidence/architecture-core-after-20261117-a.json) و [رگرسیون 98/98](../../08-testing/evidence/architecture-regression-20261117-a.json) گذشتند.

schema و قرارداد HTTP تغییر نکردند و migration لازم نیست. CSV هنوز O(N) بایت در حافظه و تولید همگام دارد؛ اگر فایل/زمان واقعی budget را بشکند، streaming یا queue با طرح جدید audit/auth/download بررسی شود. بازگشت همین query محدود از snapshot است؛ داده یا شواهد قبلی حذف نمی‌شوند. هیچ CSV یا credential واقعی HR صادر نشد.
