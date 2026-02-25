# Cockpit Agent Demo (Python-only)

This repository is a Python-only demo for an intelligent cockpit agent:
- Audio: VAD / Wakeword / ASR / TTS
- Agent: tool-calling orchestration with policies
- Vehicle: simulator + control API
- DMS: demo pipeline -> events
- Nav: HTTP + MCP server for route/poi

## Core rule
All cross-service messages MUST be wrapped by `schemas/common/envelope.schema.json`.

## Next
- Define FastAPI endpoints for each service
- Implement event bus topics (WS pub/sub)
