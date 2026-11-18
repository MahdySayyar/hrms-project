# اجرای Docker پروژه

راه‌انداز پیش‌فرض اکنون `compose.capacity.yaml` را اجرا می‌کند: چهار وب، proxy تقسیم درخواست با affinity مرورگر و PostgreSQL. هر وب یک پردازه و یک thread خصوصی برای بررسی رمز دارد؛ thread و اتصال پایگاه هنگام انتظار ورود آزاد می‌مانند. رمز/volume همان نصب حفظ می‌شود و فقط وب اول seed را اجرا می‌کند. افزایش پردازه‌ها در همین رایانه CPU فیزیکی تازه ایجاد نمی‌کند؛ زمان تکمیل ورود هم‌زمان به میزبان بستگی دارد. نشست‌ها همچنان در حافظهٔ هر وب‌اند.

برای مشاهده و توقف استقرار چهار وب، از `docker compose -f deployments/compose.capacity.yaml ps` و `docker compose -f deployments/compose.capacity.yaml stop` استفاده کنید. شروع دوباره با همان launcher یا `docker compose -f deployments/compose.capacity.yaml start` است. هنگام restart کامل، ورود دوباره لازم می‌شود. baseline تک‌وب در compose.yaml حفظ شده است؛ برای جابه‌جایی به آن ابتدا `docker compose -f deployments/compose.capacity.yaml down` بدون حذف volume و سپس `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-docker.ps1 -WebWorkers 1` را اجرا کنید. معادل Bash گزینهٔ `bash scripts/start-docker.sh 1` است. داده و secret را حذف نکنید.

اگر پورت 8001 اشغال است، در PowerShell قبل از launcher فرمان `$env:HRMS_HTTP_PORT='8002'` یا در Bash فرمان `HRMS_HTTP_PORT=8002 bash scripts/start-docker.sh` را اجرا کنید؛ سایت روی localhost:8002 باز می‌شود. برای استفادهٔ بعدی از همان پورت، همین تنظیم را هنگام راه‌اندازی نگه دارید.

برای نسخهٔ دانلودشده در ویندوز `start-docker.cmd` را دوبار کلیک کنید؛ در macOS/Linux فرمان `bash scripts/start-docker.sh` را از ریشه بزنید. فقط Docker با Linux containers و Compose v2 لازم است. کانتینر موقت initializer رمزهای نصب را تولید می‌کند و پس از اجرا حذف می‌شود. نصب تازه به `.env` یا Python میزبان نیاز ندارد.

برای بروزرسانی یک clone، در ریشه `git pull --ff-only` و سپس launcher را دوباره اجرا کنید. برای نصب از ZIP، فایل‌های نسخهٔ جدید را جایگزین کنید و پوشهٔ خصوصی `.runtime` را نگه دارید. اگر secretها را حذف کنید ولی volume را نگه دارید، رمزهای تازه با پایگاه موجود سازگار نخواهند بود. تغییر schema قدیمی همچنان نیازمند راهنمای مهاجرت همان نسخه است.

برای رفع مشکل از `docker compose -f deployments/compose.capacity.yaml ps` و `docker compose -f deployments/compose.capacity.yaml logs --tail=100 web db` استفاده کنید. Docker باید روشن باشد و پورت 8001 آزاد باشد. آماده‌شدن اولین build به سرعت اینترنت بستگی دارد.

در حالت پیش‌فرض، پروژهٔ `hrms-docker` چهار وب تک‌پردازه، پراکسی و PostgreSQL دارد. هر وب نشست‌هایش را در حافظه نگه می‌دارد. PostgreSQL روی شبکهٔ داخلی Compose و volume مستقل است. دادهٔ اولیه از نمونهٔ ساختگی کد می‌آید.

