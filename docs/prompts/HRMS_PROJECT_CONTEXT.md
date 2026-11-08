# HRMS project context for future coding chats

## Confirmed instructions from the student

- Project name: سامانه مدیریت منابع انسانی (Human Resource Management System).
- University course: Systems Analysis and Design.
- Build a complete working website through successive English prompts.
- The coding assistant will be Codex on Windows, or a GPT chat used on Windows.
- The user interface must be Persian, right-to-left, and visually simple.
- Each prompt must implement only one explicitly bounded stage.
- Stage 1 is environment/project setup and employee records, not all eight modules.
- The initial implementation should be understandable to a beginner and functional. Its architecture will evolve after actual experiments demonstrate limitations.
- Ask the student when an important requirement is unclear.
- The student wants the coding agent to handle project-related environment setup, dependency installation, database configuration, execution, and verification itself, using the tools and permissions actually available. Request specific permissions when required; preserve unrelated computer data. This autonomy does not expand the currently authorized stage to all future modules.
- Eventually produce a Persian Word report explaining actual problems, their causes, solutions, and before/after evidence.
- Do not invent measurements, screenshots, successful executions, or student modifications.

## Source inspection

The provided CamScanner PDF contains 14 actual PDF pages, although the student described it as 15 pages. All 14 pages were rendered and visually reviewed. They are screenshots of slides 2 through 15 from a larger presentation; the displayed presentation count is 31. Content beyond the supplied pages has not been reviewed.

The separate HR requirements image was also reviewed. The presentation's example domain is courses and enrollments. Adapt its architecture lessons to HR; do not build its example learning-management application.

Source locations:

- C:/Users/mahdy/Downloads/Telegram Desktop/CamScanner 10-26-26 13.15.pdf
- C:/Users/mahdy/Downloads/Telegram Desktop/photo_2026-11-08_08-42-40.jpg

## HR requirements from the image

Goal: manage the employee lifecycle across multiple organizational units, branches, and contract types.

Eight modules:

1. Employee records; organizational structure; positions and job descriptions.
2. Recruitment, hiring, interviews, and onboarding.
3. Attendance, shifts, overtime, and business travel.
4. Leave, administrative requests, and approval workflows.
5. Payroll calculations, benefits, deductions, and payslips.
6. Contracts, renewals, position changes, and termination of employment.
7. Performance evaluation, training, and career development.
8. HR reports, access control, and audit/change history.

Highlighted analysis/design challenges:

- Calculation rules that depend on contract type.
- Confidential information and appropriate access.
- History of organizational changes.
- Repeatable calculations.
- Separation of responsibilities.

No exact payroll formulas, legal rates, approval hierarchy, or detailed permission matrix were supplied. Clarify these before implementing the affected stages. Do not present simplified educational payroll rules as verified legal compliance.

## Notes from each supplied PDF page

1. Lab roadmap: environment setup; single server; Docker Compose separation and monitoring; Kubernetes deployment; service/load balancing; pod failure; database persistence; Redis cache; shared sessions/stateless web; RabbitMQ queue; failure engineering. Sharding, CDN, and multiple data centers are advanced topics.
2. Central idea: repeatedly redesign and deploy the same application. Observe a problem in the current architecture, implement a solution, measure before/after, and justify the next architectural decision. Example workload: 80% reads and 20% writes. Do not start with the final architecture.
3. Evolution diagram: single server -> separate web/database -> multiple web servers -> load balancer -> database replication -> Redis cache -> stateless web -> message queue -> monitoring -> sharding -> multi-DC/CDN. This diagram and the session roadmap organize monitoring differently; introduce monitoring early enough to obtain useful evidence.
4. Example application uses FastAPI and PostgreSQL. Example routes include courses, users, enrollment, progress, search, health, and instance identity. Transfer the health/instance ideas and architecture, while replacing the business domain with HR.
5. Technologies: Python/FastAPI, PostgreSQL, Redis for cache/shared sessions, RabbitMQ, Locust, Prometheus, Grafana, Docker, Docker Compose, Kubernetes, kind, and kubectl. FastAPI is selected to minimize framework learning overhead.
6. Learning cycle: architecture diagram -> AI-assisted implementation -> deployment -> load test -> metrics -> failure analysis -> next design. Load stages include 50, 100, 500, and 1000 users. Metrics include CPU, throughput, latency percentiles, and errors. Failure examples include pod loss, database slowdown, and queue growth.
7. AI assists design, implementation, experimentation, and analysis. Preserve the prompt, generated output, and actual student modifications for each stage. The student must run, debug, explain, and validate the work.
8. Golden rule: AI may generate implementation, but the student must explain and experimentally validate the architecture. Understand replicas, selectors, requests/limits, readiness versus liveness, Service addressing, and database StatefulSet versus Deployment.
9. Repository structure separates app code, tests, load tests, Docker, Compose, Kubernetes, and monitoring artifacts. Experiment documents contain Initial Architecture, Problem, Hypothesis, AI-assisted Implementation, Experiment and Metrics, Results and Analysis, Architectural Decision, and Next Evolution. A simple initial app is compatible with creating these documentation directories gradually.
10. Environment setup includes Docker, Compose, kubectl, kind, Git, Python, and Locust. A local laptop is sufficient; cloud deployment is not required. The presentation lists installation checks and creating a kind cluster. For our smaller stage 1, install/use only prerequisites actually needed; introduce the other tools at their relevant stages.
11. First deployment experiment deliberately puts FastAPI and PostgreSQL into one Docker container to observe resource contention. Preserve this as a later controlled educational baseline; do not silently replace it with a two-service Compose deployment before its experiment.
12. Resource-contention experiment uses CPU-intensive and database-intensive endpoints with Locust. Collect RPS, mean latency, P95/P99, error rate, CPU/memory, and database connections. Diagnose whether the web app, database, or another factor limits the system. Label synthetic diagnostic endpoints separately from normal HR behavior.
13. Compose separates web and PostgreSQL containers and adds Prometheus, Node Exporter, and Grafana, with an exporter for database metrics in the diagram. Compare web/database latency, CPU, and throughput against the single-container baseline. Little or no improvement is a valid finding. Container separation on one host does not by itself eliminate host resource competition.
14. Kubernetes deployment introduces desired state, Deployment, ReplicaSet, and reconciliation. The illustrated deployment has three web replicas. Service/load balancing and failure experiments follow in the roadmap. Supplied YAML is an illustration and requires operational configuration before use.

