"""Native HRMS baseline: 80% read / 20% write tasks, only against an isolated local lab."""
import json
import math
import os
import random
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from locust import HttpUser, between, events, task
from locust.exception import StopUser

authenticated_active = 0
authenticated_peak = 0
spawning_completed = None


@events.spawning_complete.add_listener
def record_spawn_completion(user_count, **_):
    global spawning_completed
    spawning_completed = {"user_count": user_count, "timestamp": time.time()}


class HrmsUser(HttpUser):
    wait_time = between(0.02, 0.08)

    def on_start(self):
        global authenticated_active, authenticated_peak
        self.authenticated_in_lab = False
        self.client.trust_env = False
        marker = os.environ.get("HRMS_LAB_INSTANCE")
        if not marker or urlsplit(self.host).hostname not in ("localhost", "127.0.0.1"):
            raise StopUser("Use run_load_lab.py; write tasks require a verified, isolated localhost lab.")
        with self.client.get("/instance", name="setup.instance", catch_response=True) as response:
            if response.status_code != 200 or response.json().get("instance") != marker:
                response.failure("The target is not the isolated lab instance")
                raise StopUser()
        page = self.client.get("/login", name="setup.login_form")
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        if not token:
            raise StopUser("Login form has no CSRF token")
        with self.client.post("/login", name="setup.login", data={"username": os.environ["HRMS_LAB_USERNAME"],
            "password": os.environ["HRMS_LAB_PASSWORD"], "csrf_token": token.group(1)}, allow_redirects=False, catch_response=True) as response:
            if response.status_code != 303:
                response.failure("Synthetic lab login failed")
                raise StopUser()
        page = self.client.get("/", name="setup.session")
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        if not token:
            raise StopUser("Authenticated page has no CSRF token")
        self.csrf_token = token.group(1)
        self.employee_ids = json.loads(os.environ["HRMS_LAB_EMPLOYEE_IDS"])
        self.authenticated_in_lab = True
        authenticated_active += 1
        authenticated_peak = max(authenticated_peak, authenticated_active)

    def on_stop(self):
        global authenticated_active
        if self.authenticated_in_lab:
            authenticated_active -= 1

    @task(4)
    def read_records(self):
        name, path = random.choice((("employees", "/employees"), ("dashboard", "/"),
                                   ("reports", "/reports"), ("requests", "/hr/leave")))
        with self.client.get(path, name="read." + name, catch_response=True) as response:
            if response.status_code != 200 or "id=\"username\"" in response.text:
                response.failure("The protected read did not return the expected page")

    @task(1)
    def update_synthetic_employee(self):
        employee_id = random.choice(self.employee_ids)
        with self.client.post(f"/employees/{employee_id}/status", name="write.employee_status",
            data={"active": random.choice(("true", "false")), "csrf_token": self.csrf_token},
            allow_redirects=False, catch_response=True) as response:
            if response.status_code != 303:
                response.failure("Synthetic status write was not accepted")


@events.quitting.add_listener
def save_workload_metrics(environment, **_):
    output = os.environ.get("HRMS_LAB_METRICS_PATH")
    if not output:
        return
    entries = [entry for entry in environment.stats.entries.values() if entry.name.startswith(("read.", "write."))]
    histogram = Counter()
    for entry in entries:
        histogram.update(entry.response_times)
    requests = sum(entry.num_requests for entry in entries)
    failures = sum(entry.num_failures for entry in entries)
    samples = sum(histogram.values())
    def percentile(fraction):
        threshold = math.ceil(samples * fraction)
        count = 0
        for duration, quantity in sorted(histogram.items()):
            count += quantity
            if count >= threshold:
                return duration
        return None
    duration = max(0.001, (environment.stats.total.last_request_timestamp or time.time()) - environment.stats.total.start_time)
    reads = sum(entry.num_requests for entry in entries if entry.name.startswith("read."))
    payload = {"task_weights": {"read": 4, "write": 1}, "requests": requests, "failures": failures,
        "peak_authenticated_users": authenticated_peak, "spawning_completed": spawning_completed,
        "read_requests": reads, "write_requests": requests - reads, "observed_read_fraction": reads / requests if requests else None,
        "wall_window_seconds_including_login": duration, "rps_over_wall_window": requests / duration,
        "p50_ms": percentile(0.50), "p95_ms": percentile(0.95), "p99_ms": percentile(0.99),
        "percentile_method": "Merged Locust response-time buckets; setup requests excluded",
        "endpoints": [{"name": e.name, "method": e.method, "requests": e.num_requests, "failures": e.num_failures} for e in entries]}
    Path(output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