از ریشهٔ پروژه:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-docker.ps1
docker compose -f deployments/compose.capacity.yaml ps
```

سایت Docker: [ورود](http://localhost:8001/login). نام کاربری `hradmin` و رمز اختصاصی Docker در فایل محلی `.runtime/docker-hrms-secrets/admin_password` است؛ آن را وارد Git، گزارش یا تصویر نکنید. برای حفظ کوکی‌های مستقل، Docker را با localhost و native را با 127.0.0.1 باز کنید. راه‌اندازی مجدد رمزهای موجود را عوض نمی‌کند. Compose secret محلی فایل runtime است، تضمین رمزنگاری Swarm نیست.

توقف/شروع با حفظ volume:

```powershell
docker compose -f deployments/compose.capacity.yaml stop
docker compose -f deployments/compose.capacity.yaml start
```

برای حذف کانتینرهای همین پروژه با حفظ داده از `down` بدون گزینهٔ حذف volume استفاده کنید. دادهٔ native و دیگر پروژه‌های Docker تحت این فرمان‌ها نیستند. DB هیچ پورت میزبان ندارد. healthcheck وب وابستگی PostgreSQL را هم بررسی می‌کند.

Dockerfile فقط requirements، app، templates، static و entrypoint را کپی می‌کند. .env، .runtime، tests، docs و artifacts از build کنار گذاشته شده‌اند. core/regression با منابع تستی که موقتاً جدا mount می‌شوند و schema disposable اجرا می‌شوند؛ secrets فقط داخل فرایند خوانده می‌شوند و در خروجی آزمون نیستند.

## فعال‌کردن نشست مشترک

برای اجرای چهار وب با Redis مشترک، از ریشهٔ پروژه در ویندوز `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-docker.ps1 -SharedSessions` و در macOS/Linux فرمان `bash scripts/start-docker.sh 4 shared` را بزنید. Redis فقط در شبکهٔ داخلی Compose اجرا می‌شود و راه‌انداز رمز مستقل آن را در `.runtime` می‌سازد. در این حالت درخواست‌ها بدون چسبندگی مرورگر بین وب‌ها پخش می‌شوند.

برای تغییر حالت در نصب فعلی، ابتدا `docker compose -f deployments/compose.capacity.yaml down` را اجرا کنید تا کانتینرهای قبلی متوقف شوند و volume PostgreSQL حفظ شود. سپس راه‌انداز نشست مشترک را بزنید. برای توقف این حالت از `docker compose -f deployments/compose.shared.yaml stop` استفاده کنید. کاربران پس از تغییر حالت یک بار دوباره وارد می‌شوند.

## اجرای اختیاری HTTPS

گواهی `cert.pem` و کلید `key.pem` مربوط به میزبان را در `.runtime/tls` قرار دهید یا `HRMS_TLS_DIR` را به پوشهٔ خصوصی گواهی تنظیم کنید. کلید برای کاربر پراکسی با UID 10001 خواندنی باشد. secretهای عادی را با راه‌انداز موجود آماده کنید و سپس از ریشهٔ پروژه اجرا کنید.

```powershell
docker compose -f deployments/compose.capacity.yaml -f deployments/compose.https.yaml up --build -d --wait
```

همان پورت با `https://` کار می‌کند و کوکی نشست و کوکی پراکسی Secure می‌شوند. برای حالت Redis، فایل اول `deployments/compose.shared.yaml` است. گواهی و کلید در پوشهٔ خصوصی نصب می‌مانند. گواهی واقعی باید نام دامنهٔ مقصد را پوشش دهد و برای مرورگر کاربران قابل اعتماد باشد.

## اجرای وب روی دستگاه‌های مستقل

این الگو برای استقرار آینده است. هر دستگاه همان image وب از یک نسخهٔ پروژه را اجرا می‌کند. یک بار روی وب اول `python entrypoint.py` را برای آماده‌سازی پایگاه اجرا کنید. وب‌های دیگر با `python entrypoint.py --web-only` راه می‌افتند و seed اجرا نمی‌کنند. فایل‌های رمز را روی هر میزبان به‌صورت خصوصی mount کنید و مسیر آن‌ها را در `DB_PASSWORD_FILE`، `ADMIN_PASSWORD_FILE` (الزام فعلی entrypoint) و `HRMS_REDIS_PASSWORD_FILE` قرار دهید.