## Implementation decisions proposed for this project

These choices implement the student's requirements; they are not all specified in the PDF:

- Frontend: server-rendered Jinja2 templates with ordinary HTML, CSS, and minimal JavaScript.
- Backend: Python, FastAPI, Uvicorn.
- Database: PostgreSQL from the first working stage, with a small SQLAlchemy setup.
- Initial code: a small monolith with direct route/database logic and simple forms. No service/repository architecture or distributed components yet.
- Run one web process and one local PostgreSQL instance during functional construction. Later package both in the single-container experiment prescribed by the course.
- Stage 1 authentication: one seeded HR administrator, hashed password, a simple process-local session store, and normal form/session protections. Keep sensitive employee routes protected. Expand roles and branch/unit scope later.
- Start with current employee branch/unit/position fields. Properly retaining organizational history is a later design concern to analyze. Do not label this limitation as an experimentally observed failure before observing it.
- Use fictional data. Keep basic validation, uniqueness, foreign keys, and clear error messages even in a beginner implementation.
- Add /health and /instance for later experiments; expose only health status and instance identity.

## Planned sequence (each future prompt has one bounded outcome)

1. Setup and employee records, including simple organization reference data and an HR-admin login.
2. Recruitment, interviews, and onboarding.
3. Attendance, shifts, overtime, and business travel.
4. Leave and administrative requests with agreed approvals.
5. Payroll and payslips using explicitly agreed educational calculation rules.
6. Contract lifecycle and employment changes.
7. Performance, training, and career development.
8. Reporting, role/branch/unit permissions, and basic audit records.
9. Verify the integrated functional baseline and preserve a version snapshot.
10. Deploy that baseline with web and PostgreSQL inside one Docker container.
11. Measure its resource-contention behavior with Locust and record raw evidence.
12. Separate web/database with Docker Compose and add working monitoring.
13. Repeat the same workload and analyze the measured comparison.
14. Deploy the web app to Kubernetes using kind with a shared reachable database; explain desired state.
15. Add a Kubernetes Service and test traffic distribution across web replicas.
16. Perform a bounded pod-failure and recovery experiment.
17. Deploy PostgreSQL persistence in Kubernetes and verify data survival; distinguish persistence from high availability.
18. Add Redis caching for a justified HR read path; verify invalidation, access scoping, and correctness.
19. Move process-local sessions to Redis; verify sessions across replicas and restart behavior.
20. Queue a justified long-running HR operation with RabbitMQ; address retry behavior and duplicate delivery.
21. Run bounded failure experiments against the evolved architecture and document the findings.
22. Address measured HR design problems individually, such as organizational history, payroll reproducibility, or approval responsibility conflicts. Create separate prompts per actual problem.
23. Produce the final Persian Word report from accumulated evidence and student explanations.

Database read replication can receive its own stage if measurements justify it. Sharding, CDN, and multi-DC are advanced extensions; do not assume they have already been taught in detail or are necessary for this local HR system. Adjust the sequence to evidence and any further instructor requirements.

## Documentation carried between chats

Maintain docs/project-context.md with confirmed requirements, decisions, dependencies, and unresolved questions. Maintain docs/stage-status.md with completed stages, changed files, commands/checks and outcomes, known limitations, and the boundary of the next stage.

For real experiments, save version identifiers, architecture diagrams, configuration/resource limits, dataset size, workload/read-write ratio, user counts and ramp rate, duration, hardware, commands, raw CSV/logs, screenshots, failures, and analysis. Distinguish hypotheses from observations, and measurements from projections.

For the final report, each problem should connect its trigger and observed evidence to its cause, chosen solution, alternatives/tradeoffs, verification, and remaining limitations. Record actual student modifications only when the student supplies or performs them.

In a new chat, provide this file plus the current project files and the latest stage status. The English stage prompt is authoritative for the current coding scope. Future stages in this context are background, not permission to implement them now.
