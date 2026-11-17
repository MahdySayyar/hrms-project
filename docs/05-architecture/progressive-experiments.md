# EXP-CAT-01 — مسیر آزمایش‌های معماری

این نقشه بر [ارائهٔ ۳۳ اسلایدی](../scalability-slide-review.md) و هدف مستقیم کاربر استوار است. شرط هر گام: نسخهٔ مبنا، مشکل/فرضیه، بار و دادهٔ ثابت، متریک خام، قبل/بعد، محدودیت و ADR. فناوریِ پیشنهادی تا اجرای واقعی به‌عنوان ساخته‌شده گزارش نمی‌شود.

بازبینی 2026-11-17: جدول زیر فهرست آزمایش‌های آموزشیِ قبلی است و دستور اجرای اجباری همهٔ فناوری‌ها نیست. [اولویت‌های متناسب با محصول فعلی](current-architecture-review-20261117.md) مبنای قدم بعدند. N+1 نام منابع، ورودی حجیم CSV و کلید ماه با ADR-11/12/13 اصلاح شدند؛ ایندکس، shared session، cache، replica، queue و gateway به شرط شاهد مسئله انتخاب می‌شوند. EXP-01 یا Kubernetes صرفاً برای تکمیل ترتیب درس به محصول اضافه نمی‌شود.

| شناسه | گام و مشکل مورد بررسی | اقدام و معیار | وضعیت |
|---|---|---|---|
| EXP-00 | کنترل ابزار و بار native | یک وب/DB، 10 کاربر، 20s، 100 پروندهٔ ساختگی؛ P95/P99/RPS/errors و نسبت خواندن | اجرا شده؛ baseline سبک |
| EXP-01 | رقابت منابع در کانتینر مشترک | بسته‌بندی وب+PostgreSQL در یک container؛ ramp 50/100/250/500؛ CPU/RAM/DB connections | اجرا نشده |
| EXP-02 | جداسازی وب و DB | Compose، network/volume، سپس monitoring و تکرار workload | baseline Docker طبق ADR-10 در 2026-11-16 اجرا شده؛ بار و monitoring باز |
| EXP-03 | محدودیت یک وب و توزیع درخواست | Kubernetes، 1/3/5/10 replicas، Service و instance متمایز؛ latency/throughput/resources | اجرا نشده |
| EXP-04 | از دست رفتن نمونه/داده | حذف Pod زیر بار، readiness و recovery؛ StatefulSet/PV/PVC برای DB و آزمون حفظ داده | اجرا نشده |
| EXP-05 | گم‌شدن نشست بین replicaها | ابتدا نمایش مشکل نشست محلی؛ سپس shared sessions در Redis و تکرار | [آزمون Docker روی یک میزبان](experiments/EXP-SHARED-SESSIONS-20261117.md) |
| EXP-06 | فشار خواندن و stale cache | read replica و routing/lag؛ Redis cache برای مسیر اندازه‌گیری‌شده؛ OFF/ON، invalidation/stampede | اجرا نشده |
| EXP-07 | فشار ورود/burst | پروفایل login جدا، CPU هزینه PBKDF2، gateway/rate limit؛ 429، burst/refill و بازیابی | اجرا نشده |
| EXP-08 | گزارش طولانی در درخواست | baseline همگام؛ RabbitMQ و worker، 202/job؛ 1/3/5 worker، queue depth و failure | اجرا نشده |
| EXP-09 | خرابی وابستگی‌ها | worker/Redis/DB/replica/network failure؛ اثر کاربر، recovery و ADR | اجرا نشده |

نشست حافظه‌ای عمداً برای مرحلهٔ مشاهدهٔ مشکل حفظ شده است. load فعلی ورود را برای setup انجام می‌دهد ولی latency workload آن را جدا می‌کند؛ آزمایش اشباع login نیست. «overflow» فرضیهٔ علت نیست: CPU، اتصال DB، RAM، timeout و ازدحام باید اندازه‌گیری شوند.

مقایسه‌های آینده باید generator، حجم و توزیع داده، ترکیب خواندن/نوشتن، زمان ramp و steady state، commit، تعداد وب/worker، محدودیت منابع، settings pool و query plan را ثبت کنند. RPS بدون P95/خطا یا با بار متفاوت، بهبود را اثبات نمی‌کند.

Sharding، CDN شبیه‌سازی‌شده و چند cluster مراحل پیشرفته‌اند و فقط پس از نیاز و تعیین محدوده مطرح می‌شوند. Dockerfile و Compose وب/DB طبق درخواست مستقیم کاربر اجرا شدند. مرحلهٔ کانتینر مشترک EXP-01، monitoring، Kubernetes و RabbitMQ بازند. Redis برای نشست مشترک روی یک میزبان آزمایش شده است. [راهنمای اجرا](../../deployments/README.md) و [ADR-10](ADRs/ADR-10-docker-compose-baseline.md).
