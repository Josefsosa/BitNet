# CTXP Session-Start Protocol (SPEC-CTXP-LR-001)

**FIRST ACTION EVERY SESSION:** Read `STATE.md` before touching any code.

## Identity

This is the **BitNet** repo — ternary-weight inference engine, Aegis AI server,
and NDGi data pipeline. All work supports the Aegis platform and photonic
ternary research.

## Hard Rules

1. **Read STATE.md first.** No code changes until you have loaded the decision ledger.
2. **Never re-derive settled decisions.** If STATE.md says POS or NEG, that decision is final.
3. **ZERO decisions are open.** Work on them, but do not flip them without evidence + verification.
4. **Anti-goals are load-bearing.** Do not propose work that violates an anti-goal.
5. **Stay under 2K tokens in STATE.md.** Run `python3 .ctxp/ctxp.py status` to check.
   If YELLOW, consider archiving. If RED, archive immediately.
6. **Log new decisions.** Any non-trivial choice gets `python3 .ctxp/ctxp.py decision add "label"`.
7. **Checkpoint before switching context.** Run `python3 .ctxp/ctxp.py checkpoint`.

## Key Paths

| Path | Purpose |
|------|---------|
| `STATE.md` | Decision ledger — the single source of truth |
| `DECISIONS_ARCHIVE.md` | Append-only overflow for resolved decisions |
| `.ctxp/ctxp.py` | CLI tool: status, validate, checkpoint, archive, decision |
| `src/aegis_server.py` | Aegis AI server (v4.2.1) — multi-route API |
| `src/` | Source tree: inference, kernels, tools |
| `gpu/` | CUDA kernels (W2A8 verified) |
| `preset_kernels/` | Pre-built kernel configs |

## Workflow

```
SESSION START → read STATE.md → work → decision add/resolve → checkpoint → SESSION END
```
