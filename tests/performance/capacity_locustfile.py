"""Steady-window capacity and login-pressure measurements against a verified isolated lab."""
import json
import math
import os
import random
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import gevent
from locust import HttpUser, between, events, task
from locust.exception import StopUser

ready = authenticated = ready_peak = authenticated_peak = 0
window_start = window_end = None
setup_finished = None
finish_reason = "not_started"
histogram = Counter()
endpoint_metrics = {}
all_outcomes = Counter()
setup_failures = Counter()
spawn_completion = None
burst_arrived = burst_completed = 0
burst_start = None
burst_results = []
user_ordinal = 0
workers_observed = Counter()


def percentile(values, fraction):
    samples = sum(values.values())
    threshold = math.ceil(samples * fraction)
    cumulative = 0
    for duration, count in sorted(values.items()):
        cumulative += count
        if cumulative >= threshold:
            return duration
    return None


@events.spawning_complete.add_listener
def spawned(user_count, **_):
    global spawn_completion
    spawn_completion = {"users": user_count, "time": time.time()}


@events.request.add_listener
def record_request(name, response_time, response_length, exception, response=None, start_time=None, **_):
    global histogram
    code = getattr(response, "status_code", None)
    all_outcomes[(name, code, bool(exception))] += 1
    if window_start is None or not name.startswith(("read.", "write.", "login.")):
        return
    completed = time.time()
    if (start_time is not None and start_time < window_start) or (window_end is not None and completed > window_end):
        return
    bucket = max(0, int(round(response_time)))
    if response is not None and response.headers.get("X-HRMS-Worker") is not None:
        workers_observed[response.headers["X-HRMS-Worker"]] += 1
    histogram[bucket] += 1
    entry = endpoint_metrics.setdefault(name, {"requests": 0, "failures": 0, "response_bytes": 0,
        "max_response_bytes": 0, "latency_histogram_ms": Counter(), "statuses": Counter()})
    entry["requests"] += 1
    entry["failures"] += int(bool(exception))
    entry["response_bytes"] += response_length or 0
    entry["max_response_bytes"] = max(entry["max_response_bytes"], response_length or 0)
    entry["latency_histogram_ms"][bucket] += 1
    entry["statuses"][str(code)] += 1


def control_window(environment):
    global window_start, window_end, setup_finished, finish_reason, burst_start
    deadline = time.monotonic() + float(os.environ["HRMS_LAB_WARMUP_TIMEOUT"])
    expected = int(os.environ["HRMS_LAB_EXPECTED_USERS"])
    abort_path = Path(os.environ["HRMS_LAB_ABORT_PATH"])
    while ready < expected and time.monotonic() < deadline and not abort_path.exists():
        gevent.sleep(0.1)
    if abort_path.exists():
        finish_reason = "resource_abort"
    elif ready < expected:
        finish_reason = "setup_timeout"
    else:
        setup_finished = time.time()
        window_start = setup_finished
        finish_reason = "steady_running"
        marker = Path(os.environ["HRMS_LAB_WINDOW_MARKER"])
        marker.write_text(json.dumps({"started_at": window_start, "ready_users": ready,
            "authenticated_users": authenticated}) + "\n", encoding="utf-8")
        steady_deadline = time.monotonic() + float(os.environ["HRMS_LAB_STEADY_SECONDS"])
        while time.monotonic() < steady_deadline and not abort_path.exists():
            gevent.sleep(.2)
        window_end = time.time()
        finish_reason = "resource_abort" if abort_path.exists() else "steady_completed"
        if finish_reason == "steady_completed" and os.environ.get("HRMS_LAB_BURST", "none") != "none":
            deadline = time.monotonic() + 30
            while burst_arrived < expected and time.monotonic() < deadline:
                gevent.sleep(.05)
            if burst_arrived == expected:
                burst_start = time.time()
                deadline = time.monotonic() + 45
                while burst_completed < expected and time.monotonic() < deadline:
                    gevent.sleep(.05)
    environment.runner.quit()


@events.init.add_listener
def initialize(environment, **_):
    random.seed(int(os.environ.get("HRMS_LAB_SEED", "20261108")))
    gevent.spawn(control_window, environment)


