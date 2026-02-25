import importlib
import json
import os
import tempfile


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg_path = os.path.join(td, "app_config.json")
        cfg = {
            "llm": {
                "base_url": "https://example.openai.compat/v1",
                "api_key": "demo_key_from_config",
                "model": "demo-model",
                "timeout_s": 7,
            },
            "nav": {
                "provider": "amap_mcp",
                "amap_mcp_command": "echo fake-mcp-command",
                "amap_mcp_env": {"AMAP_MAPS_API_KEY": "k_demo"},
            },
            "services": {
                "audio_port": 9101,
                "agent_port": 9102,
                "vehicle_port": 9103,
                "dms_port": 9104,
                "nav_port": 9105,
            },
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)

        os.environ["APP_CONFIG_FILE"] = cfg_path
        os.environ["APP_CONFIG_SKIP_LOCAL"] = "1"

        from libs.config import app_config

        app_config.reload_app_config()
        from libs.config import get_setting

        assert get_setting("llm.api_key") == "demo_key_from_config"
        assert get_setting("nav.provider") == "amap_mcp"
        assert int(get_setting("services.agent_port")) == 9102

        llm_mod = importlib.import_module("services.agent_service.core.llm")
        llm_mod = importlib.reload(llm_mod)
        llm = llm_mod.OpenAICompatLLM()
        assert llm.api_key == "demo_key_from_config"
        assert llm.model == "demo-model"
        assert llm.timeout_s == 7

        amap_mod = importlib.import_module("services.nav_service.providers.amap_mcp")
        amap_mod = importlib.reload(amap_mod)
        p = amap_mod.AmapMCPProvider()
        assert p.command == "echo fake-mcp-command"
        assert p.extra_env.get("AMAP_MAPS_API_KEY") == "k_demo"

        run_all_mod = importlib.import_module("scripts.run_all")
        run_all_mod = importlib.reload(run_all_mod)
        ports = [x[2] for x in run_all_mod.SERVICES]
        assert ports == [9101, 9102, 9103, 9104, 9105]

    print("Config file loading verification passed.")


if __name__ == "__main__":
    main()
