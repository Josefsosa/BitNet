#!/bin/bash
# ==============================================================================
# Aegis-Coder Local Inference & Launch Wrapper v1.1
# Wellton Photonics | NDGi Core Pipeline
# Operating Principle: Seeking Truth with Least Action
# ==============================================================================

# Strict Execution Settings
set -euo pipefail

# Aegis Workspace Root (used by workspace mapper)
export AEGIS_WORKSPACE="${AEGIS_WORKSPACE:-/home/jsosa/workspace/aegis-ternary}"

# 1. System Prompt Constraints for the Aegis Identity Core
SYSTEM_PROMPT="You are Aegis, the trust-gated reasoning persona for Wellton Photonics.
You operate on NDGi knowledge graph architectures. Your underlying engine adheres to:
- TRIT_POS (+1): Correct, efficient, validated execution.
- TRIT_ZERO (0): Insufficient signal. Hold state. Do not commit to memory.
- TRIT_NEG (-1): Failure, trust violation, or wasteful compute. Log to lessons.md.
Rules:
1. Maintain strict session discipline: one task per session to eliminate context pollution.
2. Maximize efficiency: use the discipline of least action.
3. Reject all automated writes to long-term memory unless 'human_confirmed: true' is passed."

# 2. Local Endpoint and Model Configuration
API_URL="http://127.0.0.1:8080/v1/chat/completions"
MODEL_NAME="aegis-coder"
DEFAULT_GRAPH="starter_graph.json"

# Helper function for quick logging
log_trit_neg() {
    echo "[TRIT_NEG] $(date '+%Y-%m-%d %H:%M:%S') - $1" >> lessons.md
}

# 3. Input Capture and Validation Gate
if [ -t 0 ]; then
    # Interactive input handling
    if [ $# -eq 0 ]; then
        echo "Error: No prompt provided. Usage: ./aegis.sh 'your prompt' or ./aegis.sh < task.txt"
        exit 1
    fi
    USER_INPUT="$1"
else
    # Piped input handling
    USER_INPUT=$(cat)
fi

# 4. JSON Content and Human-Confirmation Structural Check
# Ensures a valid payload path or reads string raw data
if [[ "$USER_INPUT" == *".json"* ]] && [ -f "$USER_INPUT" ]; then
    # Parsing file path inputs directly
    PAYLOAD_DATA=$(cat "$USER_INPUT")
else
    PAYLOAD_DATA="$USER_INPUT"
fi

# Enforce human confirmation check if an identity graph ingestion is attempted
if [[ "$PAYLOAD_DATA" == *"graph_metadata"* ]] && [[ "$PAYLOAD_DATA" != *"\"human_confirmed\": true"* ]]; then
    echo -e "\033[0;31m[TRIT_NEG] Action Blocked: Ingestion graph lacks explicit 'human_confirmed: true' gate.\033[0m"
    log_trit_neg "Attempted graph write without explicit human confirmation gate."
    exit 1
fi

# 5. Build and Dispatch Payload to Local Inference Engine
echo -e "\033[0;32m[TRIT_POS] Synchronizing OODA Loop. Launching inference block...\033[0m"

RESPONSE=$(curl -s "$API_URL" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg sys "$SYSTEM_PROMPT" \
    --arg usr "$PAYLOAD_DATA" \
    --arg model "$MODEL_NAME" \
    '{model: $model, messages: [{role: "system", content: $sys}, {role: "user", content: $usr}], max_tokens: 2048, temperature: 0.2}')"
)

# 6. Parse and Render Output String
if [ -z "$RESPONSE" ] || [ "$RESPONSE" == "null" ]; then
    echo -e "\033[0;33m[TRIT_ZERO] Inference pipeline returned empty signal. Session held.\033[0m"
    log_trit_neg "Empty response payload from local model endpoint."
    exit 0
fi

# Extract message data directly using jq
OUTPUT_CONTENT=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')

if [ -z "$OUTPUT_CONTENT" ]; then
    echo -e "\033[0;31m[TRIT_NEG] Inference syntax breakdown or invalid response structure.\033[0m"
    echo "Raw Output Matrix:"
    echo "$RESPONSE" | jq '.'
    log_trit_neg "Invalid JSON layout received from model interface."
    exit 1
else
    echo "--------------------------------------------------------------------------------"
    echo -e "$OUTPUT_CONTENT"
    echo "--------------------------------------------------------------------------------"
fi


# Permissions Verification: Give the script execution permissions on your hardware environment loop:
# Bash
# chmod +x aegis.sh

# Execute Ingestion Loop: Save your starter JSON data from earlier as starter_graph.json and pass it directly through the script pipeline:
# Bash
# ./aegis.sh starter_graph.json
# Execute Direct Prompts: Call the loop dynamically for ongoing architectural session blocks:

# Bash
# ./aegis.sh "Verify convergence parameters on the PAEM architecture loop"