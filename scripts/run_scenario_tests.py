from __future__ import annotations

import os
import subprocess
import sys
import time

import httpx


ROOT = os.path.dirname(os.path.dirname(__file__))
BASE_URL = os.getenv("FLEETSHARE_BASE_URL", "http://localhost:8000")


def run(command: list[str], *, env: dict[str, str] | None = None):
    print(f"[fleetshare-runner] {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True, env=env)


def wait_for_stack(timeout_seconds: int = 180):
    print(f"[fleetshare-runner] waiting for stack at {BASE_URL}")
    deadline = time.time() + timeout_seconds
    with httpx.Client(timeout=5.0) as client:
        while time.time() < deadline:
            try:
                response = client.get(f"{BASE_URL}/vehicles")
                if response.status_code == 200:
                    print("[fleetshare-runner] stack is ready")
                    return
            except Exception:
                pass
            time.sleep(2)
    raise RuntimeError(f"FleetShare stack did not become ready within {timeout_seconds} seconds.")


def main():
    keep_up = "--keep-up" in sys.argv
    env = os.environ.copy()
    env["RUN_E2E"] = "1"
    env["FLEETSHARE_BASE_URL"] = BASE_URL

    run(["docker", "compose", "down", "-v"])
    run(["docker", "compose", "up", "--build", "-d"])
    wait_for_stack()

    try:
        run(["pytest", "-s", "tests/test_scenarios_e2e.py"], env=env)
    finally:
        if not keep_up:
            run(["docker", "compose", "down", "-v"])


if __name__ == "__main__":
    main()
