import json
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import requests
from libs.config import get_setting

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class CaseResult:
    name: str
    ok: bool
    detail: str


def _id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _env(source: str, typ: str, payload: Dict, session_id: str = "demo") -> Dict:
    return {
        "meta": {
            "message_id": _id("m_test_"),
            "timestamp_ms": int(time.time() * 1000),
            "source": source,
            "type": typ,
            "session_id": session_id,
            "trace": {"trace_id": _id("trace_test_"), "span_id": _id("span_test_"), "tags": {}},
        },
        "payload": payload,
    }


def _wait_health(url: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1.5)
            if r.status_code == 200 and isinstance(r.json(), dict) and r.json().get("ok") is True:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"service not ready: {url}")


def _all_up() -> bool:
    urls = [
        "http://127.0.0.1:8001/health",
        "http://127.0.0.1:8002/health",
        "http://127.0.0.1:8003/health",
        "http://127.0.0.1:8004/health",
        "http://127.0.0.1:8005/health",
    ]
    for u in urls:
        try:
            r = requests.get(u, timeout=1.0)
            if r.status_code != 200:
                return False
        except Exception:
            return False
    return True


def _start_services_if_needed() -> Tuple[Optional[subprocess.Popen], str]:
    if _all_up():
        return None, "reuse-existing"
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    p = subprocess.Popen([sys.executable, "scripts/run_all.py"], cwd=ROOT, env=env)
    _wait_health("http://127.0.0.1:8001/health")
    _wait_health("http://127.0.0.1:8002/health")
    _wait_health("http://127.0.0.1:8003/health")
    _wait_health("http://127.0.0.1:8004/health")
    _wait_health("http://127.0.0.1:8005/health")
    return p, "started-by-suite"


def _shutdown(p: Optional[subprocess.Popen]) -> None:
    if p is None:
        return
    try:
        p.send_signal(signal.SIGINT)
        p.wait(timeout=8)
    except Exception:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            pass


def _http_timeout() -> float:
    llm_timeout = float(get_setting("llm.timeout_s", 12))
    nav_total = float(get_setting("nav.amap_mcp_total_timeout_s", 20))
    return max(25.0, llm_timeout + nav_total + 6.0)


def _run_case(name: str, fn: Callable[[], Tuple[bool, str]]) -> CaseResult:
    try:
        ok, detail = fn()
        return CaseResult(name=name, ok=ok, detail=detail)
    except Exception as e:
        return CaseResult(name=name, ok=False, detail=f"{type(e).__name__}: {e}")


