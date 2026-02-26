import json
import sys
import time
from typing import Dict

import requests

from libs.config import get_setting
from services.agent_service.core.llm import OpenAICompatLLM, build_planner_messages


def _env(source: str, typ: str, payload: Dict, suffix: str) -> Dict:
    now = int(time.time() * 1000)
    return {
        "meta": {
            "message_id": f"m_ready_{suffix}",
            "timestamp_ms": now,
            "source": source,
            "type": typ,
            "session_id": "demo",
            "trace": {"trace_id": f"trace_ready_{suffix}", "span_id": f"span_ready_{suffix}", "tags": {}},
        },
        "payload": payload,
    }


def _assert_http_ok(url: str) -> None:
    r = requests.get(url, timeout=3)
    if r.status_code != 200:
        raise RuntimeError(f"{url} status={r.status_code}")
    data = r.json()
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError(f"{url} bad body={data}")


def main() -> int:
    llm_timeout = float(get_setting("llm.timeout_s", 12))
    http_timeout = max(15.0, llm_timeout + 6.0)

    print("[1/4] health checks")
    _assert_http_ok("http://127.0.0.1:8002/health")
    _assert_http_ok("http://127.0.0.1:8003/health")

    print("[2/4] llm direct check")
    llm = OpenAICompatLLM()
    if not llm.enabled():
        raise RuntimeError("LLM not enabled: missing llm.api_key")
    raw = llm.chat_json(build_planner_messages("把副驾窗开到30%", "driver", "zh-CN"))
    if not isinstance(raw, dict) or raw.get("type") not in {"tool_call", "message"}:
        raise RuntimeError(f"unexpected llm output: {raw}")
    print("llm output:", json.dumps(raw, ensure_ascii=False))

    print("[3/4] agent vehicle path")
    req1 = _env("ui", "agent.user_utterance", {
        "text": "把副驾窗开到30%",
        "input_modality": "voice",
        "speaker_role": "driver",
        "language": "zh-CN",
    }, "0001")
    try:
        r1 = requests.post("http://127.0.0.1:8002/chat", json=req1, timeout=http_timeout)
    except requests.ReadTimeout:
        # One retry for transient LLM latency spikes
        r1 = requests.post("http://127.0.0.1:8002/chat", json=req1, timeout=http_timeout)
    d1 = r1.json()
    t1 = ((d1.get("payload") or {}).get("text") or "")
    if "车控" not in t1:
        raise RuntimeError(f"vehicle path unexpected: {d1}")
    print("agent vehicle:", t1)

    r_state = requests.get("http://127.0.0.1:8003/state", timeout=5)
    state = ((r_state.json().get("payload") or {}).get("windows") or {})
    if state.get("FR") != 30:
        raise RuntimeError(f"vehicle state mismatch, expected FR=30 got {state}")
    print("vehicle state FR=30 confirmed")

    print("[4/4] agent passenger chat path")
    req2 = _env("ui", "agent.user_utterance", {
        "text": "你好，介绍一下你能做什么",
        "input_modality": "voice",
        "speaker_role": "passenger",
        "language": "zh-CN",
    }, "0002")
    try:
        r2 = requests.post("http://127.0.0.1:8002/chat", json=req2, timeout=http_timeout)
    except requests.ReadTimeout:
        r2 = requests.post("http://127.0.0.1:8002/chat", json=req2, timeout=http_timeout)
    d2 = r2.json()
    t2 = ((d2.get("payload") or {}).get("text") or "").strip()
    if not t2:
        raise RuntimeError(f"passenger path empty response: {d2}")
    print("agent passenger:", t2)

    print("\nLLM readiness: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"\nLLM readiness: FAIL - {type(e).__name__}: {e}")
        raise SystemExit(1)
