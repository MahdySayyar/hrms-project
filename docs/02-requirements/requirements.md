# REQ-CAT-01 — نیازمندی‌ها و قواعد منابع انسانی

نسخهٔ ۱، 2026-11-08. وضعیت: رفتار موجود بازسازی شده و اهداف عددی پیشنهاد شده‌اند؛ review دانشجو/استاد هنوز ثبت نشده است. منبع [SRC-01](sources.md) و نسخهٔ ماشین‌خوان [requirements.yaml](../../specs/requirements.yaml) است.

## نیازمندی‌های عملکردی

| شناسه | نام | قرارداد پذیرش | کاربرد |
|---|---|---|---|
| FR-01 | Authenticate | حساب فعال با رمز صحیح وارد شود؛ ورودی نادرست 401 و CSRF نامعتبر 403. | UC-01 |
| FR-02 | End session | خروج معتبر نشست را باطل و صفحهٔ محافظت‌شده را به login هدایت کند. | UC-01 |
| FR-03 | Roles and organizational scope | viewer فقط گزارش کلی؛ hr عملیات مجاز در شعبه/واحد؛ admin قابلیت‌های مدیریتی. | UC-01 |
| FR-04 | Employee records | ثبت و ویرایش پرونده با کد یکتا و شعبه/واحد سازگار؛ ورودی نامعتبر 400. | UC-04 |
| FR-05 | Employee activity | تغییر active بدون حذف پرونده؛ مقادیر غیر true/false رد شوند. | UC-04 |
| FR-06 | Employee search | نام یا کد و فیلتر شعبه/واحد/وضعیت در محدودهٔ کاربر اعمال شوند. | UC-04 |
| FR-07 | Organization data | شعبه، واحد وابسته و سمت با کنترل تکرار/وابستگی ثبت و ویرایش شوند. | UC-05 |
| FR-08 | Recruitment candidates | متقاضی با اطلاعات معتبر و محدودهٔ مجاز ثبت شود؛ پذیرش بدون مصاحبهٔ قبول رد شود. | UC-06 |
| FR-09 | Interviews | مصاحبه ثبت شود؛ نتیجهٔ آینده و مصاحبه برای فرد hired/rejected رد شوند. | UC-06 |
| FR-10 | Hire and onboard | accepted به کارمند و سه وظیفهٔ پذیرش تبدیل شود؛ تکرار استخدام رکورد دوم نسازد. | UC-06 |
| FR-11 | Attendance and shifts | حضور/غیاب و دقیقهٔ کار/اضافه‌کاری با شیفت شب محاسبه؛ تردد آینده/قبل استخدام رد شود. | UC-07 |
| FR-12 | Create HR request | مرخصی/مأموریت/اداری با تاریخ معتبر، pending و audit ثبت شود. | UC-02 |
| FR-13 | Decide HR request | admin یک تصمیم نهایی دهد؛ retry یکسان بی‌نوشتن و retry مخالف 409؛ هم‌پوشانی رد شود. | UC-02 |
| FR-14 | Educational payroll rules | admin برای نوع قرارداد rule ماهانه/ساعتی و درصد/ضریب معتبر ثبت کند. | UC-03 |
| FR-15 | Payment profile | admin یک پروفایل مبلغ ریالی نامنفی برای کارمند بسازد؛ نرخ ساعتی مثبت هنگام محاسبه لازم است. | UC-03 |
| FR-16 | Payslip snapshots | محاسبهٔ employee/month یکتا و immutable با snapshot؛ ماه/پیش‌نیاز/خالص نامعتبر رد شود. | UC-03 |
| FR-17 | Contract lifecycle | ثبت draft، فعال‌سازی، تمدید و خاتمه با حداکثر یک قرارداد فعال برای هر کارمند. | UC-08 |
| FR-18 | Employee evaluations | امتیاز 0..100، بازخورد و هدف برای کارمند در محدوده ثبت شوند. | UC-09 |
| FR-19 | Training and enrollment | دوره و ثبت‌نام با ظرفیت، بدون ثبت‌نام تکراری و منع کاهش ظرفیت زیر اشغال. | UC-09 |
| FR-20 | Career plans | سمت هدف، تاریخ، اقدامات و progress در 0..100 ثبت شوند. | UC-09 |
| FR-21 | Assignment history | تغییر انتساب رکورد قبلی را ببندد و یک انتساب جاری با نام‌های snapshot بسازد. | UC-10 |
| FR-22 | Aggregate reports | تعداد/وضعیت/کارکرد/فیش دوره در محدودهٔ نقش نمایش داده شوند. | UC-11 |
| FR-23 | Employee CSV | CSV فارسی UTF-8 BOM در محدوده و با خنثی‌سازی فرمول، فقط برای hr/admin. | UC-11 |
| FR-24 | Operational audit | تغییر حساس همراه actor/time ثبت شود؛ نمایش audit فقط admin؛ شکست audit تصمیم را rollback کند. | UC-12 |
| FR-25 | Manage accounts | admin حساب/نقش/محدوده مدیریت کند؛ حذف آخرین مدیر/تنزل خود و تغییر نام/رمز موجود رد شود. | UC-12 |

