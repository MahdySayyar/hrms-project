# OPEN-01 — کارهای باز با شرط پایان

| کار | شرط پایان و مدرک |
|---|---|
| بازبینی انسانی فرآیند | reviewer/date/result برای CH/FR/BR/NFR/model/ADR/design/TRF و Gateها |
| سیاست واقعی HR | حقوق تاریخی، تقویم، گزارش انتساب تاریخی، ساعات خدمت و SLA روشن و spec اصلاح شود |
| coverage رفتاری Extended | مثبت/منفی/مرزهای قواعدِ خارج از سه Core با evidence مستقل |
| CI واقعی | workflow آماده اجراست؛ اجرای remote pipeline و نتیجه هنوز ثبت نشده |
| ظرفیت و فشار ورود | بار login جدا و NFR-01 با شرایط کامل، CPU/RAM/DB connections و raw data |
| EXP-01/02 | کانتینر مشترک سپس Compose/پایش و مقایسهٔ منصفانه |
| EXP-03/04 | replicas/Service، failure زیر بار، storage و بازیابی واقعی |
| EXP-05/06 | نشست مشترک، cache/read replica؛ مشاهدهٔ مشکل، fix و تکرار |
| EXP-07/08/09 | gateway/rate-limit، queue/worker و failure با سند هر تغییر |
| امنیت و recovery | TLS متناسب با استقرار، login rate limit، scan و timed restore |
| ارائه و مشارکت | PPTX/دموی نهایی، مشارکت واقعی اعضا و review شفاهی ثبت شود |
| قالب تحویل دانشگاه | Word/PDF یا فرم استاد اگر لازم شد از همین مدارک تهیه و بازبینی شود |

نسخهٔ کاربردی و نخستین اصلاح معماری موجودند. این فهرست نشان می‌دهد چارچوب مهندسی آماده شده ولی کل مسیر مقیاس‌پذیری یا تأیید همهٔ خواسته‌های استاد هنوز به پایان نرسیده است. [نقشهٔ EXP](../05-architecture/progressive-experiments.md) ترتیب آزمایش‌ها را مشخص می‌کند.
