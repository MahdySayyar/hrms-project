# TEST-CAT-01 — سناریوهای آزمون و شواهد

این انتظارات از specification و قواعد بازسازی/ثبت شده‌اند. آزمون تصمیم مخالف پیش از اصلاح، 409 را انتظار داشت و شکست واقعی ثبت شد. [نسخهٔ ماشین‌خوان](../../specs/test-cases.yaml) و [شاهد نهایی 29 آزمون](evidence/all-tests-final.json) مرجع‌اند. داده و حساب‌ها ساختگی و schema مستقل است.

| ID / UC | پیش‌شرط و سناریو | نتیجهٔ مورد انتظار |
|---|---|---|
| TC-01-01 / UC-01 | Anonymous session, active synthetic admin؛ Missing session, missing CSRF, wrong password, correct login, logout | 303 login redirect; 403/401 failures; rotated cookie; protected page succeeds; logout invalidates |
| TC-01-02 / UC-01 | Synthetic admin/hr/viewer and two branches؛ Out-of-scope employee and forbidden payroll/audit/users/CSV/decision | 404 hidden record; 403 forbidden capabilities; allowed report and scoped employee 200 |
| TC-01-03 / UC-01 | HR logged in؛ Deactivate account in isolated schema | Next protected request redirects 303 to login |
| TC-02-01 / UC-02 | Scoped HR and employee؛ End before start; then valid leave | 400 and zero requests; valid request is pending |
| TC-02-02 / UC-02 | Pending request and active admin؛ Approve once | 303; approved; reviewer/time populated; exactly one review audit |
| TC-02-03 / UC-02 | Pending request and admin؛ Reject with whitespace then nonblank notes | 400 without review audit; valid rejection 303 |
| TC-02-04 / UC-02 | Approved request with initial notes؛ Repeat approval with different notes | 303; one audit; original notes preserved |
| TC-02-05 / UC-02 | Approved request؛ Submit opposite rejected decision | 409; approved retained; one audit; baseline returned 303 |
| TC-02-06 / UC-02 | Approved leave 2030-01-01..02؛ Approve travel 2030-01-02..03 | 400 at shared boundary; pending travel and no review audit |
| TC-02-07 / UC-02 | Two overlapping pending requests for one employee؛ Two parallel HTTP approval submissions | One 303 and one 400; exactly one review audit |
| TC-02-08 / UC-02 | Pending request in isolated schema؛ Inject INSERT audit_log failure | 500; request remains pending; no review audit |
| TC-02-09 / UC-02 | Admin and pending request؛ Missing id; target pending; 3001 and 3000 character notes | 404; 400; 400; accepted 303 at maximum |
| TC-03-01 / UC-03 | Monthly fixture profile/rule/attendance؛ Calculate then change rule/profile and retry | Overtime 900000 and net 55015000 rial; same id/snapshots and one payslip |
| TC-03-02 / UC-03 | Hourly fixture, 600 worked and 120 overtime minutes؛ Calculate February 2025 | Base 2400000, overtime 900000, net 6055000 rial |
| TC-03-03 / UC-03 | Admin; no profile؛ 2025-13, not-a-month and valid month without prerequisites | All 400; no payslip |
| TC-03-04 / UC-03 | Hourly fixture with rate zero؛ Calculate valid period | 400; rate must be positive |
| TC-03-05 / UC-03 | Fixture deductions 1000000000؛ Calculate negative net | 400 and zero saved payslips |

## قواعد مستقل و مرز معماری

| ID | سناریو | نتیجه |
|---|---|---|
| TC-02-U01 | Pending accepts approved and rejected | Both transitions return true |
| TC-02-U02 | Repeat either final decision | Both return false |
| TC-02-U03 | Both opposite final transitions | ReviewError status 409 |
| TC-02-U04 | Unknown stored state | INVALID_REQUEST_STATE 409 |
| TC-02-U05 | Invalid target: pending/cancelled/None/empty | ReviewError; no allowed transition |
| TC-02-U06 | Admin approves with empty notes | Valid |
| TC-02-U07 | Reject with empty/whitespace notes | REJECTION_REASON_REQUIRED |
| TC-02-U08 | Review notes at 3000 and 3001 characters | 3000 accepted; 3001 rejected |
| TC-02-U09 | Non-admin roles submit a decision | 403 |
| TC-02-U10 | Invalid decision format | 400 |
| TC-M-01 | Domain imports only allowed independent dependencies | No HTTP/ORM/repository/service imports |
| TC-M-02 | Service and route obey ARCH-SPEC-01 | No HTTP/SQL/database/hr_models import in service; no direct SQL model names in review route |

TC-REG-01 شامل 98 assertion رگرسیون حوزه‌های HR است؛ TC-PERF-01 آزمایش کوچک native است. این دو به معنی پذیرش همهٔ NFRها یا user acceptance نیستند.

پوشش code statement در package تصمیم 86 از 89 statement، معادل 96.6٪ است؛ سه statement پوشش‌نداده مربوط به فیلترهای scope در Repository و نوع درخواست ناسازگار در Service است. [گزارش دقیق](evidence/coverage-request-workflow.json) شامل خط‌هاست. branch coverage اندازه‌گیری نشده و coverage کل HRMS ادعا نمی‌شود.

شکاف‌های باقی: پذیرش انسانی، همهٔ مثبت/منفی/مرزهای FRهای Extended، ماتریس جامع امنیت، قفل‌های هم‌زمانی در تمام حوزه‌ها، بار/خرابی طولانی و سنجش usability. وجود test ID و link، کافی برای اثبات پوشش همهٔ رفتار نیست.
