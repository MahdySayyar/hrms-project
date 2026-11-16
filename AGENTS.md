# HRMS project working instructions

The user wants a beginner's functional baseline, observed problems, progressive architecture fixes and an independent evidence report for each fix. Honor directly authorized user scope; do not introduce every distributed technology at once.

For changes to behavior, update the relevant FR/BR, structured UC, model/design and impact/ADR first, then implement and run meaningful positive/negative/boundary checks. Document whether artifacts were reconstructed after existing implementation; never invent a pre-code analysis or human acceptance.

Keep the current deployment a single process until the corresponding experiment demonstrates and documents the next architectural change. Only the request-decision workflow currently has a Domain/Service/Repository boundary. Do not call the whole application a modular monolith or stateless.

Never export .env, runtime credentials or real HR rows. Use disposable PostgreSQL schemas and synthetic records for new automated workflows/load. Preserve unrelated data and existing snapshots/evidence. Snapshot and test-run scripts require a unique new name.

Main verification: core unittest suite on PostgreSQL; coverage for app/request_workflow; scripts/check_engineering.py; Mermaid syntax parser when diagrams change; pip check. Do not run the legacy browser_check.cjs UI automation with browser tooling other than CUA. Historical browser evidence is not a fresh visual test.

Human review, instructor Gate acceptance, interviews, contributions and learning must remain explicitly pending unless actual evidence is provided. Keep source prompts and bounded AI outputs truthful. Local commits made by the agent must use an agent author, not an invented student.

User-facing communication is Persian. Keep the UI simple, Persian and RTL. Dates are currently Gregorian and payroll rates educational; do not assume legal rules.

The user authorized public GitHub publication and ongoing synchronization on 2026-11-17. After completing each authorized change, run applicable checks, commit the finalized project changes with an agent author, and push to the configured origin. Preserve user work; never publish .env, runtime secrets, real HR data or raw artifacts. If GitHub authentication or network access prevents pushing, report that honestly. Do not install a watcher that automatically publishes unfinished edits.
