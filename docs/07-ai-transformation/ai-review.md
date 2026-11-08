# AI-REVIEW-01 — بازبینی خروجی و مرحلهٔ انسانی

بازبینی فنی توسط عامل: قواعد terminal state، علت رد، notes boundary، scope، قفل درخواست/کارمند، یک transaction تصمیم+audit، retry و rollback با آزمون و خواندن کد بررسی شدند. service از HTTP/ORM module جدا و خروجی DB/API با برنامه تطبیق داده شد.

موارد اصلاح‌شده توسط عامل: 303 مبهم برای تصمیم مخالف به 409؛ تفکیک Domain/Service/Repository برای گردش تصمیم؛ clock مستقل از hr_models؛ بهبود ابزار snapshot و اجرای آزمایش روی schema مستقل؛ اصلاح syntax دو نمودار sequence پس از parse. این‌ها «اصلاح دستی دانشجو» نیستند.

در TRF-01 مقدار قبل از اصلاح از اجرای واقعی ثبت شد. در TRF-02 وابستگی قبلی با خواندن import مشاهده شد؛ اجرای failing boundary قبل از آن تغییر ثبت نشده است. Coverage از اجرای واقعی به دست آمد و کلیت HRMS را پوشش نمی‌دهد.

| موضوع بازبینی دانشجو/استاد | وضعیت و شاهد لازم |
|---|---|
| درستی منشور/نیازهای HR و scope | pending؛ نام reviewer، تاریخ و نتیجه |
| تأیید FR/BR و هدف NFR | pending؛ رفع ابهام حقوق تاریخی و تقویم |
| سازگاری مدل و code/API/schema | pending؛ review مدل‌ها و traceability |
| توجیه ADR و هزینهٔ مرز داخلی | pending؛ توضیح شفاهی دانشجو |
| پذیرش TRF-01/TRF-02 | pending؛ Accepted/Modified/Rejected با دلیل |
| اصلاحات واقعی انسان | گزارشی دریافت نشده؛ فقط اگر انجام شد ثبت شود |
| یادگیری و مشارکت اعضا | نامشخص؛ از commit عامل نتیجه گرفته نمی‌شود |

برای ثبت review، رکورد جدید با reviewer/date/artifact/version/result ایجاد شود؛ تکمیل خودکار یا امضای فرضی مجاز نیست.
