"""UEBA Endpoint Agent.

A small Python service that runs on company-issued employee machines to
collect security-relevant activity (logon, file, http, etc.) and stream
it to the central UEBA backend at /api/raw-logs/batch using the X-API-Key
issued at enrollment time.

Modules:
- config: load env + CLI args
- state: persist agent_id + api_key (perm 0600)
- buffer: local SQLite queue (durable, idempotent by source_id)
- transport: HTTP client (retry, backoff, batch POST)
- config_client: poll /api/agents/me/config, cache blocklist
- enroll: CLI to enroll with one-time token
- service: main loop (collectors + flusher + heartbeat)
- legal: legal banner shown at startup
- collectors: pluggable event sources
"""

__version__ = "0.1.0"
