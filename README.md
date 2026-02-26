# Cockpit Agent Demo (Python-only)

Python multi-service demo for an intelligent cockpit assistant.

## What this project demonstrates
- `audio_service`: audio ingest/transcript/tts demo endpoints
- `agent_service`: utterance planning and tool orchestration
- `vehicle_service`: in-memory vehicle simulator and control API
- `dms_service`: driver-monitoring demo events
- `nav_service`: route/poi demo APIs

The current runnable core loop is:
1. Send user utterance to `agent_service`
2. Agent plans a tool call (`vehicle.control` or `nav.poi`)
3. Agent calls target service
4. Agent returns `agent.out` response

Stage 2 adds:
- LLM-based planner (OpenAI-compatible API)
- Driver/passenger utterance support (`speaker_role`)
- AMap MCP integration path for navigation

## Architecture
- Service apps: `services/*/app.py`
- Routers: `services/*/routers/*.py`
- Shared libs: `libs/*`
- Message contracts: `schemas/**/*.schema.json`
- Runner scripts: `scripts/*.py`

## Message contract rule
All cross-service messages must use the common envelope:
- `schemas/common/envelope.schema.json`

Envelope shape:
- `meta`: message/trace/session metadata
- `payload`: business body

## Requirements
- Python `>=3.9`
- Recommended: virtual environment in repo root

## Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e . --no-use-pep517
```

Notes:
- For newer pip versions, `pip install -e .` should also work.
- `setup.py` is included to support older pip editable mode behavior.

## Configuration file
Primary config file:
- `config/app_config.json`

Local secret override file (recommended, git-ignored):
- `config/app_config.local.json`
- start from `config/app_config.local.example.json`

Example:
```bash
cp config/app_config.local.example.json config/app_config.local.json
```

Config priority:
1. `APP_CONFIG_FILE` (if set)
2. `config/app_config.json`
3. `config/app_config.local.json` (overlay)

The code now reads LLM, nav provider/MCP command, and service ports from this config layer.

## Run services
```bash
python scripts/run_all.py
```

Service ports (default):
- audio: `8001`
- agent: `8002`
- vehicle: `8003`
- dms: `8004`
- nav: `8005`

## End-to-end demo
Run one command to boot services, send sample requests, and print outputs:
```bash
python scripts/demo_e2e.py
```

## Stage 2 verify script
Offline verification (mocks LLM/MCP/HTTP paths):
```bash
python scripts/verify_stage2.py
```

Config loading verification:
```bash
python scripts/verify_config_loading.py
```

## Manual API demo
### 1) Vehicle window control via agent
```bash
curl -sS -X POST http://127.0.0.1:8002/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "meta": {
      "message_id": "m_demo_1001",
      "timestamp_ms": 1772000000000,
      "source": "ui",
      "type": "agent.user_utterance",
      "session_id": "demo",
      "trace": {"trace_id": "trace_demo_001", "span_id": "span_demo_001", "tags": {}}
    },
    "payload": {"text": "把副驾窗开到30%", "input_modality": "voice", "speaker_role": "driver", "language": "zh-CN"}
  }'
```

### 2) Check vehicle state
```bash
curl -sS http://127.0.0.1:8003/state
```

### 3) POI request via agent
```bash
curl -sS -X POST http://127.0.0.1:8002/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "meta": {
      "message_id": "m_demo_1002",
      "timestamp_ms": 1772000001000,
      "source": "ui",
      "type": "agent.user_utterance",
      "session_id": "demo",
      "trace": {"trace_id": "trace_demo_001", "span_id": "span_demo_002", "tags": {}}
    },
    "payload": {"text": "最近的星巴克", "input_modality": "voice", "speaker_role": "passenger", "language": "zh-CN"}
  }'
```

## LLM planner configuration
Agent planner uses OpenAI-compatible chat-completions API.

Set in config file:
```json
{
  "llm": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "<your_api_key>",
    "model": "gpt-4o-mini",
    "timeout_s": 12
  }
}
```

Behavior:
- If `LLM_API_KEY` is set, planner uses LLM first.
- If LLM call fails, planner falls back to rule-based logic.

## AMap MCP integration
`nav_service` supports provider mode:
- `stub` (default)
- `amap_mcp`

Set in config file:
```json
{
  "nav": {
    "provider": "amap_mcp",
    "amap_mcp_command": "npx -y -p @amap/amap-maps-mcp-server mcp-amap",
    "amap_mcp_env": {
      "AMAP_MAPS_API_KEY": "<YOUR_AMAP_KEY>"
    },
    "amap_mcp_timeout_s": 8,
    "amap_mcp_transport": "auto"
  }
}
```

Then start services and call `/poi` or `/route` through `agent_service`.

This follows your verified AMap MCP smoke setup:
`npx -y -p @amap/amap-maps-mcp-server mcp-amap` with `AMAP_MAPS_API_KEY`.
`amap_mcp_transport` supports `auto` (recommended), `ndjson`, and `content_length`.

Implementation notes:
- File: `services/nav_service/providers/amap_mcp.py`
- Transport: MCP stdio (JSON-RPC framing with `Content-Length`)
- `nav_service` falls back to built-in stub result when MCP is unavailable

## Current scope and limitations
- `audio_service` and `dms_service` remain demo-oriented stubs
- MCP local server under `nav_service/mcp/server.py` is placeholder; production flow expects external AMap MCP command via config field `nav.amap_mcp_command`
- No automated tests yet
- Schema validation is lightweight and currently covers main demo paths

## Release notes
See:
- `RELEASE_NOTES.md`
