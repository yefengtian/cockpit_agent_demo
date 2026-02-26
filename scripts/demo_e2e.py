import json
import os
import signal
import subprocess
import sys
import time
import uuid
from typing import Dict

import requests
from libs.config import get_setting

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


def _id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _envelope(source: str, typ: str, payload: Dict) -> Dict:
    return {
        "meta": {
            "message_id": _id("m_demo_"),
            "timestamp_ms": int(time.time() * 1000),
            "source": source,
            "type": typ,
            "session_id": "demo",
            "trace": {"trace_id": _id("trace_demo_"), "span_id": _id("span_demo_"), "tags": {}},
        },
        "payload": payload,
    }


def main() -> None:
    llm_timeout = float(get_setting("llm.timeout_s", 12))
    nav_total_timeout = float(get_setting("nav.amap_mcp_total_timeout_s", 20))
    http_timeout = max(20.0, llm_timeout + nav_total_timeout + 4.0)

    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    runner = subprocess.Popen([sys.executable, "scripts/run_all.py"], cwd=ROOT, env=env)

    try:
        _wait_health("http://127.0.0.1:8002/health")
        _wait_health("http://127.0.0.1:8003/health")
        _wait_health("http://127.0.0.1:8005/health")

        req1 = _envelope("ui", "agent.user_utterance", {"text": "把左后车窗开到80%", "input_modality": "voice", "speaker_role": "driver", "language": "zh-CN"})
        r1 = requests.post("http://127.0.0.1:8002/chat", json=req1, timeout=http_timeout)
        print("agent chat(window) status=", r1.status_code)
        print("agent chat(window):", json.dumps(r1.json(), ensure_ascii=False))

        req2 = _envelope("ui", "agent.user_utterance", {"text": "最近的星巴克", "input_modality": "voice", "speaker_role": "passenger", "language": "zh-CN"})
        r2 = requests.post("http://127.0.0.1:8002/chat", json=req2, timeout=http_timeout)
        print("agent chat(nav) status=", r2.status_code)
        print("agent chat(nav):", json.dumps(r2.json(), ensure_ascii=False))

        r3 = requests.get("http://127.0.0.1:8003/state", timeout=http_timeout)
        print("vehicle state:", json.dumps(r3.json(), ensure_ascii=False))

        r4 = requests.get("http://127.0.0.1:8005/debug/provider", timeout=http_timeout)
        print("nav debug:", json.dumps(r4.json(), ensure_ascii=False))
    finally:
        try:
            runner.send_signal(signal.SIGINT)
            runner.wait(timeout=8)
        except Exception:
            runner.terminate()
            runner.wait(timeout=5)


if __name__ == "__main__":
    main()
