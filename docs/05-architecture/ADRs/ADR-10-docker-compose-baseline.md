# ADR-10 — استقرار مستقیم Docker Compose طبق درخواست کاربر

2026-11-16؛ طرح قبل از کد استقرار؛ پذیرش انسانی و Gate باز.

درخواست مستقیم کاربر: «کانتینر هات کجان برام بزارشون تو داکر». بررسی واقعی نشان داد Dockerfile موجود صفر بایت بود و daemon خاموش بود؛ Docker Desktop با CLI روشن شد. هیچ کانتینر موجودِ پروژه برای ادامه وجود نداشت.

انتخاب محدود: یک کانتینر وب FastAPI با یک پردازهٔ Uvicorn و یک کانتینر PostgreSQL 17.6 در شبکهٔ Compose جدا. داده در volume نام‌دار تازه، فقط seed نمونهٔ کد؛ پورت وب روی localhost:8001 و DB بدون پورت میزبان. وب native روی 8000 و دادهٔ فعلی بدون انتقال/حذف باقی می‌مانند. کاربر استقرار مستقیم Docker را خواسته است؛ آزمایش کانتینر مشترک وب+DB در EXP-01 انجام نشده و اجرای مستقیم Compose به معنی آن آزمایش نیست.

رمزهای تازهٔ مخصوص کانتینر در مسیر ignored زیر .runtime تولید می‌شوند و به‌صورت Compose secret file فقط هنگام اجرا mount می‌شوند. .env و credential فعلی خوانده/کپی/ارسال به build یا گزارش نمی‌شوند. entrypoint رمز را از فایل می‌خواند، DATABASE_URL را در حافظه می‌سازد، seed نمونهٔ idempotent موجود را در DB جدید اجرا می‌کند و با exec یک Uvicorn را PID 1 می‌کند. رمز در آرگومان فرمان نیست. Compose secrets محلی، رمزنگاری secret در Swarm نیستند. seed/create_all مهاجرت نسخه‌دار نیست.

FR و BR رفتار HR را تغییر نمی‌دهند؛ UC-01 نشست حافظه‌ای، CSRF و نقش را در یک وب نگه می‌دارد. D-01/architecture و مدل deployment، این topology را قبل از کد ثبت می‌کنند. runtime غیر root، healthcheck DB/web، وابستگی readiness و restart unless-stopped، شبکه/volume جدا و Dockerfile allowlist کد/قالب/static انتخاب می‌شوند. فایل‌های تست/گزارش/کل workspace در تصویر وب کپی نمی‌شوند.

معیار اجرای این گام: image build، دو کانتینر healthy، GET /health و /login روی 8001، ورود/CSRF با حساب نمونهٔ همان DB، core PostgreSQL در schema disposable و کنترل وابستگی/مهندسی/parse مدل. توقف/start/recreate بدون حذف volume باید صحت اتصال و رکورد ساختگی نشانه‌دار را نگه دارد. هیچ real HR row در آزمون یا export استفاده نمی‌شود. شواهد با نام تازه ثبت می‌شوند.

ظرفیت: آزمون native قبلی چهار وب با 500 نشست/300s، 57565 درخواست و یک failure و P95=2276ms داشت؛ burst مرخصی کامل موفق بود اما NFR سرعت و هدف صفر failure تأیید نشد. این Docker baseline به‌تنهایی ظرفیت 500 یا HA را اثبات نمی‌کند. اضافه‌کردن replica/session مشترک/monitoring نیازمند آزمایش جدا است و در درخواست Docker به‌صورت خودکار انجام نمی‌شود.

بازگشت: توقف فقط project Compose همین پروژه بدون down -v؛ بازگشت به وب native موجود. image، network و volume دیگر پروژه‌ها تغییر نمی‌کنند. آزمایش مشترک EXP-01 و بار Docker/monitoring هنوز pending خواهند بود تا واقعاً اجرا شوند.
