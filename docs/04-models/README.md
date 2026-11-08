# MODEL-CAT-01 — مدل‌های HRMS

این مدل‌ها در 2026-11-08 از رفتار موجود بازسازی شده‌اند. مرز service بدون وابستگی ORM، هدف صریح اصلاح محدود TRF-02 است. همهٔ مدل‌ها برای review انسانی آماده‌اند؛ تأیید دانشجو ثبت نشده است.

| شناسه | مدل | فایل editable | کاربرد |
|---|---|---|---|
| CTX-01 | HRMS context | [Mermaid](../../models/context.mmd) | UC-01, UC-02, UC-03 |
| UCM-01 | Use-case model | [Mermaid](../../models/use-cases.mmd) | UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11, UC-12 |
| DM-01 | Conceptual domain | [Mermaid](../../models/domain.mmd) | UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11, UC-12 |
| SEQ-01 | Authenticate and logout sequence | [Mermaid](../../models/sequences/UC-01.mmd) | UC-01 |
| SEQ-02 | Request creation and decision sequence | [Mermaid](../../models/sequences/UC-02.mmd) | UC-02 |
| SEQ-03 | Payroll calculation and saved retry | [Mermaid](../../models/sequences/UC-03.mmd) | UC-03 |
| ACT-01 | Authentication activity | [Mermaid](../../models/activities/UC-01.mmd) | UC-01 |
| ACT-02 | HR request activity | [Mermaid](../../models/activities/UC-02.mmd) | UC-02 |
| ACT-03 | Payroll activity | [Mermaid](../../models/activities/UC-03.mmd) | UC-03 |
| ST-01 | Session lifecycle | [Mermaid](../../models/states/session.mmd) | UC-01 |
| ST-02 | Request decision lifecycle | [Mermaid](../../models/states/request.mmd) | UC-02 |
| ST-03 | Payslip persistence lifecycle | [Mermaid](../../models/states/payslip.mmd) | UC-03 |
| CMP-01 | Request workflow components | [Mermaid](../../models/design/components.mmd) | UC-02 |
| CLS-01 | Request workflow classes | [Mermaid](../../models/design/classes.mmd) | UC-02 |
| ARCH-01 | Actual deployment | [Mermaid](../../models/architecture.mmd) | UC-01, UC-02, UC-03 |

نسخهٔ ماشین‌خوان: [model-catalog.yaml](../../specs/model-catalog.yaml). نسخهٔ قابل مشاهدهٔ مدل‌ها در [تحلیل](analysis-models.md)، [ورود](UC-01-models.md)، [درخواست](UC-02-models.md) و [حقوق](UC-03-models.md) قرار می‌گیرد.

DM-01 مدل مفهومی است: مفهوم UserAccount به جدول admins نگاشت می‌شود؛ Actor کارمند حساب ورود جدا ندارد. AuditLog به entity/record به‌صورت منطقی ارجاع می‌دهد و برای هر نوع entity یک foreign key ندارد. ارتباط rule به فیش snapshot است، نه FK. نمودار دادهٔ استخراج‌شده در [DB-01](../06-design/database-design.md) جداست.

ST-03 چرخهٔ وجود/عدم وجود رکورد است؛ ستون status برای فیش اختراع نشده است. Context مرز سامانه و کاربران را نشان می‌دهد و PostgreSQL جزء داخلی پیاده‌سازی است. در Use Case Model، رابطهٔ viewer با UC-11 فقط گزارش کلی است؛ خروجی پرونده و CSV مجوز جدا دارند.

برای تغییر آینده، ابتدا UC/BR و مدل مرتبط و اثر تغییر بازبینی شود. مدل‌ها نباید برای نقش، وضعیت یا سرویسِ ساخته‌نشده جریان موفق رسم کنند.
