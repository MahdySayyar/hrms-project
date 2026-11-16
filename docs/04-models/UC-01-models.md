# UC-01-models — مدل‌های قابل مشاهدهٔ HRMS

از رفتار فعلی بازسازی شده؛ تأیید انسانی ثبت نشده است. نسخهٔ editable و شناسه‌ها در [فهرست مدل‌ها](README.md).

## SEQ-01 — Authenticate and logout sequence

```mermaid
%% SEQ-01 — Authenticate and logout sequence
sequenceDiagram
    actor User as کاربر
    participant Browser
    participant Route as main.py
    participant Security as security.py
    participant DB as PostgreSQL
    User->>Browser: بازکردن login
    Browser->>Route: GET /login
    Route->>Security: anonymous session + CSRF
    Route-->>Browser: 200 HTML + HttpOnly cookie
    Browser->>Route: POST /login (username,password,csrf)
    Route->>Security: check_csrf
    alt CSRF نامعتبر
      Route-->>Browser: 403
    else فرم معتبر
      Route->>DB: read active account
      DB-->>Route: snapshot id/hash/active and close session
      Route->>Security: bounded private password queue
      Route->>Security: verify_password
      alt حساب یا رمز نامعتبر
        Route-->>Browser: 401 generic message
      else حساب فعال و رمز صحیح
        Route->>Security: recheck current CSRF session
        Route->>DB: recheck active account and same hash
        alt current account and CSRF still valid
        Route->>DB: INSERT login audit + COMMIT
        Route->>Security: discard old + new authenticated session
        Route-->>Browser: 303 / + rotated cookie
        Browser->>Route: GET /
        Route->>Security: require_login
        Security->>DB: verify account still active
        Route-->>Browser: 200 dashboard
        Browser->>Route: POST /logout + CSRF
        Route->>Security: validate session + CSRF
        Route->>DB: INSERT logout audit + COMMIT
        Route->>Security: discard_session
        Route-->>Browser: 303 /login + delete cookie
        else changed account or expired CSRF
          Route-->>Browser: 401 or 403 without a new session
        end
      end
    end
```

## ACT-01 — Authentication activity

```mermaid
%% ACT-01 — Authentication activity
flowchart TD
    Start(["شروع"]) --> Page["GET login و token نشست"]
    Page --> Submit["POST نام کاربری، رمز و CSRF"]
    Submit --> CSRF{"CSRF معتبر؟"}
    CSRF -->|"خیر"| E403["403؛ بدون ورود"]
    CSRF -->|"بله"| Snapshot["snapshot حساب / بستن اتصال DB"]
    Snapshot --> Queue{"ظرفیت خصوصی رمز آزاد؟"}
    Queue -->|"خیر"| Busy["503 / بدون ورود / تلاش مجدد"]
    Queue -->|"بله"| Hash["PBKDF2 در thread خصوصی"]
    Hash --> Valid{"حساب فعال و رمز صحیح؟"}
    Valid -->|"خیر"| E401["401؛ پیام عمومی"]
    Valid -->|"بله"| Recheck{"CSRF و active/hash هنوز معتبر؟"}
    Recheck -->|"بله"| Audit["ثبت audit و commit"]
    Recheck -->|"خیر"| Stale["401 یا 403 / بدون ورود"]
    Stale --> Page
    Audit --> Rotate["ابطال نشست قدیمی؛ نشست جدید"]
    Rotate --> Dashboard["303 سپس داشبورد"]
    Dashboard --> Logout["POST logout با CSRF"]
    Logout --> Remove["audit؛ ابطال نشست؛ حذف cookie"]
    Remove --> Finish(["بازگشت login"])
    E401 --> Page
    E403 --> Page
```

## ST-01 — Session lifecycle

```mermaid
%% ST-01 — Session lifecycle
stateDiagram-v2
    [*] --> Anonymous: GET login
    Anonymous --> Authenticated: valid active credentials + CSRF + audit
    Anonymous --> Anonymous: invalid credentials / 401
    Anonymous --> Anonymous: invalid CSRF / 403
    Anonymous --> Expired: anonymous lifetime ends
    Authenticated --> Invalidated: logout + CSRF + audit
    Authenticated --> Expired: configured lifetime ends
    Authenticated --> Invalidated: account inactive or missing
    Authenticated --> Lost: process restart
    Invalidated --> Anonymous: next login page
    Expired --> Anonymous: next login page
    Lost --> Anonymous: next login page
    note right of Authenticated
      New cookie after login
      Session is process-local
      Roles live in account data
    end note
```
