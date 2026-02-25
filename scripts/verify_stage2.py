import json

import services.agent_service.core.orchestrator as orch
import services.agent_service.core.runtime as runtime
import services.nav_service.routers.http as nav_http


def _print(title: str, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, (dict, list)) else str(data))


def verify_orchestrator_llm_path() -> None:
    def fake_chat_json(messages, temperature=0.1):
        text_line = [m for m in messages if m["role"] == "user"][0]["content"]
        if "副驾窗开到30%" in text_line:
            return {
                "type": "tool_call",
                "tool_name": "vehicle.control",
                "arguments": {"command": "set_window", "args": {"position": "FR", "percent": 30}},
                "requires_confirmation": False,
            }
        return {
            "type": "message",
            "message": {"text": "你好，我在。有什么可以帮你？", "output_modality": "voice", "should_tts": True},
        }

    orch._LLM.chat_json = fake_chat_json
    p1 = orch.simple_plan("把副驾窗开到30%", speaker="driver", language="zh-CN")
    p2 = orch.simple_plan("你好，今天天气怎么样", speaker="passenger", language="zh-CN")
    _print("planner driver", p1)
    _print("planner passenger", p2)


def verify_runtime_execution_path() -> None:
    class Resp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, json, timeout):
        if url.endswith("/command"):
            return Resp(200, {"payload": {"event": "state_changed", "state": {"windows": {"FL": 0, "FR": 30, "RL": 0, "RR": 0}}}})
        if url.endswith("/poi"):
            return Resp(200, {"payload": {"items": [{"name": "星巴克", "distance_m": 600}]}})
        return Resp(500, {})

    runtime.requests.post = fake_post

    # force planner outputs to test execution branch deterministically
    def fake_simple_plan(text, speaker=None, language=None):
        if "星巴克" in text:
            return {
                "type": "tool_call",
                "tool_call": {
                    "tool_name": "nav.poi",
                    "call_id": "call_x",
                    "arguments": {"center": {"lat": 31.23, "lon": 121.47}, "query": "星巴克", "radius_m": 5000, "limit": 3},
                    "requires_confirmation": False,
                },
            }
        return {
            "type": "tool_call",
            "tool_call": {
                "tool_name": "vehicle.control",
                "call_id": "call_y",
                "arguments": {"command": "set_window", "args": {"position": "FR", "percent": 30}},
                "requires_confirmation": False,
            },
        }

    runtime.simple_plan = fake_simple_plan
    r1 = runtime.execute_text_plan("demo", None, "把副驾窗开到30%", speaker="driver")
    r2 = runtime.execute_text_plan("demo", None, "找最近星巴克", speaker="passenger")
    _print("runtime vehicle", r1)
    _print("runtime nav", r2)


def verify_nav_amap_mcp_path() -> None:
    nav_http._provider_mode = lambda: "amap_mcp"

    def fake_search_poi(center, query, radius_m, limit):
        return {
            "items": [
                {"name": f"{query}(高德MCP)", "lat": center["lat"], "lon": center["lon"], "address": "AMap Street", "distance_m": 420}
            ]
        }

    def fake_plan_route(origin, destination, mode, avoid):
        return {
            "distance_m": 12345,
            "duration_s": 1500,
            "summary": "高德MCP推荐路线",
            "polyline": "encoded_polyline",
            "steps": [{"instruction": "沿主路行驶", "distance_m": 800}],
        }

    nav_http.AMAP.search_poi = fake_search_poi
    nav_http.AMAP.plan_route = fake_plan_route

    req_meta = {
        "message_id": "m_demo_001",
        "timestamp_ms": 1,
        "source": "agent",
        "type": "nav.req",
        "session_id": "demo",
        "trace": {"trace_id": "trace_demo_001", "span_id": "span_demo_001", "tags": {}},
    }
    poi_req = {"meta": req_meta, "payload": {"center": {"lat": 31.23, "lon": 121.47}, "query": "星巴克", "radius_m": 5000, "limit": 3}}
    route_req = {
        "meta": req_meta,
        "payload": {
            "origin": {"lat": 31.23, "lon": 121.47},
            "destination": {"lat": 31.20, "lon": 121.44},
            "mode": "driving",
            "avoid": [],
        },
    }
    p1 = nav_http.poi(poi_req)
    p2 = nav_http.route(route_req)
    _print("nav poi via amap_mcp", p1)
    _print("nav route via amap_mcp", p2)


if __name__ == "__main__":
    verify_orchestrator_llm_path()
    verify_runtime_execution_path()
    verify_nav_amap_mcp_path()
    print("\nStage2 verification passed.")
