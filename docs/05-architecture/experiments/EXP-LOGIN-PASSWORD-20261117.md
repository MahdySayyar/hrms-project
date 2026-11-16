# EXP-LOGIN-PASSWORD — شاهد مستقل صف خصوصی رمز

2026-11-17؛ ADR-16، FR-01/BR-01/02، UC-01، طراحی و مدل پیش از این کد نوشته شدند. review انسانی و Gate pending هستند. مشکل مشاهده‌شده، thread عمومی و اتصال DB درگیر PBKDF2 هنگام 500 ورود هم‌زمان بود.

خواندن snapshot حساب و final revalidation/audit تراکنش‌های کوتاه شدند؛ هنگام صف/hash هیچ اتصال DB نگه داشته نمی‌شود. یک executor خصوصی با سقف کار پذیرفته‌شده جدا از threadهای عمومی است. CSRF و active/hash پس از انتظار دوباره کنترل، audit commit و بعد cookie چرخانده می‌شود. PBKDF2 و iteration قبلی حفظ، بدون cache رمز یا نتیجه؛ ظرفیت پر 503 و Retry-After می‌دهد. helper runtime مرز Domain/Service/Repository جدید نیست.

| آزمون | نتیجه |
|---|---|
| [قبل، چهار وب](../../08-testing/evidence/login500-fourweb-before-20261117-a.json) | 500/500 ورود، 43/56 probe failure |
| [بعد از صف خصوصی](../../08-testing/evidence/login500-fourweb-after-20261117-a.json) | 500/500 ورود و نشست/audit؛ 903/904 probe موفق، P95 probe=78ms؛ یک 503 باقی‌مانده در proxy |
| [قراردادهای منفی و مرزی](../../08-testing/evidence/login-capacity-contracts-20261117-a.json) | 6/6 موفق: صف پر/آزاد، event loop، عدم نگه‌داری DB در hash، تغییر active/hash، CSRF حذف‌شده، audit شکست‌خورده و allowlist |
| [core نسخهٔ دانلودی](../../08-testing/evidence/core-docker-login500-download-20261117-a.json) | 57/57 موفق شامل startup secondary worker و رفتارهای قبلی |

تأخیر معمول probe از timeoutهای دو ثانیه‌ای به زیر 100ms رسید و /health در تمام 452 بررسی همان اجرا موفق بود. تمام ورودها 114.39s طول کشیدند؛ این اصلاح پاسخ‌گویی سایر صفحات را بهتر کرد، ولی سرعت انجام تمام hashها روی میزبان را سریع‌تر نکرد. یک خطای proxy مانع قبول هدف خطای صفر همان اجرا شد و در ADR-17 جدا بررسی شد. منابع/شکست‌های قبلی حفظ، دادهٔ ساختگی/schema/project حذف شدند؛ آزمون تصویری یا mixed capacity ادعا نمی‌شود.
