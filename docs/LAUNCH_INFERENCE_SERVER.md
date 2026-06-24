# Aegis Model Server — Launch Guide

## OODA Launch Protocol

### Observe
- The Aegis Inference Server lives at `src/aegis_server.py`
- It exposes an OpenAI-compatible API on port 5000
- Routing mode: HYBRID (local Headroom proxy on 8787 first, Gemini cloud fallback)
- Requires `GEMINI_API_KEY` from Google AI Studio

### Orient
- Entry point: `src/launch_aegis_cloud.sh`
- Model: `gemini-2.5-flash` (via Google Generative Language API)
- The server translates OpenAI chat completion format to/from Gemini API format
- No dependency on aegis-cli.py (that lives in `aegis-ternary` project)

### Decide
Launch the server standalone for UI testing against `http://localhost:5000`.

### Act

#### Prerequisites

```bash
export GEMINI_API_KEY="your_google_ai_studio_key"
```

#### Launch (single command)

```bash
bash /home/jsosa/workspace/BitNet/src/launch_aegis_cloud.sh
```

#### Launch (tmux session)

```bash
tmux new-session -d -s aegis-server \
  "export GEMINI_API_KEY='your_key' && bash /home/jsosa/workspace/BitNet/src/launch_aegis_cloud.sh; bash"
tmux attach -t aegis-server
```

#### Verify

```bash
# Health check
curl http://localhost:5000/

# List models
curl http://localhost:5000/v1/models

# Test completion
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

#### Stop

```bash
kill $(lsof -t -i:5000)
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Server status and health |
| GET | `/v1/models` | List available models |
| POST | `/v1/chat/completions` | OpenAI-compatible chat completion |
| POST | `/v1/aegis/classify` | Local 1.58-bit ternary intent classifier |

## Routing Modes

| Mode | Behavior |
|------|----------|
| `local` | All requests proxy through Headroom on port 8787 |
| `cloud` | All requests go direct to Gemini API |
| `hybrid` | Try local first, fall back to cloud on failure |

## Troubleshooting

- **501 Unsupported method**: Server now handles both GET and POST — update the server if you see this.
- **404 model not found**: Model name was updated from `gemini-2.5-flash-preview-09-2025` to `gemini-2.5-flash`.
- **Port 5000 in use**: The launch script auto-kills stale processes. Manual: `fuser -k 5000/tcp`
- **Empty responses**: Check that your `GEMINI_API_KEY` is valid at https://aistudio.google.com