برای هر FR، [FS-CAT-01](../../specs/functional-specifications.yaml) پیش‌شرط، قواعد، موفقیت/شکست و کد را ثبت می‌کند. جزئیات سه Core در UC-01 تا UC-03 است. باقی کاربردها هنوز سه مدل رفتاری تفصیلی مستقل ندارند؛ FR بدون شناسهٔ UC یا بدون منشأ ایجاد نشده است.

## قواعد کسب‌وکار

| شناسه | قاعده | FR |
|---|---|---|
| BR-01 | حساب فعال، hash صحیح و token نشست منقضی‌نشده لازم است. | FR-01, FR-03 |
| BR-02 | POST مرورگر token وابسته به نشست می‌خواهد؛ login نیز مستثنا نیست. | FR-01, FR-02, FR-12, FR-13, FR-16 |
| BR-03 | viewer گزارش کلی؛ hr عملیات HR؛ admin تصمیم/حقوق/حساب/audit. | FR-03 |
| BR-04 | پرونده خارج از scope با 404 پنهان و انتخاب سازمان خارج از scope با 403 رد شود. | FR-03 |
| BR-05 | کد پرسنلی یکتا در برنامه و پایگاه است. | FR-04, FR-10 |
| BR-06 | unit/branch در فرم و foreign key مرکب باید سازگار باشند. | FR-04, FR-07, FR-08 |
| BR-07 | start <= end؛ administrative یک روز دارد؛ وضعیت اولیه pending. | FR-12 |
| BR-08 | pending یک بار نهایی می‌شود؛ retry یکسان بدون تغییر؛ تصمیم مخالف یا state نامعتبر 409. | FR-13 |
| BR-09 | rejected توضیح غیرخالی می‌خواهد؛ review_notes حداکثر 3000 نویسه. | FR-13 |
| BR-10 | approved leave/travel همان کارمند با بازهٔ inclusive هم‌پوشان رد شود؛ قفل کارمند تأییدها را سری می‌کند. | FR-13 |
| BR-11 | profile و rule لازم‌اند؛ در حالت hourly نرخ مثبت؛ ورودی مبلغ نامنفی. | FR-14, FR-15, FR-16 |
| BR-12 | regular=worked-overtime؛ gross=base+overtime+benefits؛ net=gross-insurance-tax-deductions؛ گردکردن HALF_UP به ریال. | FR-14, FR-16 |
| BR-13 | یک فیش employee/ماه؛ retry از snapshot؛ edit route فیش وجود ندارد؛ حفاظت در سطح DB از UPDATE مستقیم نیست. | FR-16 |
| BR-14 | تغییر عملیاتی و audit در یک transaction؛ failure عملیات تصمیم هیچ وضعیت جزئی نسازد. | FR-10, FR-12, FR-13, FR-16, FR-17, FR-24 |
| BR-15 | accepted نیازمند interview passed؛ استخدام فقط accepted؛ تکرار استخدام رکورد دوم نسازد. | FR-08, FR-09, FR-10 |
| BR-16 | یک attendance در روز/کارمند؛ آینده و قبل hire ممنوع؛ کارکرد/اضافه‌کاری از شیفت و استراحت. | FR-11 |
| BR-17 | ویرایش فقط draft؛ قرارداد غیر دائم تاریخ پایان می‌خواهد؛ حداکثر یک active؛ تمدید زنجیره می‌سازد. | FR-17 |
| BR-18 | evaluation score و career progress در 0..100. | FR-18, FR-20 |
| BR-19 | ثبت‌نام یکتا employee/training؛ غیر cancelled ظرفیت مصرف می‌کند؛ کاهش زیر اشغال مجاز نیست. | FR-19 |
| BR-20 | حداکثر یک انتساب end_date NULL؛ تغییر سازمان، قبلی را ببندد و نام‌ها را snapshot کند. | FR-21 |
| BR-21 | مقدار با =، +، - یا @ پس از فضای آغازین با apostrophe خنثی شود. | FR-23 |
| BR-22 | نام کاربری ثابت؛ رمز اولیه حداقل 12 نویسه؛ رمز در edit تغییر نمی‌کند؛ یک admin فعال باقی بماند. | FR-25 |

