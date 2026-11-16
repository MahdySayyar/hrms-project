# اجرای Docker پروژه

اگر پورت 8001 اشغال است، در PowerShell قبل از launcher فرمان `$env:HRMS_HTTP_PORT='8002'` یا در Bash فرمان `HRMS_HTTP_PORT=8002 bash scripts/start-docker.sh` را اجرا کنید؛ سایت روی localhost:8002 باز می‌شود. برای استفادهٔ بعدی از همان پورت، همین تنظیم را هنگام راه‌اندازی نگه دارید.

برای نسخهٔ دانلودشده در ویندوز `start-docker.cmd` را دوبار کلیک کنید؛ در macOS/Linux فرمان `bash scripts/start-docker.sh` را از ریشه بزنید. فقط Docker با Linux containers و Compose v2 لازم است. کانتینر موقت initializer رمزهای نصب را تولید و حذف می‌شود؛ دو سرویس کاربردی باقی می‌مانند. نصب تازه به `.env`، Python میزبان یا فایل‌های رایانهٔ سازنده نیاز ندارد.

برای بروزرسانی یک clone، در ریشه `git pull --ff-only` و سپس launcher را دوباره اجرا کنید. برای نصب از ZIP، فایل‌های نسخهٔ جدید را جایگزین کنید و پوشهٔ خصوصی `.runtime` را نگه دارید. اگر secretها را حذف کنید ولی volume را نگه دارید، رمزهای تازه با پایگاه موجود سازگار نخواهند بود. تغییر schema قدیمی همچنان نیازمند راهنمای مهاجرت همان نسخه است.

برای رفع مشکل از `docker compose -f deployments/compose.yaml ps` و `docker compose -f deployments/compose.yaml logs --tail=100 web db` استفاده کنید. Docker باید روشن باشد و پورت 8001 آزاد باشد. آماده‌شدن اولین build به سرعت اینترنت بستگی دارد.

دو سرویس `web` و `db` در پروژهٔ Compose به نام `hrms-docker`. وب یک پردازه دارد؛ نشست‌ها حافظه‌ای‌اند. PostgreSQL روی شبکهٔ داخلی Compose و volume مستقل است. دادهٔ اولیه نمونهٔ ساختگی کد است؛ داده یا رمز نسخهٔ native منتقل نشده است.

از ریشهٔ پروژه:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-docker.ps1
docker compose -f deployments/compose.yaml ps
```

سایت Docker: [ورود](http://localhost:8001/login). نام کاربری `hradmin` و رمز اختصاصی Docker در فایل محلی `.runtime/docker-hrms-secrets/admin_password` است؛ آن را وارد Git، گزارش یا تصویر نکنید. برای حفظ کوکی‌های مستقل، Docker را با localhost و native را با 127.0.0.1 باز کنید. راه‌اندازی مجدد رمزهای موجود را عوض نمی‌کند. Compose secret محلی فایل runtime است، تضمین رمزنگاری Swarm نیست.

توقف/شروع با حفظ volume:

```powershell
docker compose -f deployments/compose.yaml stop
docker compose -f deployments/compose.yaml start
```

برای حذف کانتینرهای همین پروژه با حفظ داده از `down` بدون گزینهٔ حذف volume استفاده کنید. دادهٔ native و دیگر پروژه‌های Docker تحت این فرمان‌ها نیستند. DB هیچ پورت میزبان ندارد. healthcheck وب وابستگی PostgreSQL را هم بررسی می‌کند.

Dockerfile فقط requirements، app، templates، static و entrypoint را کپی می‌کند. .env، .runtime، tests، docs و artifacts از build کنار گذاشته شده‌اند. core/regression با منابع تستی که موقتاً جدا mount می‌شوند و schema disposable اجرا می‌شوند؛ secrets فقط داخل فرایند خوانده می‌شوند و در خروجی آزمون نیستند.

[ADR-10](../docs/05-architecture/ADRs/ADR-10-docker-compose-baseline.md) طرح قبل از کد را ثبت می‌کند. این baseline، ظرفیت 500 کاربر یا HA نیست؛ آزمایش مشترک وب+DB و monitoring هنوز انجام نشده‌اند. create_all و seed موجود migration نسخه‌دار نیستند. تاریخ‌ها میلادی و حقوق آموزشی‌اند.

[گزارش اجرای واقعی](../docs/05-architecture/experiments/EXP-DOCKER-COMPOSE.md): دو سرویس healthy، 41 آزمون اصلی، 98 بررسی رگرسیون و حفظ marker ساختگی پس از stop/start. verifier موقت و schema آزمون حذف شدند؛ دو سرویس کاربردی روشن مانده‌اند. آزمون‌ها با نام جدید قابل تکرارند:

```powershell
.\.venv\Scripts\python.exe scripts/run_docker_checks_20261116.py --name docker-next-run
.\.venv\Scripts\python.exe scripts/verify_docker_deployment_20261116.py --output docs/08-testing/evidence/docker-deployment-next.json
```
