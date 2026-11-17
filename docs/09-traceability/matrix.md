# TR-CAT-01 — ماتریس نیازمندی تا آزمون

از specificationهای جاری ساخته شده؛ review انسانی باز است. [دادهٔ ماشین‌خوان](../../specs/traceability.yaml) و [شناسه‌ها](../../specs/artifact-registry.yaml).

هر ردیف منبع، FR/BR، specification، UC، مدل، طرح، API، code symbol و evidence را وصل می‌کند. لینک به suite عمومی یا سابقهٔ تاریخی، پوشش کامل acceptance همان FR را اثبات نمی‌کند.

| TR / FR | Spec / UC | Model / Design | API / Code | Test |
|---|---|---|---|---|
| TR-01 / FR-01 | FS-01 / UC-01 | ACT-01, DM-01, SEQ-01, ST-01, UCM-01 / D-01 | API-01<br>[login](../../app/main.py#login) | TC-01-01, TC-01-03, TC-01-07, TC-01-10, TC-01-11, TC-01-12, TC-01-13, TC-01-14, TC-01-15, TC-01-16, TC-REG-01 |
| TR-02 / FR-02 | FS-02 / UC-01 | ACT-01, DM-01, SEQ-01, ST-01, UCM-01 / D-01 | API-01<br>[logout](../../app/main.py#logout) | TC-01-01 |
| TR-03 / FR-03 | FS-03 / UC-01, UC-02, UC-03 | ACT-01, ACT-02, ACT-03, DM-01, SEQ-01, SEQ-02, SEQ-03, ST-01, ST-02, ST-03, UCM-01 / D-01, D-02, D-03 | API-01, API-02, API-03<br>[require_hr](../../app/access.py#require_hr)<br>[require_admin](../../app/access.py#require_admin)<br>[scoped_employee](../../app/access.py#scoped_employee) | TC-01-02, TC-REG-01 |
| TR-04 / FR-04 | FS-04 / UC-04 | DM-01, UCM-01 / D-04 | API-04<br>[employee_create](../../app/main.py#employee_create)<br>[employee_edit](../../app/main.py#employee_edit) | TC-HIST-01, TC-REG-01 |
| TR-05 / FR-05 | FS-05 / UC-04 | DM-01, UCM-01 / D-04 | API-04<br>[employee_status](../../app/main.py#employee_status) | TC-HIST-01, TC-REG-01 |
| TR-06 / FR-06 | FS-06 / UC-04 | DM-01, UCM-01 / D-04 | API-04<br>[employee_list](../../app/main.py#employee_list) | TC-04-01, TC-04-02, TC-04-03, TC-04-04, TC-HIST-01 |
| TR-07 / FR-07 | FS-07 / UC-05 | DM-01, UCM-01 / D-04 | API-05<br>[save_organization](../../app/main.py#save_organization) | TC-HIST-01, TC-REG-01 |
| TR-08 / FR-08 | FS-08 / UC-04, UC-06 | DM-01, UCM-01 / D-04 | API-04, API-06<br>[validate_record](../../app/modules.py#validate_record) | TC-REG-01 |
| TR-09 / FR-09 | FS-09 / UC-04, UC-06 | DM-01, UCM-01 / D-04 | API-04, API-06<br>[save_record](../../app/modules.py#save_record)<br>[validate_record](../../app/modules.py#validate_record) | TC-REG-01 |
| TR-10 / FR-10 | FS-10 / UC-06 | DM-01, UCM-01 / D-04 | API-06<br>[hire_candidate](../../app/modules.py#hire_candidate)<br>[complete_onboarding](../../app/modules.py#complete_onboarding) | TC-REG-01 |
| TR-11 / FR-11 | FS-11 / UC-04, UC-07 | DM-01, UCM-01 / D-04 | API-04, API-07<br>[validate_record](../../app/modules.py#validate_record)<br>[minutes_between](../../app/modules.py#minutes_between) | TC-04-05, TC-REG-01 |
| TR-12 / FR-12 | FS-12 / UC-02, UC-04 | ACT-02, DM-01, SEQ-02, ST-02, UCM-01 / D-02, D-04 | API-02, API-04<br>[save_record](../../app/modules.py#save_record) | TC-02-01, TC-REG-01 |
| TR-13 / FR-13 | FS-13 / UC-02 | ACT-02, DM-01, SEQ-02, ST-02, UCM-01 / D-02 | API-02<br>[review_request](../../app/modules.py#review_request)<br>[RequestReviewService.review](../../app/request_workflow/service.py#RequestReviewService.review) | TC-02-02, TC-02-03, TC-02-04, TC-02-05, TC-02-06, TC-02-07, TC-02-08, TC-02-09, TC-REG-01 |
| TR-14 / FR-14 | FS-14 / UC-03 | ACT-03, DM-01, SEQ-03, ST-03, UCM-01 / D-03 | API-03<br>[app/module_forms.py](../../app/module_forms.py)<br>[validate_record](../../app/modules.py#validate_record)<br>[PayrollRule](../../app/hr_models.py#PayrollRule) | TC-03-01, TC-03-02, TC-REG-01 |
| TR-15 / FR-15 | FS-15 / UC-03, UC-04 | ACT-03, DM-01, SEQ-03, ST-03, UCM-01 / D-03, D-04 | API-03, API-04<br>[app/module_forms.py](../../app/module_forms.py)<br>[PayrollProfile](../../app/hr_models.py#PayrollProfile) | TC-03-04, TC-REG-01 |
| TR-16 / FR-16 | FS-16 / UC-03 | ACT-03, DM-01, SEQ-03, ST-03, UCM-01 / D-03 | API-03<br>[calculate_payroll](../../app/modules.py#calculate_payroll)<br>[payslip_detail](../../app/modules.py#payslip_detail) | TC-03-01, TC-03-02, TC-03-03, TC-03-04, TC-03-05, TC-REG-01 |
| TR-17 / FR-17 | FS-17 / UC-04, UC-08 | DM-01, UCM-01 / D-04 | API-04, API-08<br>[activate_contract](../../app/modules.py#activate_contract)<br>[renew_contract](../../app/modules.py#renew_contract)<br>[terminate_contract](../../app/modules.py#terminate_contract) | TC-REG-01 |
| TR-18 / FR-18 | FS-18 / UC-04, UC-09 | DM-01, UCM-01 / D-04 | API-04, API-09<br>[app/module_forms.py](../../app/module_forms.py)<br>[Evaluation](../../app/hr_models.py#Evaluation) | TC-REG-01 |
| TR-19 / FR-19 | FS-19 / UC-04, UC-09 | DM-01, UCM-01 / D-04 | API-04, API-09<br>[validate_record](../../app/modules.py#validate_record)<br>[TrainingEnrollment](../../app/hr_models.py#TrainingEnrollment) | TC-REG-01 |
| TR-20 / FR-20 | FS-20 / UC-04, UC-09 | DM-01, UCM-01 / D-04 | API-04, API-09<br>[app/module_forms.py](../../app/module_forms.py)<br>[CareerPlan](../../app/hr_models.py#CareerPlan) | TC-REG-01 |
| TR-21 / FR-21 | FS-21 / UC-10 | DM-01, UCM-01 / D-04 | API-10<br>[sync_assignment](../../app/access.py#sync_assignment)<br>[employee_history](../../app/modules.py#employee_history) | TC-REG-01 |
| TR-22 / FR-22 | FS-22 / UC-11 | DM-01, UCM-01 / D-04 | API-11<br>[reports](../../app/modules.py#reports) | TC-01-02, TC-11-04, TC-11-05, TC-REG-01 |
| TR-23 / FR-23 | FS-23 / UC-11 | DM-01, UCM-01 / D-04 | API-11<br>[export_employees](../../app/modules.py#export_employees)<br>[safe_csv](../../app/modules.py#safe_csv) | TC-01-02, TC-11-01, TC-11-02, TC-11-03, TC-REG-01 |
| TR-24 / FR-24 | FS-24 / UC-02, UC-03, UC-12 | ACT-02, ACT-03, DM-01, SEQ-02, SEQ-03, ST-02, ST-03, UCM-01 / D-02, D-03, D-04 | API-02, API-03, API-12<br>[audit](../../app/access.py#audit)<br>[audit_page](../../app/modules.py#audit_page)<br>[RequestReviewRepository.save_decision](../../app/request_workflow/repository.py#RequestReviewRepository.save_decision) | TC-02-02, TC-02-08, TC-REG-01 |
| TR-25 / FR-25 | FS-25 / UC-01, UC-04, UC-12 | ACT-01, DM-01, SEQ-01, ST-01, UCM-01 / D-01, D-04 | API-01, API-04, API-12<br>[register](../../app/main.py#register)<br>[validate_record](../../app/modules.py#validate_record)<br>[Admin](../../app/database.py#Admin) | TC-01-24, TC-REG-01 |

TC-REG-01 = 98 assertion رگرسیون فعلی؛ index دقیق مرتبط در YAML. TC-HIST-01 = 45 بررسی قدیمی Stage 1؛ اجرای تازه نیست. TC-PERF-01 = بار native سبک. TC-01..03 = آزمون‌های Core با نتیجهٔ نهایی؛ TC-02-U و TC-M قواعد و مرز معماری.

## نیازمندی غیرعملکردی

| NFR | وضعیت واقعی | تست / شاهد |
|---|---|---|
| NFR-01 | proposed_not_verified | <br>[native-load.json](../../docs/08-testing/evidence/native-load.json), [capacity-native4-500-before-20261115-a.json](../../docs/08-testing/evidence/capacity-native4-500-before-20261115-a.json) |
| NFR-P-02 | proposed_not_verified | <br>شاهد پذیرش موجود نیست |
| NFR-S-01 | partially_verified | TC-01-02<br>شاهد پذیرش موجود نیست |
| NFR-S-02 | partially_verified | TC-01-01<br>شاهد پذیرش موجود نیست |
| NFR-AU-01 | verified_for_request_decisions | TC-02-02, TC-02-04, TC-02-08<br>شاهد پذیرش موجود نیست |
| NFR-A-01 | proposed_not_verified | <br>شاهد پذیرش موجود نیست |
| NFR-M-01 | verified_for_request_module_pending_human_review | TC-M-01, TC-M-02<br>[all-tests-final.json](../../docs/08-testing/evidence/all-tests-final.json) |
| NFR-T-01 | measured_request_package_threshold_passed | <br>[coverage-request-workflow.json](../../docs/08-testing/evidence/coverage-request-workflow.json) |
| NFR-U-01 | proposed_not_verified | <br>شاهد پذیرش موجود نیست |
| NFR-L-01 | implemented_historical_browser_evidence | <br>شاهد پذیرش موجود نیست |
| NFR-R-01 | proposed_not_verified | <br>شاهد پذیرش موجود نیست |

سازگاری semantic و کامل بودن قراردادها نیازمند review انسانی است. بررسی خودکار تنها وجود/شناسه/پیوند/symbol و دادهٔ schema را کنترل می‌کند؛ نمرهٔ Consistency از تعداد linkها تولید نمی‌شود.
