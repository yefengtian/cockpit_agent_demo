# Release Notes

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
