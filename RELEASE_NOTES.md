# Release Notes

## v0.2.0-stage2 (2026-02-26)

Tag: `v0.2.0-stage2`

### Summary
Stage 2 delivers an LLM-first cockpit agent flow with hardened AMap MCP integration, unified config management, and runtime readiness tooling.

### Highlights
- Added LLM planner normalization for vehicle control command variants.
- Added local `LLM readiness` check script:
  - `scripts/llm_readiness_check.py`
- Hardened AMap MCP integration:
  - configurable transport (`auto` / `ndjson` / `content_length`)
  - timeout budget controls (`amap_mcp_timeout_s`, `amap_mcp_total_timeout_s`)
  - robust stdio parsing and improved diagnostics
  - tool name mapping aligned with observed AMap MCP tools
  - AMap response normalization into project canonical schemas
- Enhanced nav debug endpoint:
  - provider mode/command/transport visibility
  - last provider path and MCP error reason
- Added config defaults and local examples for new nav fields.

### Operational Notes
- Keep local secrets in `config/app_config.local.json` (git-ignored).
- Node dependencies are local-only (`node_modules/` ignored).
- MCP success depends on external conditions:
  - network availability
  - valid `AMAP_MAPS_API_KEY`
  - provider-side service availability

## v0.1.0-demo.1 (2026-02-25)

Tag: `v0.1.0-demo.1`

### Summary
This release delivers a runnable cockpit agent demo with an end-to-end flow:
user utterance -> agent planning -> tool execution -> agent response.

### Highlights
- Added end-to-end demo runner script:
  - `scripts/demo_e2e.py`
- Implemented unified agent runtime for tool execution:
  - `services/agent_service/core/runtime.py`
- Unified HTTP and WebSocket behavior in `agent_service`:
  - both now validate input and execute tool calls
- Connected agent to real nav service calls (`nav.poi`, `nav.route`) instead of stub response
- Added request/response validation hooks for:
  - envelope
  - agent utterance
  - vehicle command
  - nav route request
  - nav poi request
- Added legacy editable-install compatibility:
  - `setup.py` for older pip environments

### Fixes
- Fixed window percentage parsing bug in planner:
  - `把副驾窗开到30%` now correctly maps to `percent=30`
  - supports both `%` and `％`

### Developer Notes
- `pip install -e .` may fail on old pip versions.
- Fallback command:
  - `pip install -e . --no-use-pep517`

### Known Limitations
- Audio, DMS, and MCP components are still demo/stub implementations.
- Automated tests are not included yet.
- Event bus pub/sub is scaffolded but not integrated across services.
