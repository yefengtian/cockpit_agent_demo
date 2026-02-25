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
    "payload": {"text": "把副驾窗开到30%", "input_modality": "voice"}
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
    "payload": {"text": "最近的星巴克", "input_modality": "voice"}
  }'
```

## Current scope and limitations
- `audio_service` and `dms_service` remain demo-oriented stubs
- MCP server in `nav_service/mcp/server.py` is placeholder
- No automated tests yet
- Schema validation is lightweight and currently covers the main demo paths

## Release notes
See:
- `RELEASE_NOTES.md`
