# UC-03-models — مدل‌های قابل مشاهدهٔ HRMS

از رفتار فعلی بازسازی شده؛ تأیید انسانی ثبت نشده است. نسخهٔ editable و شناسه‌ها در [فهرست مدل‌ها](README.md).

## SEQ-03 — Payroll calculation and saved retry

```mermaid
%% SEQ-03 — Payroll calculation and saved retry
sequenceDiagram
    actor Admin
    participant Route as calculate_payroll
    participant DB as PostgreSQL
    participant Detail as payslip_detail
    Admin->>Route: POST /payroll/calculate + employee/month/CSRF
    Route->>Route: active admin + CSRF + valid Gregorian month
    Route->>DB: SELECT employee FOR UPDATE
    Route->>DB: existing payslip(employee,period)?
    alt existing
      Route-->>Admin: 303 existing id
    else no existing
      Route->>DB: read current profile and current contract rule
      alt missing prerequisites or nonpositive hourly rate
        Route-->>Admin: 400, no payslip
      else valid inputs
        Route->>DB: monthly attendance
        Route->>Route: regular/overtime, HALF_UP rial, gross/net
        alt negative net
          Route-->>Admin: 400, no payslip
        else valid net
          Route->>DB: INSERT snapshots + amounts + audit, COMMIT
          Route-->>Admin: 303 saved id
        end
      end
    end
    Admin->>Detail: GET /payroll/id
    Detail->>DB: read saved record (admin/scope)
    Detail-->>Admin: 200 from snapshots
    Note over Route,DB: First historical calculation uses current profile/rule, no effective-date model
```

## ACT-03 — Payroll activity

```mermaid
%% ACT-03 — Payroll activity
flowchart TD
    Start(["شروع"]) --> Input["admin فرم employee/month + CSRF"]
    Input --> Valid{"نقش/CSRF/ورودی معتبر؟"}
    Valid -->|"خیر"| EInput["400/403 یا 303 login"]
    Valid -->|"بله"| Lock["قفل کارمند در scope"]
    Lock --> Existing{"فیش employee/month موجود؟"}
    Existing -->|"بله"| Saved["همان فیش snapshot"]
    Existing -->|"خیر"| Prereq{"profile و rule و نرخ معتبر؟"}
    Prereq -->|"خیر"| E400["400؛ بدون فیش"]
    Prereq -->|"بله"| Attendance["خواندن attendance ماه"]
    Attendance --> Calculate["regular و overtime؛ محاسبه HALF_UP"]
    Calculate --> Net{"net نامنفی؟"}
    Net -->|"خیر"| E400
    Net -->|"بله"| Persist["ذخیره input/rule snapshots و audit"]
    Persist --> Commit["commit؛ 303 فیش"]
    Commit --> Saved
    Saved --> End(["نمایش مبلغ تاریخی ذخیره‌شده"])
```

## ST-03 — Payslip persistence lifecycle

```mermaid
%% ST-03 — Payslip persistence lifecycle
stateDiagram-v2
    [*] --> NoPayslip
    NoPayslip --> NoPayslip: invalid input / missing profile or rule / negative net
    NoPayslip --> Saved: valid calculation; snapshots + audit commit
    Saved --> Saved: same employee/month retry
    Saved --> Saved: display from saved snapshots
    note right of Saved
      These are conceptual persistence states
      Payslip has no status column
      No update/recalculate route exists
      Direct SQL UPDATE is not prevented
    end note
```
