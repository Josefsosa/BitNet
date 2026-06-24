# CLAUDE.md — src/ndgi/
## Purpose: NDGi memory graph — continuous-time graph evolution layer.

## Components
- EML operator: Exp-Minus-Log for symbolic regression
- EIG loop: curiosity-driven, maximizes Expected Information Gain
- ndgi_store.cc: B-tree→TST router (trust-gated)

## Router Trust Rules
- TRIT_POS (confirmed ≥1.7x): new writes → TST
- TRIT_NEG (benchmark failed): → B-tree, log failure
- TRIT_ZERO (indeterminate): → B-tree, flag for review

## Schema
- GraphNode: {id: uint64, trit_state: trit_t, embedding: float[128]}
- GraphEdge: {src: uint64, dst: uint64, weight: trit_t, timestamp: uint64}
- No orphan nodes — verify src/dst exist before edge insert

## Test command
cd ../../ && cmake --build build -j20 && \
  ./build/tests/integration/test_ndgi_storage
