import json
import os
from functools import lru_cache
from typing import Any, Dict


def _repo_root() -> str:
    # libs/config/app_config.py -> repo_root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def load_app_config() -> Dict[str, Any]:
    root = _repo_root()
    default_cfg = {
        "services": {
            "audio_port": 8001,
            "agent_port": 8002,
            "vehicle_port": 8003,
            "dms_port": 8004,
            "nav_port": 8005,
        },
        "llm": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-4o-mini",
            "timeout_s": 12,
        },
        "nav": {
            "provider": "stub",
            "amap_mcp_command": "",
            "amap_mcp_env": {},
            "amap_mcp_timeout_s": 8,
        },
    }

    cfg_file = os.getenv("APP_CONFIG_FILE", os.path.join(root, "config", "app_config.json"))
    local_file = os.path.join(root, "config", "app_config.local.json")
    skip_local = os.getenv("APP_CONFIG_SKIP_LOCAL", "0") == "1"
    file_cfg = _read_json(cfg_file)
    local_cfg = {} if skip_local else _read_json(local_file)
    merged = _deep_merge(default_cfg, file_cfg)
    merged = _deep_merge(merged, local_cfg)
    return merged


def reload_app_config() -> Dict[str, Any]:
    load_app_config.cache_clear()
    return load_app_config()


def get_setting(path: str, default: Any = None) -> Any:
    cfg = load_app_config()
    cur: Any = cfg
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur
