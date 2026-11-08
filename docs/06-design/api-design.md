# API-CAT-01 — قرارداد وب و خروجی OpenAPI

نسخهٔ قابل ماشین‌خوان: [http-contracts.yaml](../../specs/http-contracts.yaml). [OpenAPI استخراج‌شده از FastAPI](openapi-generated.json)، [OpenAPI اصلاح‌شده برای مرورگر](openapi-browser.yaml) و [فهرست واقعی routes و فرم‌ها](route-inventory.json) توسط scripts/export_engineering_artifacts.py ساخته می‌شوند. صفحهٔ Swagger/OpenAPI در runtime عمداً غیرفعال است؛ export فایل endpoint جدید ایجاد نمی‌کند.

| شناسه | حوزه | UC | پاسخ اصلی |
|---|---|---|---|
| API-01 | GET /login؛ POST /login؛ POST /logout | UC-01 | HTML / 303 |
| API-02 | POST /hr/{module}/new؛ POST /requests/{request_id}/review | UC-02 | HTML / 303 |
| API-03 | GET /payroll؛ POST /payroll/calculate؛ GET /payroll/{payslip_id} | UC-03 | HTML / 303 |
| API-04 | GET /employees؛ GET /employees/{employee_id}؛ POST /employees/new؛ POST /employees/{employee_id}/edit؛ POST /employees/{employee_id}/status | UC-04 | HTML / 303 |
| API-05 | GET /organization/{kind}؛ POST /organization/{kind}/new | UC-05 | HTML / 303 |
| API-06 | POST /hire/{candidate_id}؛ POST /onboarding/{task_id} | UC-06 | HTML / 303 |
| API-07 | POST /hr/{module}/new | UC-07 | HTML / 303 |
| API-08 | POST /contracts/{contract_id}/activate؛ POST /contracts/{contract_id}/renew؛ POST /contracts/{contract_id}/terminate | UC-08 | HTML / 303 |
| API-09 | POST /hr/{module}/new | UC-09 | HTML / 303 |
| API-10 | GET /history/{employee_id} | UC-10 | HTML / 303 |
| API-11 | GET /reports؛ GET /reports/employees.csv | UC-11 | HTML / 303 / CSV |
| API-12 | GET /audit؛ POST /hr/{module}/new | UC-12 | HTML / 303 |

فرم‌ها JSON API نیستند. کوکی hrms_session هویت نشست است؛ csrf_token فیلد فرم POST است. پاسخ mutation عموماً 303 همراه Location، validation معمولاً 400، نقش غیرمجاز 403، رکورد پنهان/ناموجود 404 و تصمیم مخالف 409 است. مسیر/پارامتر ناسازگار می‌تواند 422 پیش‌فرض FastAPI بدهد. خطای غیرمنتظرهٔ persistence پاسخ 500 دارد.

OpenAPI پیش‌فرض از request.form() فیلدها، کوکی و redirect را استنتاج نمی‌کند؛ فایل مرورگر توضیح‌های صریح را اضافه می‌کند و برای فرم‌های عمومی schemaها را از MODULES استخراج می‌کند. موارد fields_from هنوز ارجاع به فرم/کد هستند و تضمین specification کاملِ تمام endpointهای فرعی نیستند.

GET /health وضعیت اتصال DB را با 200/503 JSON می‌دهد؛ GET /instance نام نمونه را می‌دهد. GET خروجی CSV با وجود روش خواندن، audit می‌نویسد. اثر جانبی مذکور باید در طراحی cache/retry آینده در نظر گرفته شود.

قرارداد Core شامل شرط notes غیرخالی برای رد، حفظ تصمیم در retry یکسان، بازهٔ inclusive، ماه میلادی واقعی و immutable payslip است. این شروط با [آزمون‌ها](../08-testing/test-cases.md) مرتبط‌اند. OpenAPI خروجی، قرارداد توصیفی است؛ آزمون schema قراردادیِ کامل همهٔ فرم‌ها هنوز ساخته نشده است.
