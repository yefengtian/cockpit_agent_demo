# Cockpit Agent Demo (Python-only)

This repository is a Python-only demo for an intelligent cockpit agent:
- Audio: VAD / Wakeword / ASR / TTS
- Agent: tool-calling orchestration with policies
- Vehicle: simulator + control API
- DMS: demo pipeline -> events
- Nav: HTTP + MCP server for route/poi

## Core rule
All cross-service messages MUST be wrapped by `schemas/common/envelope.schema.json`.

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Start all services:
```bash
python scripts/run_all.py
```

## End-to-end demo
Run one command to start services, send demo requests, and print results:
```bash
python scripts/demo_e2e.py
```

Expected flow:
1. User utterance -> `agent_service /chat`
2. Agent plans tool call (`vehicle.control` or `nav.poi`)
3. Agent calls target service
4. Agent returns `agent.out` envelope

## Service ports
- audio: `8001`
- agent: `8002`
- vehicle: `8003`
- dms: `8004`
- nav: `8005`
