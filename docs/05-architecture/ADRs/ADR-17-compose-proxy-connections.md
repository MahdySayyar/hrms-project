# ADR-17 — اتصال proxy در burst ورود Docker

2026-11-17؛ طرح پیش از اصلاح transport این گام؛ review انسانی pending. [آزمون چهار وب با صف خصوصی](../../08-testing/evidence/login500-fourweb-after-20261117-a.json) تمام 500 ورود/نشست/audit را تأیید کرد، ولی یک probe داشبورد در حدود ثانیهٔ 46، طی 15ms با 503 پاسخ گرفت؛ 903/904 probe موفق، P95 کلی=78ms و health تماماً موفق بود. علت دقیق exception در نسخهٔ قبلی log نشده بود و قطعی تلقی نمی‌شود.

فرضیهٔ محدود: connector proxy اتصال idle را تا 15s بازاستفاده می‌کند، در حالی که Uvicorn پیش‌فرض keep-alive پنج ثانیه دارد؛ خطای اتصال قدیمی ممکن است بدون retry به 503 تبدیل شود. در حالت Compose اتصال HTTP خروجی پس از هر پاسخ بسته می‌شود تا اتصال idle بازاستفاده نشود. native transport تاریخی همان تنظیم قبلی را حفظ می‌کند. این تصمیم ممکن است throughput بار مداوم را کم کند؛ فقط burst ورود این گام دوباره سنجیده می‌شود.

proxy همچنان هیچ method را خودکار retry نمی‌کند؛ GET CSV هم audit دارد و بدون تحلیل مجاز به retry نیست. exception فقط با class، method و worker index log می‌شود؛ body/URL/کوکی/credential log نمی‌شوند. درخواست‌هایی که backend واقعاً قطع است همچنان 503 می‌گیرند. timeout ورود ابزار تا 180s با سقف صریح proxy هماهنگ می‌شود؛ زمان واقعی جدا گزارش می‌شود و افزایش deadline به‌تنهایی موفقیت سرعت نیست.

FR-01، BR-01/02، UC-01 و D-01 در حالت Compose این سیاست اتصال و failure را ثبت می‌کنند. هیچ سیاست کوکی/CSRF، قدرت hash، تراکنش یا topology تازه‌ای در این اصلاح نیست. همچنین بازخوانی نهایی حساب هنگام audit با FOR UPDATE کوتاه، تغییر concurrent active/hash را تا پایان همان تصمیم سری می‌کند؛ DB در حین صف/hash بسته می‌ماند. آزمون منفی قطع backend و عدم retry، اتصال‌های مجزا و cookieهای جدا، core/coverage و همان 500 لاگین/probe تکرار می‌شوند.
