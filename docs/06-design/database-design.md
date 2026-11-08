# DB-01 — طراحی دادهٔ واقعی

این export از reflection فقط‌خواندنی PostgreSQL 17.6 در schema public ساخته شده؛ هیچ سطر HR، رمز یا URL اتصال صادر نشده است. تعداد جدول‌ها 21 است و نام/ستون/نوع/nullability با مدل‌های ORM و نگاشت مفهومی تطبیق داده شد.

[DDL فعلی](database-schema.sql)، [metadata و constraints](database-schema.json)، [منبع و hash کد](export-source.json)، [نمودار ER editable](../../models/data-model.mmd).

| جدول | ستون | foreign key |
|---|---|---|
| admins | 8 | 2 |
| assignment_history | 11 | 4 |
| attendance | 11 | 2 |
| audit_log | 7 | 1 |
| branches | 3 | 0 |
| candidates | 14 | 4 |
| career_plans | 6 | 2 |
| employees | 14 | 3 |
| employment_contracts | 10 | 2 |
| evaluations | 6 | 1 |
| hr_requests | 13 | 2 |
| interviews | 6 | 1 |
| onboarding_tasks | 5 | 1 |
| payroll_profiles | 6 | 1 |
| payroll_rules | 8 | 0 |
| payslips | 14 | 2 |
| positions | 4 | 0 |
| shifts | 6 | 0 |
| training_enrollments | 5 | 2 |
| trainings | 5 | 0 |
| units | 4 | 1 |

قیدهای اصلی: کد کارمند یکتا؛ unit/branch مرکب؛ attendance employee/day یکتا؛ payslip employee/period یکتا؛ profile برای هر employee یکتا؛ یک active contract و یک assignment جاری با partial unique index؛ ثبت‌نام employee/training یکتا؛ score/progress و درصد/ساعت در محدوده.

قواعد request status و overlap در service/domain و transaction قفل‌دار اعمال می‌شوند و CHECK/EXCLUDE constraint جامع در DB ندارند. snapshotهای فیش JSON هستند، نه JSONB. audit به entity/record منطقی متصل است و سیستم tamper-evident نیست.

این SQL شرح schema است؛ migration یا backup نیست و روی پایگاه موجود اجرا نمی‌شود. مدیریت migration نسخه‌دار، طرح restore آزموده و effective-dated profile/report هنوز باقی‌اند. اصل HRMS همچنان یک پایگاه مشترک دارد.
