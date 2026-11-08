# analysis-models — مدل‌های قابل مشاهدهٔ HRMS

از رفتار فعلی بازسازی شده؛ تأیید انسانی ثبت نشده است. نسخهٔ editable و شناسه‌ها در [فهرست مدل‌ها](README.md).

## CTX-01 — HRMS context

```mermaid
%% CTX-01 — HRMS context
flowchart LR
    Admin["مدیر HR / admin"] -->|"حساب، تصمیم، حقوق، ممیزی"| HRMS["سامانه HRMS"]
    HR["کارشناس HR / hr"] -->|"عملیات پرونده در scope"| HRMS
    Viewer["مشاهده‌گر / viewer"] -->|"گزارش کلی در scope"| HRMS
    HRMS -->|"صفحه فارسی / نتیجه / CSV"| Admin
    HRMS -->|"صفحه فارسی / نتیجه / CSV"| HR
    HRMS -->|"گزارش کلی"| Viewer
    Employee["کارکنان؛ صاحبان داده، بدون ورود فعلی"] -.->|"پرونده و درخواست از طریق HR"| HR
    Operator["مسئول اجرا"] -->|"راه‌اندازی و backup"| HRMS
```

## UCM-01 — Use-case model

```mermaid
%% UCM-01 — Use-case model
flowchart LR
    Admin["admin"]
    HR["hr"]
    Viewer["viewer"]
    subgraph System["مرز HRMS"]
      U1(["UC-01 ورود و خروج"])
      U2(["UC-02 ثبت و تصمیم درخواست"])
      U3(["UC-03 فیش آموزشی"])
      U4(["UC-04 پرونده و جست‌وجو"])
      U5(["UC-05 سازمان"])
      U6(["UC-06 استخدام و پذیرش"])
      U7(["UC-07 تردد"])
      U8(["UC-08 قرارداد"])
      U9(["UC-09 ارزیابی و آموزش"])
      U10(["UC-10 تاریخچه"])
      U11(["UC-11 گزارش و CSV"])
      U12(["UC-12 حساب و ممیزی"])
    end
    Admin --> U1 & U2 & U3 & U4 & U5 & U6 & U7 & U8 & U9 & U10 & U11 & U12
    HR --> U1 & U2 & U4 & U5 & U6 & U7 & U8 & U9 & U10 & U11
    Viewer --> U1 & U11
    U2 -.->|"تصمیم فقط admin"| Admin
    U11 -.->|"CSV فقط admin و hr"| HR
```

## DM-01 — Conceptual domain

```mermaid
%% DM-01 — Conceptual domain
classDiagram
    class UserAccount {
      username
      role
      organizationalScope
    }
    class Branch {
      name
    }
    class Unit {
      name
    }
    class Position {
      title
      jobDescription
    }
    class Employee {
      employeeCode
      name
      currentContractType
      active
    }
    class Candidate {
      name
      applicationDate
      status
    }
    class Interview {
      scheduledAt
      result
    }
    class OnboardingTask {
      title
      completed
    }
    class Shift {
      startTime
      endTime
      breakMinutes
    }
    class Attendance {
      workDate
      workedMinutes
      overtimeMinutes
    }
    class HrRequest {
      kind
      dateRange
      status
      reviewNotes
    }
    class PayrollRule {
      mode
      percentages
      overtimeFactor
    }
    class PayrollProfile {
      baseSalary
      hourlyRate
      benefits
      deductions
    }
    class Payslip {
      period
      amounts
      inputSnapshot
      ruleSnapshot
    }
    class EmploymentContract {
      dateRange
      status
      renewedFrom
    }
    class Evaluation {
      date
      score
      feedback
      goals
    }
    class Training {
      date
      capacity
    }
    class TrainingEnrollment {
      status
    }
    class CareerPlan {
      targetDate
      progress
      actions
    }
    class AssignmentHistory {
      dateRange
      organizationNameSnapshots
    }
    class AuditLog {
      actor
      action
      entityReference
      timestamp
    }
    Branch "1" --> "*" Unit : contains
    Employee "*" --> "1" Branch : assigned
    Employee "*" --> "1" Unit : assigned
    Employee "*" --> "1" Position : holds
    UserAccount "*" --> "0..1" Branch : optionalScope
    UserAccount "*" --> "0..1" Unit : optionalScope
    Candidate "*" --> "1" Branch : applies
    Candidate "*" --> "1" Unit : applies
    Candidate "*" --> "1" Position : applies
    Candidate "1" --> "*" Interview : interviews
    Candidate "1" --> "*" OnboardingTask : onboarding
    Candidate "0..1" --> "0..1" Employee : hiredAs
    Employee "1" --> "*" Attendance : attendance
    Shift "1" --> "*" Attendance : schedule
    Employee "1" --> "*" HrRequest : requests
    UserAccount "0..1" --> "*" HrRequest : reviews
    Employee "1" --> "0..1" PayrollProfile : paymentInputs
    PayrollRule ..> Payslip : ruleSnapshot
    Employee "1" --> "*" Payslip : monthlySnapshots
    UserAccount "1" --> "*" Payslip : creates
    Employee "1" --> "*" EmploymentContract : contracts
    EmploymentContract "0..1" --> "*" EmploymentContract : renewedFrom
    Employee "1" --> "*" Evaluation : reviews
    Training "1" --> "*" TrainingEnrollment : enrollments
    Employee "1" --> "*" TrainingEnrollment : attends
    Employee "1" --> "*" CareerPlan : career
    Position "1" --> "*" CareerPlan : target
    Employee "1" --> "*" AssignmentHistory : assignmentHistory
    Branch "1" --> "*" AssignmentHistory : branch
    Unit "1" --> "*" AssignmentHistory : unit
    Position "1" --> "*" AssignmentHistory : position
    UserAccount "0..1" --> "*" AuditLog : performs
    AuditLog ..> Employee : logicalEntityReference
```
