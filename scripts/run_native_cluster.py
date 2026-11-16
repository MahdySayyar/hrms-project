"""Supervise only this invocation's localhost web processes and affinity proxy."""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time

import httpx
import psutil


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stop(process):
    try:
        parent = psutil.Process(process.pid)
        family = [parent, *parent.children(recursive=True)]
    except psutil.Error:
        return
    for child in reversed(family):
        try:
            child.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(family, timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass


def run(args):
    if not 1 <= args.workers <= 8 or not 1 <= args.threads <= 40 or not 1 <= args.pool_size <= 10:
        raise ValueError("Use 1..8 workers, 1..40 threads and 1..10 DB connections per web.")
    children, urls = [], []
    stopped = False
    def shutdown(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        for index in range(args.workers):
            port = free_port()
            urls.append(f"http://127.0.0.1:{port}")
            environment = os.environ.copy()
            environment.update({"HRMS_THREADS": str(args.threads), "HRMS_DB_POOL_SIZE": str(args.pool_size),
                "HRMS_DB_MAX_OVERFLOW": "0", "INSTANCE_ID": os.getenv("INSTANCE_ID", "hrms-local-1") + f"-web-{index}"})
            children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", "127.0.0.1", "--port", str(port), "--http", args.http_parser], env=environment))
        deadline = time.monotonic() + 30
        pending = set(urls)
        while pending and time.monotonic() < deadline and not stopped:
            for url in list(pending):
                try:
                    if httpx.get(url + "/health", timeout=1, trust_env=False).status_code == 200:
                        pending.remove(url)
                except httpx.HTTPError:
                    pass
            time.sleep(.1)
        if pending:
            raise RuntimeError("One or more isolated native workers did not become ready.")
        environment = os.environ.copy()
        environment["HRMS_NATIVE_BACKENDS"] = json.dumps(urls)
        children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.native_proxy:app",
            "--host", "127.0.0.1", "--port", str(args.port), "--http", args.http_parser], env=environment))
        print(json.dumps({"native_workers": args.workers, "threads_per_web": args.threads,
            "max_db_connections_per_web": args.pool_size, "session_policy": "browser affinity / process-local"}), flush=True)
        while not stopped:
            if any(process.poll() is not None for process in children):
                raise RuntimeError("An owned native cluster child exited; stopping this cluster.")
            time.sleep(.5)
    finally:
        for process in reversed(children):
            stop(process)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--pool-size", type=int, default=10)
    parser.add_argument("--http-parser", choices=("auto", "h11", "httptools"), default="auto")
    parser.add_argument("--port", type=int, default=8000)
    run(parser.parse_args())