class LabUser(HttpUser):
    abstract = True
    wait_time = between(0.02, 0.08)

    def verify_target(self):
        self.registered = self.is_authenticated = False
        self.client.trust_env = False
        marker = os.environ.get("HRMS_LAB_INSTANCE")
        if not marker or urlsplit(self.host).hostname not in ("localhost", "127.0.0.1"):
            raise StopUser("Capacity tests require a verified isolated localhost target.")
        with self.client.get("/instance", name="setup.instance", timeout=15, catch_response=True) as response:
            try:
                valid = response.status_code == 200 and response.json().get("instance") == marker
            except ValueError:
                valid = False
            if not valid:
                response.failure("Isolated instance marker mismatch")
                setup_failures["target"] += 1
                raise StopUser()

    def login_form(self):
        with self.client.get("/login", name="setup.login_form", timeout=30, catch_response=True) as response:
            token = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
            if response.status_code != 200 or not token:
                response.failure("The synthetic login form was unavailable")
                setup_failures["login_form"] += 1
                raise StopUser()
            return token.group(1)

    def register_ready(self, logged_in):
        global ready, authenticated, ready_peak, authenticated_peak
        self.registered, self.is_authenticated = True, logged_in
        ready += 1
        authenticated += int(logged_in)
        ready_peak = max(ready_peak, ready)
        authenticated_peak = max(authenticated_peak, authenticated)
        # Establish the requested authenticated population before starting work.
        # This keeps expensive list requests during ramp out of the steady baseline.
        while window_start is None and finish_reason not in ("setup_timeout", "resource_abort"):
            gevent.sleep(.1)
        if window_start is None:
            raise StopUser("The full requested population did not finish setup.")

    def on_stop(self):
        global ready, authenticated
        if self.registered:
            ready -= 1
            authenticated -= int(self.is_authenticated)


class HrmsCapacityUser(LabUser):
    def on_start(self):
        global user_ordinal
        self.verify_target()
        token = self.login_form()
        with self.client.post("/login", name="setup.login", timeout=45, allow_redirects=False,
            data={"username": os.environ["HRMS_LAB_USERNAME"], "password": os.environ["HRMS_LAB_PASSWORD"],
                  "csrf_token": token}, catch_response=True) as response:
            if response.status_code != 303:
                response.failure("The synthetic account could not authenticate")
                setup_failures["authentication"] += 1
                raise StopUser()
        with self.client.get("/", name="setup.session", timeout=30, catch_response=True) as response:
            token = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
            if response.status_code != 200 or not token:
                response.failure("The authenticated session was unavailable")
                setup_failures["session"] += 1
                raise StopUser()
            self.csrf_token = token.group(1)
        self.employee_ids = json.loads(Path(os.environ["HRMS_LAB_EMPLOYEE_IDS_PATH"]).read_text(encoding="utf-8"))
        self.ordinal = user_ordinal
        user_ordinal += 1
        if os.environ.get("HRMS_LAB_BURST", "none") != "none":
            reserved = int(os.environ["HRMS_LAB_EXPECTED_USERS"])
            self.burst_employee_id = self.employee_ids[self.ordinal]
            self.employee_ids = self.employee_ids[reserved:]
        self.register_ready(True)

    def burst_after_steady(self):
        global burst_arrived, burst_completed
        mode = os.environ.get("HRMS_LAB_BURST", "none")
        if window_end is None or mode == "none":
            return False
        burst_arrived += 1
        while burst_start is None:
            gevent.sleep(.05)
        started = time.time()
        if mode == "requests":
            path = "/hr/leave/new"
            payload = {"employee_id": self.burst_employee_id, "start_date": "2030-01-01", "end_date": "2030-01-02",
                "leave_type": "annual", "description": "Synthetic burst " + os.environ["HRMS_LAB_INSTANCE"]}
        else:
            path = f"/employees/{self.burst_employee_id}/status"
            payload = {"active": "false"}
        with self.client.post(path, name="burst." + mode, timeout=30, allow_redirects=False,
            data={**payload, "csrf_token": self.csrf_token}, catch_response=True) as response:
            if response.status_code != 303:
                response.failure("Burst mutation did not return 303")
            location = response.headers.get("location", "")
            match = re.fullmatch(r"/hr/leave/(\d+)\?saved=1", location)
            burst_results.append({"employee_id": self.burst_employee_id, "started_at": started,
                "elapsed_ms": round((time.time() - started) * 1000), "status": response.status_code,
                "request_id": int(match.group(1)) if match else None})
        burst_completed += 1
        while True:
            gevent.sleep(1)

    @task(4)
    def read_records(self):
        if self.burst_after_steady():
            return
        name, path = random.choice((("employees", "/employees"), ("dashboard", "/"),
                                   ("reports", "/reports"), ("requests", "/hr/leave")))
        with self.client.get(path, name="read." + name, timeout=10, catch_response=True) as response:
            if response.status_code != 200 or 'id="username"' in response.text:
                response.failure("Protected read did not return the expected authenticated page")

    @task(1)
    def write_record(self):
        if self.burst_after_steady():
            return
        employee_id = random.choice(self.employee_ids)
        with self.client.post(f"/employees/{employee_id}/status", name="write.employee_status", timeout=10,
            data={"active": random.choice(("true", "false")), "csrf_token": self.csrf_token},
            allow_redirects=False, catch_response=True) as response:
            if response.status_code != 303:
                response.failure("Synthetic status mutation did not return 303")


