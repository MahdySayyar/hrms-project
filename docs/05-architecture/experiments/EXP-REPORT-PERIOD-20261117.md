# EXP-REPORT-PERIOD — شاهد مستقل ADR-13

2026-11-17؛ FR-22/BR-13/FS-22، UC-11، SEQ-11 و [ADR-13](../ADRs/ADR-13-canonical-report-period.md) پیش از اصلاح در [snapshot طرح](../../snapshots/architecture-read-plan-20261117-a.json) ثبت شدند. رفتار موجود از کد بازسازی شده؛ این گزارش پس از اجرای واقعی نوشته شد. review انسانی و سیاست واقعی HR در انتظار است.

`reports` start/end و validation را normalize می‌کرد ولی مقایسهٔ `Payslip.period` از متن اولیه استفاده می‌کرد. در schema synthetic با 10,000 فیش آموزشی 100 واحدیِ Jan 2025، نتیجهٔ قبل/بعد:

| ورودی ماه | جمع قبل | جمع بعد | context بعد |
|---|---:|---:|---|
| `2025-01` | 1,000,000 | 1,000,000 | `2025-01` |
| `۲۰۲۵-۰۱` | 0 | 1,000,000 | `2025-01` |
| `٢٠٢٥-٠١` | 0 | 1,000,000 | `2025-01` |

اصلاح یک normalization پس از default موجود در `app/modules.py#reports` است؛ همان متغیر برای همهٔ query/context استفاده می‌شود. [قبل](../../08-testing/evidence/architecture-reads-before-20261117-d.json)، [بعد](../../08-testing/evidence/architecture-reads-after-20261117-a.json) و [مقایسه](../../08-testing/evidence/architecture-read-comparison-20261117-a.json) مستقل از سطر واقعی HR‌اند. این اعداد fixture هستند، نه مبلغ واقعی یا نرخ قانونی.

آزمون‌های TC-11-04/05 در [ReportReads](../../../tests/test_report_reads.py) ماه لاتین/فارسی/عربی و فاصله پیرامونی، ماه/سال نامعتبر و whitespace-only، default موجود، روز کبیسهٔ February 2024، role/scope و نداشتن audit نوشتنی گزارش را بررسی می‌کنند. [Core بعد 50/50](../../08-testing/evidence/architecture-core-after-20261117-a.json) و [رگرسیون 98/98](../../08-testing/evidence/architecture-regression-20261117-a.json) موفق بودند.

schema و stored snapshot تغییر ندارند؛ calculator از قبل ASCII YYYY-MM می‌نوشت. مهاجرت داده، تقویم جلالی، نرخ یا recompute فیش ایجاد نشد. بازگشت حذف همین normalization است و مشکل قبلی را برمی‌گرداند. تست مرورگر/پذیرش انسانی یا بهبود latency از این اصلاح کوچک ادعا نمی‌شود.