- `DB_HOST` را نشانی خصوصی PostgreSQL و `DB_PORT`، `DB_NAME` و `DB_USER` را مشخصات نصب مشترک بگذارید.
- برای هر وب `HRMS_SESSION_BACKEND=redis`، `HRMS_REDIS_HOST` و `HRMS_REDIS_PORT` را روی سرویس مشترک تنظیم کنید. همهٔ وب‌های همان سامانه باید `HRMS_REDIS_NAMESPACE` و `SESSION_HOURS` یکسان داشته باشند. برای Redis با TLS، `HRMS_REDIS_TLS=true` را تنظیم کنید.
- `INSTANCE_ID` برای هر وب یکتا باشد. دسترسی به پورت 8000 وب‌ها فقط از پراکسی ورودی روی شبکهٔ خصوصی باشد. PostgreSQL و Redis روی اینترنت منتشر نشوند.
- پراکسی ورودی بیرونی با TLS، فهرست upstream صریح از نشانی خصوصی وب‌ها و بررسی `/health` داشته باشد. `COOKIE_SECURE=true` روی وب‌ها تنظیم شود. درخواست‌های نوشتنی را در پراکسی خودکار تکرار نکنید. نشست مشترک امکان توزیع درخواست بدون affinity را می‌دهد.

اجرای این الگو روی چند میزبان فیزیکی و بازیابی پس از خرابی PostgreSQL یا Redis هنوز آزمایش نشده است. Redis این Compose نشست را روی دیسک ذخیره نمی‌کند. پس از راه‌اندازی مجدد Redis، کاربران دوباره وارد می‌شوند.

[ADR-10](../docs/05-architecture/ADRs/ADR-10-docker-compose-baseline.md) طرح قبل از کد را ثبت می‌کند. این baseline، ظرفیت 500 کاربر یا HA نیست؛ آزمایش مشترک وب+DB و monitoring هنوز انجام نشده‌اند. create_all و seed موجود migration نسخه‌دار نیستند. تاریخ‌ها میلادی و حقوق آموزشی‌اند.

[گزارش اجرای واقعی](../docs/05-architecture/experiments/EXP-DOCKER-COMPOSE.md): دو سرویس healthy، 41 آزمون اصلی، 98 بررسی رگرسیون و حفظ marker ساختگی پس از stop/start. verifier موقت و schema آزمون حذف شدند؛ دو سرویس کاربردی روشن مانده‌اند. آزمون‌ها با نام جدید قابل تکرارند:

```powershell
.\.venv\Scripts\python.exe scripts/run_docker_checks_20261116.py --name docker-next-run
.\.venv\Scripts\python.exe scripts/verify_docker_deployment_20261116.py --output docs/08-testing/evidence/docker-deployment-next.json
```

## آزمایش ایزولهٔ اندازهٔ گروه وب

برای مقایسهٔ چهار و شش وب با ۵۰۰ ورود هم‌زمان، از همان ابزار Docker استفاده کنید. هر نام باید تازه باشد. ابزار برای هر اجرا پروژه، پورت، volume و دادهٔ آزمایشی جدا می‌سازد و منابع Docker همان اجرا را پس از پایان جمع می‌کند. [پروتکل و نتایج](../docs/05-architecture/experiments/EXP-DOCKER-LOGIN-WEB-SCALE.md)

```powershell
.\.venv\Scripts\python.exe scripts/run_login_storm_20261117.py --name compare-four-new --web-workers 4
.\.venv\Scripts\python.exe scripts/run_login_storm_20261117.py --name compare-six-new --web-workers 6
```
