# DOCS-01 — راهنمای مدارک و وضعیت پروژه

شروع مرور: [گزارش جاری](10-final-report/report.md)، [تطبیق هر 93 اسلاید](project-framework-slide-review.md) و [کارهای باقی‌مانده](10-final-report/remaining-work.md).

| بخش | سند و کارکرد |
|---|---|
| 01 Project Charter | [CH-01](01-project-charter/charter.md)؛ مسئله، کاربران و scope |
| 02 Requirements | [منابع](02-requirements/sources.md)، [FR/NFR/BR](02-requirements/requirements.md) |
| 03 Specifications | [کاربردها](03-specifications/use-cases.md)، سه YAML در specs/ |
| 04 Models | [فهرست](04-models/README.md)، Context/UC/Domain و مدل‌های سه Core |
| 05 Architecture | [معماری واقعی](05-architecture/architecture.md)، [کیفیت](05-architecture/quality-scenarios.md)، [مسیر آزمایش](05-architecture/progressive-experiments.md)، ADRها |
| 06 Design | [component/class](06-design/design.md)، [API](06-design/api-design.md)، [DB واقعی](06-design/database-design.md) |
| 07 AI Transformation | [رکورد/پرامپت/خروجی](07-ai-transformation/README.md)، [review باز](07-ai-transformation/ai-review.md) |
| 08 Testing | [استراتژی](08-testing/strategy.md)، [test cases](08-testing/test-cases.md)، [نتایج واقعی](08-testing/report.md) |
| 09 Traceability | [ماتریس](09-traceability/matrix.md) و registry/specs ماشین‌خوان |
| 10 Report | [گزارش 20 بخش](10-final-report/report.md)، [CR-01](10-final-report/changes/CR-01.md)، [Gate](10-final-report/milestones.md)، [Rubric](10-final-report/rubric.md)، [دمو](10-final-report/presentation-and-demo.md)، [مشارکت](10-final-report/contributions.md) |

کار انجام‌شده: حفظ baseline/Git، framework، سه specification/model، اصلاح واقعی تصمیم درخواست، مستقل کردن clock، رگرسیون/coverage و load سبک. باز: review انسانی، NFRهای کامل، CI remote و آزمایش‌های container/replica/session/cache/gateway/worker.

«prepared» مدرک آمادهٔ review است؛ «tested» به آزمون ثبت‌شده و دامنهٔ آن اشاره دارد؛ «planned» اجرا نشده است. حضور فایل و عبور test به معنی تایید استاد نیست.

نسخهٔ اولیهٔ اسناد در history/ حفظ می‌شود؛ [گزارش Stage 1 تاریخی](history/stage01-status.md) و snapshotهای قبل، سوابق‌اند. [بررسی 33 اسلاید مقیاس‌پذیری](scalability-slide-review.md) وضعیت زمان آن بررسی را ثبت می‌کند و مسیر [EXP](05-architecture/progressive-experiments.md) وضعیت جدید را می‌دهد.

برای بازتولید مدارک، scripts/export_engineering_artifacts.py، build_traceability.py و render_slide_review.py خروجی مشتق‌شده می‌سازند. scripts/check_engineering.py پیوند/شناسه/schema/spec را بررسی می‌کند. نتایج آزمون و snapshotهای تاریخی overwrite نمی‌شوند.
