"""Compare synthetic password costs; never reads application credentials or HR data."""
import argparse
import hashlib
import json
import math
import platform
import ssl
import time
from concurrent.futures import ThreadPoolExecutor

from argon2 import PasswordHasher, Type


def profile(count):
    password = "Synthetic-crypto-profile-only"
    # OWASP minimum Argon2id profile: 19 MiB, two iterations, one lane.
    hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1, type=Type.ID)
    encoded = hasher.hash(password)
    expected = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes(16), 600000)
    rows = []
    for algorithm in ("pbkdf2_sha256_600000", "argon2id_m19456_t2_p1"):
        for workers in (1, 2, 4, 8):
            def verify(_index):
                begin = time.perf_counter()
                if algorithm.startswith("pbkdf2"):
                    assert hashlib.pbkdf2_hmac("sha256", password.encode(), bytes(16), 600000) == expected
                else:
                    assert hasher.verify(encoded, password)
                return (time.perf_counter() - begin) * 1000
            begin = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                timings = sorted(pool.map(verify, range(count)))
            elapsed = time.perf_counter() - begin
            rows.append({"algorithm": algorithm, "workers": workers, "checks": count,
                "elapsed_ms": round(elapsed * 1000, 2), "checks_per_second": round(count / elapsed, 2),
                "execution_p50_ms": round(timings[math.ceil(count * .5) - 1], 2),
                "execution_p95_ms": round(timings[math.ceil(count * .95) - 1], 2)})
    return {"platform": platform.system(), "python": platform.python_version(), "openssl": ssl.OPENSSL_VERSION,
        "synthetic_only": True, "timings_exclude_web_database_and_queue": True,
        "parameters_source": "https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html",
        "measurements": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checks", type=int, default=32)
    options = parser.parse_args()
    if not 8 <= options.checks <= 500:
        parser.error("Use 8..500 synthetic checks.")
    print(json.dumps(profile(options.checks), indent=2))
