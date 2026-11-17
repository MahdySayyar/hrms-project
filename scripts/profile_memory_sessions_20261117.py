"""Measure memory-only session insertion with disposable synthetic state."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.session_store import MemorySessionStore, Session


def measure(size):
    entries = [(str(index), Session(None, "synthetic", time.time() + 1800)) for index in range(size)]
    samples = []
    for _ in range(5):
        store = MemorySessionStore()
        start = time.perf_counter()
        for token, session in entries:
            store.put(token, session)
        samples.append(round((time.perf_counter() - start) * 1000, 3))
        assert len(store.sessions) == size
    return {"insertions": size, "sample_ms": samples, "median_ms": statistics.median(samples)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT)
    report = {"phase": args.phase, "synthetic_only": True, "scope": "MemorySessionStore.put, excludes HTTP and password hashing",
              "results": [measure(size) for size in (500, 5000)]}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
