# ADR-19 — نشست مشترک و آماده‌سازی سرورهای مستقل

ثبت 2026-11-17، پیش از کد جدید؛ review انسانی و Gate pending. scope مستقیم کاربر، تقسیم درخواست‌ها بین سرور مستقل و آماده‌سازی نشست است؛ هیچ VPS یا حساب میزبانی در دسترس نیست.

مسئلهٔ موجود: نشست حافظه‌ای ADR-03 با cookie affinity فقط در وب انتخاب‌شده قابل استفاده است و با restart آن وب از بین می‌رود. EXP-05 باید انتقال همان cookie به وب دوم و restart وب اول را در schema/project ساختگی مشاهده کند، سپس اصلاح را آزمایش کند. شاهد جدید با نام یکتا حفظ شود؛ آزمایش روی نشست‌ها یا داده‌های واقعی انجام نمی‌شود.

گزینه‌ها: affinity دائمی، نشست PostgreSQL، نشست Redis، JWT. Redis انتخاب می‌شود تا expire و ابطال فوری در یک store مشترک انجام شود؛ PostgreSQL همچنان مرجع حساب و audit است. هیچ cache حساب/رمز یا read replica اضافه نمی‌شود. Redis dependency عملیاتی جدید و نقطهٔ خرابی مشترک است، بنابراین این تغییر HA کامل نیست.

تصمیم: حالت native پیش‌فرض memory باقی بماند؛ استقرار چند وب آزمایش‌شده Redis مشترک داشته باشد. token تصادفی 256 بیتی در cookie؛ فقط SHA256(token) در key Redis؛ payload شامل admin_id، csrf و expires_at. TTL ناشناس 30 دقیقه، احراز‌شده SESSION_HOURS؛ حذف نشست روی logout، نبود/انقضای token روی هر worker دسترسی را قطع کند. rotation با عملیات اتمی شرط وجود نشست قبلی انجام شود؛ ابطال هم‌زمان اجازهٔ احیای نشست ندهد. connection pool محدود، timeout کوتاه، خطای Redis پاسخ فارسی 503 بدون fallback حافظه و بدون افشای URL/credential بدهد. SQL همچنان active account را در هر درخواست تازه بررسی کند؛ reuse فقط همان request و همان نشست معتبر.

Redis فقط شبکهٔ داخلی Compose، بدون host port، password از فایل secret محلی تازه، بدون dump نشست؛ restart Redis نشست‌ها را از بین می‌برد و ورود مجدد لازم است. restart وب نشست را از بین نبرد. عملیات sync Redis در مسیر async به threadpool سپرده شود. proxy جدید round-robin هر درخواست، بدون نیاز به affinity و بدون retry خودکار درخواست نوشته‌شونده است. proxy در این مرحله failover برای یک درخواست in-flight تضمین نمی‌کند.

ترتیب دقیق تراکنش ورود، پیش از کد: بعد از قفل و بازاعتبارسنجی حساب/CSRF، audit و hash در SQL آماده، rotation شرطی در store انجام، سپس SQL commit و در آخر cookie صادر شود. اگر commit شکست خورد نشست تازه حذف شود؛ token تازه پیش از commit هیچ‌گاه به مرورگر داده نمی‌شود. Redis و PostgreSQL تراکنش توزیع‌شده ندارند: قطع store هنگام cleanup می‌تواند token صادرنشده را تا TTL نگه دارد؛ token تصادفی آن در اختیار کاربر نیست. انقضا/ابطال قبل از rotation پاسخ 403 و rollback SQL دارد. شکست DB ممکن است نشست ناشناس قبلی را باطل کند و دریافت فرم تازه لازم شود.

قراردادهای آزمون پیش از کد: TC-01-19 دو client/store مستقل، expiry، revoke و rotation؛ TC-01-20 خرابی store fail-closed، revocation میان hash و commit و reuse داخلی درخواست؛ TC-01-21 cross-worker login/CSRF/logout، restart وب و حساب غیرفعال. EXP-05 قبل/بعد؛ سپس بار 500 حساب برای سنجش هزینهٔ store. deployment و launcher تنها بعد از شاهد موفق تغییر کنند.

آماده‌سازی چند دستگاه: نمونهٔ configuration وب با DB و Redis مشترک و یک reverse proxy دارای upstreamهای صریح روی شبکهٔ خصوصی، بدون seed هم‌زمان؛ ورودی عمومی TLS/secure cookie نیاز دارد. config قابل مرور ساخته می‌شود ولی استفادهٔ واقعی چند دستگاه، هزینه، DNS و HA وابستگی‌ها اثبات یا انجام نمی‌شوند. هیچ خرید/ساخت VPS خودکار مجاز تلقی نمی‌شود.
