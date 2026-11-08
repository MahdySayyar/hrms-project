# MILESTONE-CAT-01 — تقویم، Gate و Definition of Done

تقویم اصلی از [اسلاید 53](https://sadprojectdocs.space-z.ai/#slide-53) است؛ هفته‌ها نسبی‌اند. تاریخ شروع واقعی ترم و برنامهٔ اعضا هنوز دریافت نشده است. وجود مدارک امروز به معنی عبور تاریخی از Gateهای پیش از کدنویسی نیست.

| Milestone / هفته | خروجی و Gate | وضعیت فعلی مدارک |
|---|---|---|
| M1 / 1–2 | مسئله، ذی‌نفع، scope و هدف روشن؛ review منشور | CH-01 آماده؛ review انسانی باز |
| M2 / 3–4 | FR/NFR/BR اتمیک، قابل تست، منبع/فرض‌ها مشخص | 25 FR، 22 BR و 11 NFR ثبت؛ اهداف پیشنهادی نیازمند تأیید |
| M3 / 5–6 | Context/Use Case/Domain و سه UC کامل با sequence/activity/state سازگار | مدل‌ها آماده و parse شده؛ اغلب بازسازی؛ review انسانی باز |
| M4 / 7–8 | سه alternative، معماری اجرا، ADR و quality scenario | مونولیت و مرز تصمیم مستند؛ تأیید استدلال انسانی باز |
| M5 / 9–10 | component/class/API/DB و سه YAML spec | مدارک و export واقعی آماده؛ review design باز |
| M6 / 11–12 | سه Core end-to-end و رکورد واقعی prompt/input/output/review/validation | Core موجود؛ 2 task ثبت؛ human review و transcript تاریخی کامل موجود نیست |
| M7 / 13–14 | test/traceability/change/report/presentation/demo | شواهد فنی و برنامهٔ دمو آماده؛ NFR/آزمایش‌های معماری و پذیرش نهایی باز |

اسلاید 17 برنامهٔ جزئی هر هفته را می‌دهد: 1 Proposal، 2 Requirements v1، 3 Review، 4 Specification، 5 Analysis، 6 Dynamic، 7 Architecture، 8 Design، 9 Design Review، 10 AI Transformation، 11 Implementation، 12 Testing، 13 Evaluation، 14 Demo. این برنامه، جزئیات زمانیِ ارائه است؛ با جدول دو هفته‌ای اسلاید 53 مخلوط و به تاریخ انجام گذشته نسبت داده نمی‌شود.

## هفت شرط DoD

طبق [اسلاید 58](https://sadprojectdocs.space-z.ai/#slide-58): artifact وجود داشته باشد؛ review شده باشد؛ سازگاری داخلی داشته باشد؛ با مدارک قبلی سازگار باشد؛ شناسه داشته باشد؛ در Git commit شود؛ به مدارک مرتبط وصل شود.

فایل/شناسه/پیوند و کنترل‌های فنی آماده‌اند. commit حاوی این نسخه با Git قابل شناسایی است. شرط review انسانی برای مدل/نیازمندی/ADR/TRF باز است؛ پس «همهٔ artifactها Done» یا «همهٔ Gateها Passed» ثبت نمی‌شود.

## ارزیابی و مسئولیت

در هر Gate، درستی، کامل بودن، سازگاری، قابلیت ردیابی و توجیه بررسی شود. نتیجه با reviewer/date/version/action ثبت شود. اگر نقص وجود دارد، artifact اصلاح و دوباره بررسی شود. وزن‌های Milestone در اسلاید 62: M1=5٪، M2=10٪، M3=15٪، M4=15٪، M5=15٪، M6=20٪، M7=20٪؛ مستقل از دسته‌های [Rubric](rubric.md).

این نسخه، مبنای review و ادامهٔ مهندسی است. اجرای اصلاح فنی در این گفت‌وگو به درخواست مستقیم کاربر انجام شده و جای تایید دانشگاهی Gateها نیست.
