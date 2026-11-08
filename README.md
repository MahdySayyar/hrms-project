# سامانهٔ مدیریت منابع انسانی — پروژهٔ معماری

وب‌سایت فارسی و RTL با FastAPI، Jinja2 و PostgreSQL. هشت حوزهٔ HR پیاده‌سازی شده‌اند و چارچوب مهندسی درس به پروژه اضافه شده است. هدف، حفظ نسخهٔ ساده و اصلاح تدریجی معماری با مشکل و evidence واقعی است.

شروع بررسی: [گزارش جاری](docs/10-final-report/report.md)، [تطبیق هر 93 اسلاید استاد](docs/project-framework-slide-review.md)، [فهرست مستندات](docs/README.md).

## سایت و اجرا

نشانی محلی: [صفحهٔ ورود](http://127.0.0.1:8000/login). فایل «اجرای سامانه.cmd» برنامه را روشن و مرورگر را باز می‌کند. اجرای PowerShell از ریشهٔ پروژه:

```powershell
Set-Location -LiteralPath 'C:/Users/mahdy/Desktop/MP'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch.ps1
```

راه‌انداز PostgreSQL همین پروژه و یک وب روی localhost:8000 را اجرا می‌کند؛ پردازهٔ سالم دوم نمی‌سازد. برای بارگذاری کد جدید، scripts/restart.ps1 فقط پردازهٔ شناخته‌شدهٔ همین پروژه را restart می‌کند. توقف foreground با Ctrl+C در scripts/start.ps1؛ توقف DB با setup-postgres.ps1 -Action stop.

نام کاربری اولیه hradmin است؛ رمز و تنظیمات را از فایل محلی .env بخوانید. .env حاوی credential پایگاه است و وارد Git/گزارش نمی‌شود. حساب‌های admin، hr و viewer قابل مدیریت‌اند. نشانی 127.0.0.1 فقط روی همین رایانه در دسترس است.

## وضعیت واقعی

| بخش | وضعیت |
|---|---|
| استخدام و پذیرش | متقاضی، مصاحبه، استخدام و چک‌لیست |
| اطلاعات پرسنل | پرونده/جست‌وجو/فعالیت و سازمان |
| تردد | شیفت، حضور/غیاب، دقیقهٔ کار و اضافه‌کاری/شیفت شب |
| درخواست | مرخصی، مأموریت و اداری؛ تصمیم و منع overlap |
| حقوق آموزشی | rule/profile، محاسبه و snapshot فیش یکتا |
| قرارداد | draft، فعال‌سازی، تمدید و خاتمه با حفظ سابقه |
| رشد حرفه‌ای | ارزیابی، آموزش/ظرفیت و مسیر شغلی |
| گزارش/تاریخچه/دسترسی | تاریخچهٔ انتساب، گزارش کلی، CSV، نقش/محدوده، audit و حساب |

معماری فعلی یک مونولیت با یک وب و DB محلی است. فقط تصمیم درخواست به Domain / Service / Repository منتقل شده؛ تصمیم مخالف نهایی اکنون 409 می‌گیرد و retry یکسان بدون تغییر دوباره است. سایر قواعد عمدتاً در route هستند.

تاریخ‌ها میلادی، مبالغ ریال آموزشی و قواعد حقوق قانونی نیستند. محاسبهٔ اولیهٔ دورهٔ تاریخی از profile/rule فعلی استفاده می‌کند؛ گزارش از سازمان فعلی. نشست‌ها در حافظهٔ یک وب‌اند. صفحه‌بندی، Docker/Compose/Kubernetes، Redis/RabbitMQ/gateway/monitoring و HA هنوز پیاده نشده‌اند.

## مدارک و شواهد

25 FR، 22 BR و 11 NFR؛ سه کاربرد کامل YAML و مدل‌های Context/Use Case/Domain، سه sequence/activity/state؛ architecture alternatives و ADR؛ design و OpenAPI/schema واقعی؛ دو AI record؛ traceability و CR-01؛ Gate/DoD/Rubric و برنامهٔ ارائه.

[آزمون‌های واقعی](docs/08-testing/report.md): 16/17 قبل اصلاح → 17/17 بعد؛ 29/29 پس از تکمیل مرز، 98/98 assertion رگرسیون؛ coverage package تصمیم 96.6٪. load سبک 10 کاربر، 1418 درخواست و خطای صفر با P95=210ms. این load ظرفیت 500 کاربر را تأیید نمی‌کند.

[کارهای باز](docs/10-final-report/remaining-work.md): review انسانی و یادگیری/مشارکت، NFRهای کامل و آزمایش‌های مرحله‌ای معماری. «مدرک آماده» یا «test passed» معادل پذیرش استاد نیست.

## نصب تازه و وابستگی‌ها

Python 3.12 و محیط مجزا:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-postgres.ps1 -Action setup
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

setup-postgres بستهٔ رسمی PostgreSQL 17.6 را داخل .runtime نصب و روی 127.0.0.1:55432 آماده می‌کند؛ نصب سراسری یا reset دادهٔ موجود ندارد. seed صریح و تکرارپذیر است و password حساب موجود را خودکار عوض نمی‌کند. برای database از قبل دارای جدول‌های نسخهٔ قدیمی، ارتقای مرحله‌ای مستندشده لازم است؛ create_all مهاجرت نسخه‌دار نیست.

requirements-lock.txt نسخهٔ تولید و requirements-dev-lock.txt snapshot محیط توسعه است. محیط توسعه Locust/PyYAML/coverage دارد. تغییر وابستگی production در این نوبت انجام نشده است.

## تکرار آزمون و تولید مدارک

خروجی‌ها نام جدید می‌خواهند؛ نمونه‌های زیر برای اجرای بعدی‌اند و فایل فعلی را overwrite نمی‌کنند.

```powershell
.\.venv\Scripts\python.exe .\scripts\run_core_checks.py --phase after --pattern 'test_*.py' --output docs/08-testing/evidence/core-next.json
.\.venv\Scripts\python.exe .\scripts\run_isolated_smoke.py --output docs/08-testing/evidence/smoke-next.json
.\.venv\Scripts\python.exe .\scripts\run_load_lab.py --users 10 --seconds 20 --employees 100 --output docs/08-testing/evidence/load-next.json
.\.venv\Scripts\python.exe .\scripts\export_engineering_artifacts.py --refresh
.\.venv\Scripts\python.exe .\scripts\build_traceability.py --refresh
.\.venv\Scripts\python.exe .\scripts\render_slide_review.py --refresh
.\.venv\Scripts\python.exe .\scripts\check_engineering.py --output docs/08-testing/evidence/docs-next.json
.\.venv\Scripts\python.exe -m pip check
```

Core/رگرسیون/بار در schema PostgreSQL مستقل و دادهٔ ساختگی اجرا می‌شوند؛ بار نوشتنی فقط localhost دارای marker آزمایش را قبول می‌کند. برای اندازه‌گیری coverage از coverage run --source app/request_workflow روی run_core_checks.py و report --fail-under=80 استفاده کنید؛ فایل داده را زیر artifacts نگه دارید.

برای parse نمودار بدون کنترل مرورگر:

```powershell
npm.cmd install --prefix .\artifacts\diagram-validator --ignore-scripts --no-audit --no-fund mermaid@11 jsdom@26
node .\scripts\validate_diagrams.mjs --output docs/08-testing/evidence/diagrams-next.json
```

workflow CI در .github/workflows/engineering.yml آماده است؛ اجرا/انتشار remote در این نوبت انجام نشده. legacy browser_check.cjs برای UI با ابزارهای قدیمی اجرا نشده است؛ شواهد مرورگر قبلی تاریخی‌اند.

## نسخه‌ها و ساختار

```text
app/                 برنامه و مرز داخلی request_workflow
templates/, static/  UI فارسی
specs/, models/      قرارداد و مدل editable
docs/01..10/         زنجیرهٔ مهندسی و evidence
docs/history/        اسناد اولیهٔ حفظ‌شده
scripts/, tests/     اجرا، export، آزمون و load
.github/workflows/   CI آمادهٔ اجرای آینده
artifacts/           فایل‌های خام و archive محلی، خارج Git
.runtime/, .venv/    اجرای محلی و وابستگی، خارج Git
.env                 تنظیمات خصوصی، خارج Git
```

baseline پیش از framework در commit 326f77b و artifacts/baseline-before-framework-20261108-source.zip محفوظ است. آرشیو Stage 1 قدیمی overwrite نشده. برای snapshot تازه:

```powershell
.\.venv\Scripts\python.exe .\scripts\save_stage_snapshot.py --name hrms-next-baseline --description 'A separately named validated source baseline'
```

فایل‌های فعلی و مدارک، توسط عامل کدنویسی تهیه شده‌اند؛ student review/contribution بدون شاهد گزارش نمی‌شود.
