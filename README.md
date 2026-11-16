# سامانهٔ مدیریت منابع انسانی — پروژهٔ معماری

[مخزن عمومی GitHub](https://github.com/MahdySayyar/hrms-project) · [دانلود ZIP](https://github.com/MahdySayyar/hrms-project/archive/refs/heads/master.zip) · [نتیجهٔ آزمون‌های خودکار](https://github.com/MahdySayyar/hrms-project/actions)

وب‌سایت فارسی و RTL با FastAPI، Jinja2 و PostgreSQL. هشت حوزهٔ HR پیاده‌سازی شده‌اند و چارچوب مهندسی درس به پروژه اضافه شده است. هدف، حفظ نسخهٔ ساده و اصلاح تدریجی معماری با مشکل و evidence واقعی است.

شروع بررسی: [گزارش جاری](docs/10-final-report/report.md)، [تطبیق هر 93 اسلاید استاد](docs/project-framework-slide-review.md)، [فهرست مستندات](docs/README.md). [شاهد نصب از کپی تازه](docs/05-architecture/experiments/EXP-DOWNLOAD-20261117.md) راه‌اندازی قابل دانلود را بررسی می‌کند.

تغییرات نهایی این پروژه پس از بررسی در Git ثبت و به همان مخزن GitHub ارسال می‌شوند؛ GitHub Actions آزمون‌ها را روی push اجرا می‌کند. هنگام بروزرسانی نسخهٔ نصب‌شده، فایل‌های پروژه را تازه و launcher را دوباره اجرا کنید؛ پوشهٔ خصوصی `.runtime` را حفظ کنید.

## شروع سریع بعد از دانلود

پیش‌نیاز: Docker Desktop روشن با **Linux containers** و Docker Compose v2 یا جدیدتر. نصب Python، PostgreSQL و Git لازم نیست. بار اول برای دریافت imageها اینترنت لازم است.

1. از GitHub گزینهٔ **Code → Download ZIP** را بزنید و ZIP را استخراج کنید.
2. در ویندوز فایل **`start-docker.cmd`** را دوبار کلیک کنید. در macOS/Linux از ریشهٔ پروژه اجرا کنید:

   ```bash
   bash scripts/start-docker.sh
   ```

3. بعد از آماده‌شدن کانتینرها، [صفحهٔ ورود](http://localhost:8001/login) را باز کنید. نام کاربری **`hradmin`** است. رمز مخصوص همین نصب داخل **`.runtime/docker-hrms-secrets/admin_password`** ساخته می‌شود؛ فایل را روی رایانهٔ خودتان باز کنید.

برنامه با دادهٔ نمونهٔ ساختگی آماده می‌شود. اجرای دوباره رمز یا دادهٔ قبلی را پاک نمی‌کند. اگر پورت 8001 اشغال است، ابتدا برنامهٔ دیگری را که روی آن اجرا شده متوقف کنید. راهنمای توقف، بروزرسانی و رفع مشکل در [راهنمای Docker](deployments/README.md) است.

## اجرا در Docker

استقرار 2026-11-16 با [Compose](deployments/compose.yaml): کانتینر `hrms-docker-web-1` برای وب و `hrms-docker-db-1` برای PostgreSQL، دادهٔ نمونه در volume مستقل. سایت: [ورود Docker](http://localhost:8001/login). راه‌اندازی/توقف، رمز اختصاصی محلی و حدود در [راهنمای Docker](deployments/README.md) است. نسخهٔ native روی 8000 محفوظ است. این baseline یک وب دارد؛ ظرفیت 500 یا HA به آن نسبت داده نمی‌شود.

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

تاریخ‌ها میلادی، مبالغ ریال آموزشی و قواعد حقوق قانونی نیستند. محاسبهٔ اولیهٔ دورهٔ تاریخی از profile/rule فعلی استفاده می‌کند؛ گزارش از سازمان فعلی. صفحه‌بندی کارکنان، ماژول‌ها و فیش‌ها پیاده شده است. نشست‌های هر وب حافظه‌ای‌اند؛ آزمایش native چهار وب با proxy و affinity مرورگر نیز اندازه‌گیری شده است. Docker/Compose وب و PostgreSQL اکنون اجرا شده‌اند؛ Kubernetes، Redis/RabbitMQ/gateway و HA هنوز اجرا نشده‌اند.

ادامهٔ 2026-11-15: هدف مستقیم کاربر تحمل 500 نفر بدون خطاست. [گزارش‌های مستقل اصلاح‌ها](docs/05-architecture/experiments/README.md) صفحه‌بندی، احراز هویت، چهار وب، transport و اعتبارسنجی فرم را با شواهد مثبت و منفی ثبت می‌کنند. آزمون کوتاه transport با 500 نفر از 5144 درخواست فقط یک timeout داشت، اما P95=3063ms و burst ناموفق بود؛ اصلاح محدودکردن اعتبارسنجی POST و آزمون کامل پنج‌دقیقه‌ای پس از آن ادامه یافته است. این عدد، پذیرش NFR یا ظرفیت سایت اصلی نیست.

## مدارک و شواهد

25 FR، 22 BR و 11 NFR؛ چهار کاربرد کامل YAML و مدل‌های Context/Use Case/Domain، سه sequence/activity/state؛ architecture alternatives و ADR؛ design و OpenAPI/schema واقعی؛ دو AI record تاریخی؛ traceability و CR-01/CR-02؛ Gate/DoD/Rubric و برنامهٔ ارائه.

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

workflow CI در .github/workflows/engineering.yml روی push و pull request بررسی‌های PostgreSQL، coverage، مهندسی، نمودارها و راه‌اندازی Docker را اجرا می‌کند. نتیجهٔ هر اجرای واقعی در تب Actions مخزن مشخص است. legacy browser_check.cjs برای UI با ابزارهای قدیمی اجرا نشده است؛ شواهد مرورگر قبلی تاریخی‌اند.

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
