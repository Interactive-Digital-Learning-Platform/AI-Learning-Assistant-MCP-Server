# Learning Assistant MCP Server

MCP capability server consumed by `AI-Learning-Assistant-Service`.

```
AI Learning Assistant  ──MCP / Streamable HTTP──▶  this server  ──▶  Web Search Provider (Tavily)
```

Design doc: [`dev-docs/web-search-mcp-integration.md`](dev-docs/web-search-mcp-integration.md).

## Capabilities

| Tool | Purpose |
|---|---|
| `web_search` | Ranked public-web results (title, URL, snippet, score) for current/external info. |

## Setup

```bash
uv sync
cp .env.example .env   # then fill MCP_AUTH_TOKEN and TAVILY_API_KEY
```

`MCP_AUTH_TOKEN` must match the assistant's `MCP_SERVER_AUTH_TOKEN`.
`TAVILY_API_KEY` lives only here — never in the assistant.

## Run

```bash
uv run python -m app.main          # Streamable HTTP on :8006 → POST/GET /mcp/
```

Health check: `GET http://localhost:8006/health`.

## Transport

Streamable HTTP (`transport="http"`). Single endpoint, works across independently
deployed services and through the Nginx gateway. Clients authenticate with
`Authorization: Bearer <MCP_AUTH_TOKEN>`.

| Access path | MCP endpoint | Health |
|---|---|---|
| Direct (service-to-service) | `http://<host>:8006/mcp` | `http://<host>:8006/health` |
| Via API gateway | `http://<gateway>:8080/api/mcp/mcp` | `http://<gateway>:8080/api/mcp/health` |

Use the no-trailing-slash `/mcp` form; the server redirects `/mcp/` → `/mcp`.

## Layout

```
app/
  main.py            # composition root: FastMCP + auth + tool registration + /health
  config.py          # pydantic-settings
  logging_config.py  # structured JSON logging
  auth.py            # StaticBearerVerifier (shared-secret, constant-time)
  rate_limit.py      # in-process token bucket
  schemas.py         # WebSearchInput / WebSearchResultItem / WebSearchResponse
  tools/web_search.py # register_web_search(mcp, provider, settings)
  providers/
    base.py          # WebSearchProvider protocol + ProviderResult + errors
    tavily.py        # TavilyProvider
    __init__.py      # get_provider(settings) factory
```

## Adding a tool

1. `app/tools/<name>.py` with `register_<name>(mcp, deps)`.
2. Call it from `app/main.py`.
3. If it wraps an external API, add a provider under `app/providers/`.

No transport/auth/architecture changes required.

## Tests

```bash
uv run pytest                 # unit
uv run pytest -m integration  # hits Tavily; needs TAVILY_API_KEY
uv run ruff check .
```
