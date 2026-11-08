# UC-02-models — مدل‌های قابل مشاهدهٔ HRMS

از رفتار فعلی بازسازی شده؛ تأیید انسانی ثبت نشده است. نسخهٔ editable و شناسه‌ها در [فهرست مدل‌ها](README.md).

## SEQ-02 — Request creation and decision sequence

```mermaid
%% SEQ-02 — Request creation and decision sequence
sequenceDiagram
    actor HR
    actor Admin
    participant Route as modules.py
    participant Service as RequestReviewService
    participant Domain
    participant Repo as RequestReviewRepository
    participant DB as PostgreSQL
    HR->>Route: POST /hr/leave/new + fields + CSRF
    Route->>Route: role/scope/fields/date validation
    Route->>DB: INSERT pending request + audit, COMMIT
    Route-->>HR: 303 detail
    Admin->>Route: POST /requests/id/review + CSRF
    Route->>Route: normalize form, validate active admin
    Route->>Service: review(id,decision,notes,Reviewer)
    Service->>Domain: validate_decision
    Service->>Repo: transaction()
    Repo->>DB: BEGIN
    Service->>Repo: locked_request then locked_employee(scope)
    Repo->>DB: SELECT FOR UPDATE request, employee
    alt رکورد ناموجود یا خارج از محدوده
      Repo->>DB: ROLLBACK
      Service-->>Route: ReviewError 404
    else رکورد معتبر
      Service->>Domain: decision_changes_state
      alt تصمیم نهایی مخالف / state نامعتبر
        Repo->>DB: ROLLBACK
        Service-->>Route: ReviewError 409
      else همان تصمیم نهایی
        Repo->>DB: COMMIT without write
        Service-->>Route: changed=false
      else pending
        Service->>Repo: has_approved_overlap for leave/travel
        Repo->>DB: inclusive overlap query
        alt هم‌پوشانی
          Repo->>DB: ROLLBACK
          Service-->>Route: ReviewError 400
        else قابل تصمیم
          Service->>Repo: save_decision + UTC clock
          Repo->>DB: UPDATE request + INSERT audit
          alt failure in persistence/audit
            Repo->>DB: ROLLBACK
            Service-->>Route: unhandled persistence exception
            Route-->>Admin: 500
          else commit
            Repo->>DB: COMMIT
            Service-->>Route: changed=true
          end
        end
      end
    end
    Note over Route,Admin: success and identical retry: 303 detail, ReviewError maps to 400/403/404/409
```

## ACT-02 — HR request activity

```mermaid
%% ACT-02 — HR request activity
flowchart TD
    Start(["شروع"]) --> Form["ثبت فرم توسط HR"]
    Form --> Date{"تاریخ و محدوده معتبر؟"}
    Date -->|"خیر"| CreationError["400/403/404؛ ثبت نشود"]
    Date -->|"بله"| Pending["ثبت pending و audit"]
    Pending --> Review["admin تصمیم می‌فرستد"]
    Review --> Input{"نقش، CSRF، تصمیم و notes معتبر؟"}
    Input -->|"خیر"| E400["400/403؛ بدون تغییر"]
    Input -->|"بله"| Lock["تراکنش؛ قفل request سپس employee"]
    Lock --> Found{"رکورد/نوع/محدوده معتبر؟"}
    Found -->|"خیر"| E404["404 یا 409"]
    Found -->|"بله"| Final{"وضعیت نهایی؟"}
    Final -->|"همان تصمیم"| Retry["303 بدون write/audit"]
    Final -->|"تصمیم مخالف یا state نامعتبر"| Conflict["409؛ تصمیم اولیه حفظ"]
    Final -->|"pending"| Overlap{"approval مرخصی/مأموریت هم‌پوشان؟"}
    Overlap -->|"بله"| EOverlap["400؛ rollback"]
    Overlap -->|"خیر"| Save["تصمیم، actor/time و audit"]
    Save --> Commit{"commit موفق؟"}
    Commit -->|"خیر"| Rollback["500؛ rollback همه"]
    Commit -->|"بله"| Done(["303؛ یک تصمیم نهایی"])
```

## ST-02 — Request decision lifecycle

```mermaid
%% ST-02 — Request decision lifecycle
stateDiagram-v2
    [*] --> Pending: valid creation + audit
    Pending --> Pending: valid edit
    Pending --> Approved: admin approval; no approved overlap; atomic audit
    Pending --> Rejected: admin rejection; nonblank reason; atomic audit
    Pending --> Pending: invalid input / overlap / audit failure
    Approved --> Approved: identical retry; no new write/audit
    Rejected --> Rejected: identical retry; no new write/audit
    note right of Approved
      Opposite final decision returns 409
      Editing finalized request is rejected
    end note
    note right of Rejected
      Opposite final decision returns 409
      No cancelled state is implemented
    end note
```