BR-08 نسخهٔ اصلاح‌شدهٔ CR-01 است؛ اکثر BRها از کد موجود استخراج شده‌اند. قانون واقعی سازمان، محاسبهٔ حقوق تاریخی، تقویم جلالی و سیاست دقیق انتهای بازهٔ assignment هنوز باید با ذی‌نفع روشن شوند.

## نیازمندی‌های غیرعملکردی

| شناسه | شرط سنجش | وضعیت |
|---|---|---|
| NFR-01 | p95 < 2000ms; error fraction < 0.01; 500 authenticated concurrent users; 10000 employees; 80/20 read/write workload; 5 minutes steady after ramp | proposed_not_verified |
| NFR-P-02 | 500 authenticated users complete the defined read/write workload without incorrect scope, lost writes or duplicate transitions | proposed_not_verified |
| NFR-S-01 | Every protected capability follows the role/scope matrix; negative role and scope samples all rejected | partially_verified |
| NFR-S-02 | All mutation forms validate session CSRF; session cookie is HttpOnly/SameSite=Lax; non-static pages no-store and self CSP | partially_verified |
| NFR-AU-01 | Each changed request decision has one actor/time audit; identical retry none; injected audit failure leaves no decision | verified_for_request_decisions |
| NFR-A-01 | 99.5% during a defined 30-day service window, measured by external probes | proposed_not_verified |
| NFR-M-01 | Request decision domain and service import no HTTP/ORM/persistence module; route delegates decision rules and SQL | آزموده برای ماژول تصمیم؛ review انسانی باز |
| NFR-T-01 | At least 80% statement coverage in the explicitly governed package app/request_workflow, with positive/negative/boundary tests; report scope and uncovered lines | 96.6٪ در package تصمیم؛ دامنهٔ کل HRMS نیست |
| NFR-U-01 | Five representative HR users can create a valid request within 60 seconds without assistance | proposed_not_verified |
| NFR-L-01 | Browser UI is Persian/RTL with Persian display numbers; Gregorian date labels remain explicit | implemented_historical_browser_evidence |
| NFR-R-01 | Proposed RPO 24 hours and RTO 30 minutes, tested by restoring a copy into an isolated lab | proposed_not_verified |

۵۰۰ کاربر، ۹۹.۵٪، coverage و زمان انجام کار، نمونه‌های هدف آموزشی‌اند؛ از مشتری HR دریافت نشده‌اند. هدف ۳۰۰ms، AES-256 کیف پول و افزودن vendor در مثال غذا، الزام همان دامنه‌اند. برای HR، latency با بار مشخص، کنترل دسترسی، audit و آزمون package اصلاح‌شده مبناست. همهٔ اهدافی که شاهد کافی ندارند باز مانده‌اند؛ شکست آن‌ها با موفقیت smoke جایگزین نمی‌شود.