class LoginPressureUser(LabUser):
    def on_start(self):
        self.verify_target()
        self.csrf_token = self.login_form()
        self.register_ready(False)

    @task
    def password_check(self):
        # A known disposable account and wrong password exercise the real PBKDF2 path.
        with self.client.post("/login", name="login.password_check", timeout=10, allow_redirects=False,
            data={"username": os.environ["HRMS_LAB_USERNAME"], "password": "Intentionally-Wrong-Synthetic-Password",
                  "csrf_token": self.csrf_token}, catch_response=True) as response:
            expected = {int(code) for code in os.environ.get("HRMS_LAB_EXPECTED_LOGIN_CODES", "401").split(",")}
            if response.status_code in expected:
                response.success()
            else:
                response.failure("Unexpected login-pressure response")


@events.quitting.add_listener
def save_metrics(environment, **_):
    effective_end = window_end or time.time()
    seconds = max(0, effective_end - window_start) if window_start is not None else 0
    requests = sum(e["requests"] for e in endpoint_metrics.values())
    failures = sum(e["failures"] for e in endpoint_metrics.values())
    reads = sum(e["requests"] for name, e in endpoint_metrics.items() if name.startswith("read."))
    writes = sum(e["requests"] for name, e in endpoint_metrics.items() if name.startswith("write."))
    endpoints = []
    for name, entry in sorted(endpoint_metrics.items()):
        endpoints.append({"name": name, **entry, "mean_response_bytes": entry["response_bytes"] / entry["requests"],
            "p95_ms": percentile(entry["latency_histogram_ms"], .95)})
    payload = {"protocol_version": 2, "setup_barrier": True,
        "profile": os.environ["HRMS_LAB_PROFILE"], "finish_reason": finish_reason,
        "ready_users_peak": ready_peak, "authenticated_users_peak": authenticated_peak,
        "spawn_completion": spawn_completion, "setup_failures": dict(setup_failures),
        "steady_started_at": window_start, "steady_finished_at": window_end, "steady_seconds": seconds,
        "requests": requests, "failures": failures, "failure_fraction": failures / requests if requests else None,
        "read_requests": reads, "write_requests": writes, "observed_read_fraction": reads / (reads + writes) if reads + writes else None,
        "rps": requests / seconds if seconds else None, "p50_ms": percentile(histogram, .5),
        "workers_observed_steady": dict(workers_observed),
        "p95_ms": percentile(histogram, .95), "p99_ms": percentile(histogram, .99),
        "percentile_method": "Nearest-rank over 1ms response-time buckets; requests started before or completed after the steady window excluded",
        "latency_histogram_ms": dict(sorted(histogram.items())), "endpoints": endpoints,
        "all_window_and_setup_outcomes": [{"name": name, "status": code, "failed": failed, "count": count}
            for (name, code, failed), count in all_outcomes.items()],
        "burst": {"mode": os.environ.get("HRMS_LAB_BURST", "none"), "arrived": burst_arrived,
            "started_at": burst_start, "completed": burst_completed, "outcomes": burst_results}}
    Path(os.environ["HRMS_LAB_METRICS_PATH"]).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
