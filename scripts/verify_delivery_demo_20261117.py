"""Exercise the delivery demo using an explicitly disposable Docker install."""
import argparse
import json
import os
import re
import secrets
import subprocess
from contextlib import ExitStack
from pathlib import Path

import httpx


def verify_demo(port, admin_secret):
    checks = {}

    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise RuntimeError(f"Demo check failed: {name}")

    def post(client, form_path, path, **fields):
        page = client.get(form_path)
        match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        if page.status_code != 200 or not match:
            raise RuntimeError("Demo form or CSRF token unavailable")
        return client.post(path, data={**fields, "csrf_token": match[1]})

    with ExitStack() as stack:
        admin, applicant = [stack.enter_context(httpx.Client(base_url=f"http://127.0.0.1:{port}",
            follow_redirects=False, trust_env=False, timeout=10)) for _ in range(2)]
        check("login_links_to_registration", 'href="/register"' in applicant.get("/login").text)
        username = "demo-" + secrets.token_hex(8)
        password = secrets.token_urlsafe(24)
        name = "کاربر ساختگی دمو"
        registered = post(applicant, "/register", "/register", display_name=name, username=username,
            password=password, password_confirmation=password)
        check("registration_creates_pending_account", registered.status_code == 303 and registered.headers.get("location") == "/login?registered=1")
        check("pending_account_cannot_login", post(applicant, "/login", "/login", username=username, password=password).status_code == 401)
        check("seeded_admin_can_login", post(admin, "/login", "/login", username="hradmin", password=admin_secret.read_text().strip()).status_code == 303)
        listing = admin.get("/hr/users")
        displayed_username = username.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        row = next((row for row in re.findall(r"<tr\b.*?</tr>", listing.text, re.S) if displayed_username in row), "")
        account = re.search(r'href="/hr/users/(\d+)(?:/edit)?"', row)
        check("admin_can_find_pending_account", listing.status_code == 200 and account is not None)
        edit = f"/hr/users/{account[1]}/edit"
        check("admin_activates_as_hr", post(admin, edit, edit, username=username, display_name=name, role="hr", is_active="true").status_code == 303)
        check("activated_account_can_login", post(applicant, "/login", "/login", username=username, password=password).status_code == 303)
        new_leave = "/hr/leave/new"
        form = applicant.get(new_leave)
        employees = re.search(r'<select[^>]*name="employee_id"[^>]*>(.*?)</select>', form.text, re.S)
        employee = re.search(r'<option[^>]*value="([0-9]+)"', employees[1]) if employees else None
        check("synthetic_employee_available", form.status_code == 200 and employee is not None)
        created = post(applicant, new_leave, new_leave, employee_id=employee[1], start_date="2035-04-10",
            end_date="2035-04-11", leave_type="annual", description="مرخصی آزمایشی دمو")
        detail = re.fullmatch(r"(/hr/leave/(\d+))(?:\?saved=1)?", created.headers.get("location", ""))
        check("hr_creates_leave", created.status_code == 303 and detail is not None)
        review = f"/requests/{detail[2]}/review"
        check("admin_approves_leave", post(admin, detail[1], review, decision="approved", review_notes="تأیید آزمایشی").status_code == 303)
        check("hr_sees_approved_leave", "تأییدشده" in applicant.get(detail[1]).text)
        report = applicant.get("/reports?period=2035-04")
        check("report_contains_one_approved_leave", report.status_code == 200 and re.search(
            r"<td>مرخصی</td>\s*<td>تأییدشده</td>\s*<td>۱</td>", report.text) is not None)
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = os.getenv("COMPOSE_PROJECT_NAME", "")
    compose_file = os.getenv("HRMS_CI_COMPOSE", "")
    if os.getenv("GITHUB_ACTIONS") != "true" or not re.fullmatch(r"hrms-demo-ci-\d+-\d+", project) \
            or compose_file not in {"compose.capacity.yaml", "compose.shared.yaml"}:
        parser.error("The CLI is restricted to a fresh GitHub Actions demo project.")
    binding = subprocess.check_output(["docker", "compose", "-f", f"deployments/{compose_file}",
        "port", "proxy", "8000"], text=True).strip()
    address = re.fullmatch(r"127\.0\.0\.1:(\d+)", binding)
    if not address:
        parser.error("The disposable proxy must be bound to loopback.")
    checks = verify_demo(address[1], Path(".runtime/docker-hrms-secrets/admin_password"))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump({"all_passed": True, "checks": checks, "synthetic_only": True, "human_gate": "pending"}, stream, indent=2)
    print(f"{len(checks)} delivery demo checks passed.")