def run_suite() -> List[CaseResult]:
    t = _http_timeout()
    results: List[CaseResult] = []

    def c1():
        r = requests.post("http://127.0.0.1:8002/chat", json={
            "meta": {
                "message_id": "m1",
                "timestamp_ms": int(time.time() * 1000),
                "source": "ui",
                "type": "agent.user_utterance",
                "session_id": "demo",
                "trace": {"trace_id": "trace_12345678", "span_id": "span_12345678", "tags": {}},
            },
            "payload": {"text": "hello", "input_modality": "voice", "speaker_role": "passenger", "language": "zh-CN"},
        }, timeout=t)
        d = r.json()
        return (d.get("ok") is False and "invalid meta.message_id" in str(d.get("error", "")), str(d))

    def c2():
        req = _env("ui", "agent.user_utterance", {"text": "把副驾窗开到30%", "input_modality": "voice", "speaker_role": "driver", "language": "zh-CN"})
        d = requests.post("http://127.0.0.1:8002/chat", json=req, timeout=t).json()
        text = ((d.get("payload") or {}).get("text") or "")
        return ("车控" in text, text)

    def c3():
        req = _env("ui", "agent.user_utterance", {"text": "把左后窗开到30%", "input_modality": "voice", "speaker_role": "driver", "language": "zh-CN"})
        requests.post("http://127.0.0.1:8002/chat", json=req, timeout=t)
        s = requests.get("http://127.0.0.1:8003/state", timeout=8).json()
        rl = (((s.get("payload") or {}).get("windows") or {}).get("RL"))
        return (rl == 30, f"RL={rl}")

    def c4():
        req = _env("ui", "agent.user_utterance", {"text": "把右后窗开到40%", "input_modality": "voice", "speaker_role": "driver", "language": "zh-CN"})
        requests.post("http://127.0.0.1:8002/chat", json=req, timeout=t)
        s = requests.get("http://127.0.0.1:8003/state", timeout=8).json()
        rr = (((s.get("payload") or {}).get("windows") or {}).get("RR"))
        return (rr == 40, f"RR={rr}")

    def c5():
        req = _env("ui", "agent.user_utterance", {"text": "温度调到22", "input_modality": "voice", "speaker_role": "driver", "language": "zh-CN"})
        requests.post("http://127.0.0.1:8002/chat", json=req, timeout=t)
        s = requests.get("http://127.0.0.1:8003/state", timeout=8).json()
        temp = (((s.get("payload") or {}).get("ac") or {}).get("temp_c"))
        return (float(temp) == 22.0, f"temp_c={temp}")

    def c6():
        req = _env("ui", "agent.user_utterance", {"text": "你好，介绍一下你会什么", "input_modality": "voice", "speaker_role": "passenger", "language": "zh-CN"})
        d = requests.post("http://127.0.0.1:8002/chat", json=req, timeout=t).json()
        text = ((d.get("payload") or {}).get("text") or "").strip()
        return (len(text) > 0, text)

    def c7():
        req = _env("agent", "nav.poi.request", {"center": {"lat": 31.23, "lon": 121.47}, "query": "星巴克", "radius_m": 5000, "limit": 3})
        d = requests.post("http://127.0.0.1:8005/poi", json=req, timeout=t).json()
        items = ((d.get("payload") or {}).get("items") or [])
        return (isinstance(items, list) and len(items) >= 1, f"items={len(items)}")

    def c8():
        req = _env("agent", "nav.route.request", {
            "origin": {"lat": 39.90923, "lon": 116.397428},
            "destination": {"lat": 39.90816, "lon": 116.43383},
            "mode": "driving",
            "avoid": [],
        })
        d = requests.post("http://127.0.0.1:8005/route", json=req, timeout=t).json()
        p = d.get("payload") or {}
        return ("summary" in p and "distance_m" in p and "duration_s" in p, json.dumps(p, ensure_ascii=False))

    def c9():
        d = requests.get("http://127.0.0.1:8005/debug/provider", timeout=8).json()
        return ("provider_mode" in d and "last_mcp_error" in d, json.dumps(d, ensure_ascii=False))

    def c10():
        req = _env("agent", "audio.tts.request", {"text": "你好，这是TTS测试"})
        d = requests.post("http://127.0.0.1:8001/tts", json=req, timeout=t).json()
        typ = ((d.get("meta") or {}).get("type"))
        return (typ == "audio.tts.audio", f"type={typ}")

    def c11():
        req = _env("ui", "dms.frame.ingest", {"frame_b64": "AA==", "camera_id": "driver_cam"})
        d = requests.post("http://127.0.0.1:8004/frame", json=req, timeout=t).json()
        typ = ((d.get("meta") or {}).get("type"))
        return (typ == "dms.event", f"type={typ}")

    def c12():
        req = _env("agent", "vehicle.command", {"command": "set_window", "args": {"position": "XX", "percent": 30}})
        d = requests.post("http://127.0.0.1:8003/command", json=req, timeout=t).json()
        return (d.get("ok") is False, json.dumps(d, ensure_ascii=False))

    def c13():
        req = _env("agent", "nav.poi.request", {"center": {"lat": 31.23, "lon": 121.47}})
        d = requests.post("http://127.0.0.1:8005/poi", json=req, timeout=t).json()
        return (d.get("ok") is False, json.dumps(d, ensure_ascii=False))

    cases = [
        ("schema validation rejects short message_id", c1),
        ("agent chat window command responds", c2),
        ("left rear window set to 30", c3),
        ("right rear window set to 40", c4),
        ("ac temperature set to 22", c5),
        ("passenger chat returns response", c6),
        ("nav poi returns items", c7),
        ("nav route returns summary and metrics", c8),
        ("nav debug endpoint returns provider info", c9),
        ("audio tts endpoint returns envelope", c10),
        ("dms frame endpoint returns event", c11),
        ("vehicle invalid command rejected", c12),
        ("nav invalid request rejected", c13),
    ]

    for name, fn in cases:
        results.append(_run_case(name, fn))
    return results


def main() -> int:
    runner, mode = _start_services_if_needed()
    print(f"[suite] service mode: {mode}")
    try:
        results = run_suite()
    finally:
        _shutdown(runner)

    passed = sum(1 for r in results if r.ok)
    total = len(results)
    print("")
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"[{status}] {r.name} :: {r.detail}")
    print("")
    print(f"[suite] result: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
