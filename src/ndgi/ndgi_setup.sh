#!/bin/bash

# NDGi Local Setup - Initialize your knowledge base so the agent remembers everything
# Usage: ./ndgi_setup.sh ~/BitNet

PROJECT_ROOT="${1:-.}"
NDGI_DIR="$HOME/.ndgi"

echo "=========================================="
echo "NDGi Local Agent Setup"
echo "=========================================="
echo ""

# Create NDGi directory structure
mkdir -p "$NDGI_DIR"
mkdir -p "$PROJECT_ROOT/.ooda"
mkdir -p "$PROJECT_ROOT/docs"

# Initialize TST (Ternary Search Tree) - your persistent knowledge base
if [ -f "ndgi_initial_state.json" ]; then
    cp ndgi_initial_state.json "$NDGI_DIR/tst.json"
    echo "✓ NDGi TST initialized with system state"
    echo "  Location: $NDGI_DIR/tst.json"
else
    echo "⚠ ndgi_initial_state.json not found - creating empty TST"
    echo '{}' > "$NDGI_DIR/tst.json"
fi

# Create OODA session log directory
echo "✓ OODA session directory: $PROJECT_ROOT/.ooda"

# Create lessons.md if it doesn't exist
if [ ! -f "$PROJECT_ROOT/docs/lessons.md" ]; then
    cat > "$PROJECT_ROOT/docs/lessons.md" << 'EOF'
# NDGi Lessons Learned (TRIT_NEG Rejections)

This file records contradictions and failures (TRIT_NEG states) that were rejected
by the validation consensus engine. These are anti-patterns to avoid.

## Format
- **Date**: OODA cycle timestamp
- **What**: The claim or code that was rejected
- **Why**: The contradiction or validation failure
- **Resolved**: Whether this has been fixed

---

EOF
    echo "✓ Lessons file created: $PROJECT_ROOT/docs/lessons.md"
fi

# Create OODA session log template
if [ ! -f "$PROJECT_ROOT/docs/OODA_LOG.md" ]; then
    cat > "$PROJECT_ROOT/docs/OODA_LOG.md" << 'EOF'
# OODA Session Log

Records of Observe-Orient-Decide-Act cycles run through NDGi validation.

## Session Format

```
### Session: YYYYMMDD_HHMMSS

**OBSERVE**: What prior knowledge exists?
- [list prior validated claims]

**ORIENT**: What expertise is needed?
- Domain: [expert role]

**DECIDE**: What is the consensus?
- Agreement: [what all agreed on]
- Conflicts: [contradictions found]
- Trust State: TRIT_POS (+1) / TRIT_ZERO (0) / TRIT_NEG (-1)

**ACT**: What happens next?
- Action: [commit/hold/reject]
- Written to: [NDGi / staging / lessons.md]
- Git status: [committed / pending / rejected]
```

---

EOF
    echo "✓ OODA log template created: $PROJECT_ROOT/docs/OODA_LOG.md"
fi

echo ""
echo "=========================================="
echo "NDGi Knowledge Base Contents:"
echo "=========================================="

python3 << 'PYEOF'
import json
import os

tst_path = os.path.expanduser("~/.ndgi/tst.json")
if os.path.exists(tst_path):
    with open(tst_path, 'r') as f:
        data = json.load(f)
    
    for key, node in data.items():
        trust_map = {1: "✓ TRUSTED", 0: "⚠ UNCERTAIN", -1: "✗ REJECTED"}
        trust_str = trust_map.get(node.get('trit_state', 0), "UNKNOWN")
        value = node.get('value', '')[:50] + ('...' if len(node.get('value', '')) > 50 else '')
        print(f"  {trust_str} | {key}: {value}")
else:
    print("  [Empty - no prior knowledge]")

PYEOF

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Run the OODA Coding Agent:"
echo "   python3 ndgi_coding_agent.py"
echo ""
echo "2. To validate code changes through NDGi:"
echo "   - Write code in your project"
echo "   - Run agent's OODA loop"
echo "   - Agent validates through consensus gates"
echo "   - On TRIT_POS: code is committed automatically"
echo "   - On TRIT_ZERO: code held in staging for review"
echo "   - On TRIT_NEG: contradiction recorded in lessons.md"
echo ""
echo "3. The agent never forgets:"
echo "   - All prior validated knowledge stored in: $NDGI_DIR/tst.json"
echo "   - Each session logged to: $PROJECT_ROOT/.ooda/session_*.md"
echo "   - Failures tracked in: $PROJECT_ROOT/docs/lessons.md"
echo ""
echo "=========================================="
echo "Setup Complete! ✓"
echo "=========================================="
