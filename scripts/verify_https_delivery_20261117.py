"""Verify TLS using a disposable certificate inside a fresh delivery lab."""
import os
import re
import ssl
import subprocess

import httpx


def verify_https(compose, source, environment, port, run):
    if not environment.get("COMPOSE_PROJECT_NAME", "").startswith("hrms-https-"):
        raise ValueError("HTTPS verification requires an owned disposable lab.")
    directory = source / ".runtime" / "tls"
    directory.mkdir(exist_ok=False)
    run(["docker", "run", "--rm", "--network", "none", "--volume", f"{directory.as_posix()}:/tls",
        "postgres:17.6-bookworm", "sh", "-ec", "openssl req -x509 -nodes -newkey rsa:2048 -days 1 "
        "-subj /CN=localhost -addext subjectAltName=DNS:localhost,IP:127.0.0.1 "
        "-keyout /tls/key.pem -out /tls/cert.pem; chgrp 10001 /tls/key.pem; chmod 640 /tls/key.pem"])
    config = dict(environment, HRMS_TLS_DIR=str(directory))
    secure_compose = [*compose, "-f", str(source / "deployments" / "compose.https.yaml")]
    result = subprocess.run([*secure_compose, "up", "-d", "--wait", "--wait-timeout", "180"],
        cwd=source, env=config, capture_output=True, text=True, timeout=210)
    if result.returncode:
        raise RuntimeError("Disposable HTTPS environment failed to start.")
    context = ssl.create_default_context(cafile=os.fspath(directory / "cert.pem"))
    with httpx.Client(base_url=f"https://127.0.0.1:{port}", verify=context, trust_env=False) as client:
        response = client.get("/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
        if response.status_code != 200 or not token:
            raise RuntimeError("TLS login form unavailable.")
        cookies = response.headers.get_list("set-cookie")
        secure_session = any(value.startswith("hrms_session=") and "; secure" in value.lower() for value in cookies)
        passwords = source / ".runtime" / "docker-hrms-secrets"
        logged_in = client.post("/login", data={"username": "hradmin",
            "password": (passwords / "admin_password").read_text().strip(), "csrf_token": token[1]})
        dashboard = client.get("/")
        session_after_login = any(value.startswith("hrms_session=") and "; secure" in value.lower()
            for value in logged_in.headers.get_list("set-cookie"))
        static_assets = all(reference in response.text and client.get(path).status_code == 200 for reference, path in (
            ('href="/static/style.css"', "/static/style.css"), ('href="/static/modules.css"', "/static/modules.css"),
            ('src="/static/forms.js"', "/static/forms.js")))
        return {"https_certificate_verified": response.http_version.startswith("HTTP/"),
                "https_anonymous_cookie_secure": secure_session, "https_authenticated_cookie_secure": session_after_login,
                "https_authenticated_dashboard": logged_in.status_code == 303 and dashboard.status_code == 200,
                "https_static_assets_same_origin": static_assets}
