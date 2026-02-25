import json
import os
import signal
import subprocess
import sys
import time
from typing import Dict

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _wait_health(url: str, timeout_s: int = 15) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"service not ready: {url}")


def _envelope(source: str, typ: str, payload: Dict) -> Dict:
    return {
        "meta": {
            "message_id": "m_demo_0001",
            "timestamp_ms": int(time.time() * 1000),
            "source": source,
            "type": typ,
            "session_id": "demo",
            "trace": {"trace_id": "trace_demo_001", "span_id": "span_demo_001", "tags": {}},
        },
        "payload": payload,
    }


def main() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    runner = subprocess.Popen([sys.executable, "scripts/run_all.py"], cwd=ROOT, env=env)

    try:
        _wait_health("http://127.0.0.1:8002/health")
        _wait_health("http://127.0.0.1:8003/health")
        _wait_health("http://127.0.0.1:8005/health")

        req1 = _envelope("ui", "agent.user_utterance", {"text": "把副驾窗开到30%", "input_modality": "voice"})
        r1 = requests.post("http://127.0.0.1:8002/chat", json=req1, timeout=5)
        print("agent chat(window):", json.dumps(r1.json(), ensure_ascii=False))

        req2 = _envelope("ui", "agent.user_utterance", {"text": "最近的星巴克", "input_modality": "voice"})
        r2 = requests.post("http://127.0.0.1:8002/chat", json=req2, timeout=5)
        print("agent chat(nav):", json.dumps(r2.json(), ensure_ascii=False))

        r3 = requests.get("http://127.0.0.1:8003/state", timeout=5)
        print("vehicle state:", json.dumps(r3.json(), ensure_ascii=False))
    finally:
        try:
            runner.send_signal(signal.SIGINT)
            runner.wait(timeout=8)
        except Exception:
            runner.terminate()
            runner.wait(timeout=5)


if __name__ == "__main__":
    main()
