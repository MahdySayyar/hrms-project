# EXP-NATIVE-TRANSPORT — گزارش اصلاح transport آزمایش

2026-11-15؛ ADR-08، D-01 و قرارداد UC-01 پیش از کد این تغییر ثبت شدند؛ این گزارش پس از اجرا تکمیل می‌شود. review انسانی و Gate باز.

اصلاح: HTTPX خروجی proxy با aiohttp 3.13.2 جایگزین شد؛ CookieJar غیرفعال، redirect/decompression/retry خاموش، حفظ روش/body/query/کوکی‌های متعدد، حذف headerهای hop-by-hop و Connection-nominated. برنامهٔ HR، تعداد وب و پارامترهای pool/thread ثابت‌اند. parser binary در wheel نصب‌شده استفاده می‌شود. غیرفعال‌کردن retry به attribute داخلی نسخهٔ pinned وابسته است؛ ارتقای aiohttp باید این قرارداد را دوباره بررسی کند.

[آزمون سه قرارداد با backend واقعی disposable](../../08-testing/evidence/proxy-transport-20261115-b.json) موفق شد. نخستین اجرای تست به‌علت حساس‌بودن نام header در assertion خطا داشت؛ [خروجی ناموفق](../../08-testing/evidence/proxy-transport-20261115-a.json) حفظ شد و assertion به نام‌های lowercase تبدیل شد.

[اجرای 50 نفر](../../08-testing/evidence/capacity-aiohttp-50-20261115-a.json): 30.1s steady، 5167 درخواست، صفر خطا، P95=481ms، 171.84 RPS؛ burst مرخصی 50/50 با پاسخ 303 و ذخیره/audit یکتا موفق شد. این نتیجهٔ exploratory است؛ مقایسه با اجرای تاریخی 50 نفر، به‌سبب تاریخ و spawn rate متفاوت مقایسهٔ آماری کنترل‌شده نیست. مقایسهٔ تازهٔ 500 نفر و اجرای پذیرش کامل جدا ثبت می‌شوند.

[اجرای تازه 500 نفر](../../08-testing/evidence/capacity-aiohttp-500-20261115-a.json): هر 500 کاربر وارد شدند؛ 30s steady، 5144 درخواست، یک timeout (0.0194٪)، P95=3063ms و 171.2 RPS. در مقایسهٔ تازهٔ پیش از تغییر، failure از 68.87٪ به 0.0194٪ کاهش یافت ولی معیار سرعت برقرار نشد. burst 500 مرخصی هم فقط 403/500 تأیید ذخیره/audit داشت و موفق نبود. هر دو اجرا همان چهار وب/8 thread/10 pool و نرخ ورود 5 داشتند؛ core/ابزارهای طراحی در مرحلهٔ ورود به‌طور مستقل اجرا شدند و ممکن است بخشی از ابتدای steady اجرای بعد را هم تحت فشار گذاشته باشند. مقایسه کنترل منابع انحصاری و تکرار آماری ندارد.

[نمونه‌گیری تفکیکی پس از transport در 50 نفر](../../08-testing/evidence/capacity-aiohttp-profile-50-20261115-a.json): 5166 درخواست، صفر خطا، P95=425ms؛ میانگین CPU proxy=41.8٪ یک هسته، مجموع وب‌ها=252.5٪ و PostgreSQL backend=217٪. proxy دیگر عامل غالب قبلی نیست. گلوگاه burst از بازبینی مسیر فرم به [ADR-09](../ADRs/ADR-09-submitted-reference-validation.md) منتقل شد.
