# STATE.md — CTXP Decision Ledger

## Phases

| Track | Phase | Status |
|-------|-------|--------|
| DATA_ENGINEERING | NEAR_REAL_TIME_NDGI_FLOW | Active |
| GENAI_ENGINEERING | AGENTIC_MCP_INTEGRATION_ONLINE | Active |

## Decisions

| ID | Label | State | Detail |
|----|-------|-------|--------|
| 1 | W2A8 CUDA kernel | POS | 11-13x over BF16 verified on RTX m18 R1 [commit 253c2e09] |
| 2 | Aegis server v4.2.1 | POS | Multi-route AI API working, heal_cli dynamic routing stable |


## Anti-Goals

- No microservice refactor — monolith-first until scale demands it
- No Headroom removal — metric is load-bearing for kernel selection
- No Protocol version bump without full regression pass

## File Manifest

| File | Role |
|------|------|
| `src/aegis_server.py` | Aegis AI server — multi-route API gateway |
| `src/tools/ggml-bitnet-lut.cpp` | Ternary LUT kernel implementation |
| `src/tools/ggml-bitnet-mad.cpp` | Ternary MAD kernel implementation |
| `gpu/` | CUDA kernels — W2A8 verified |
| `preset_kernels/` | Pre-built kernel configurations |
| `src/tools/heal_cli_routes_dynamic.py` | Dynamic CLI route healing |
| `src/aegis_local_inference_server.py` | Local inference server |
