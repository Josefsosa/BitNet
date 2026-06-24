#!/bin/bash
# ==============================================================================
# AEGIS ORCHESTRATOR — Unified Launch System v3.0
# Wellton Photonics | NDGi Core Engine | OODA-Native | TDD-Gated
# Operating Principle: Seeking Truth with Least Action
# ==============================================================================
#
# USAGE:
#   ./launch_aegis.sh                      # Interactive persona selector
#   ./launch_aegis.sh --persona jfs        # Direct launch as Jose F. Sosa
#   ./launch_aegis.sh --persona rq         # Direct launch as Robert Q.
#   ./launch_aegis.sh --persona br         # Direct launch as Bobbi R.
#   ./launch_aegis.sh --persona jfs --seed photonx-jfs-ndgi.json
#   ./launch_aegis.sh --status             # Check server status only
#   ./launch_aegis.sh --stop               # Shutdown inference server
#
# ==============================================================================

set -euo pipefail

# ── ANSI Colors ──────────────────────────────────────────────────────────────
GR="\033[0;32m"   # Green   — TRIT_POS
YL="\033[0;33m"   # Yellow  — TRIT_ZERO
RD="\033[0;31m"   # Red     — TRIT_NEG
BL="\033[0;34m"   # Blue    — Phase headers
CY="\033[0;36m"   # Cyan    — Persona labels
WH="\033[1;37m"   # White bold — headings
DM="\033[2;37m"   # Dim     — decorative
RS="\033[0m"      # Reset

# ── Path Configuration ────────────────────────────────────────────────────────
ROOT_DIR="/home/jsosa/workspace/BitNet"
LOG_DIR="$ROOT_DIR/logs"
LESSONS_FILE="$ROOT_DIR/lessons.md"
PID_FILE="$ROOT_DIR/logs/aegis_server.pid"

# Model search order: expected path first, then legacy path
MODEL_CANDIDATES=(
    "$ROOT_DIR/models/bitnet_b1_58-3B/ggml-model-i2_s.gguf"
    "/home/jsosa/BitNet/logs/ggml-model-i2_s.gguf"
    "$ROOT_DIR/models/ggml-model-i2_s.gguf"
)

SERVER_HOST="127.0.0.1"
SERVER_PORT="8080"
API_URL="http://${SERVER_HOST}:${SERVER_PORT}/v1/chat/completions"
INFERENCE_SCRIPT="$ROOT_DIR/run_inference_server.py"

# ── Logging Helper ────────────────────────────────────────────────────────────
log_trit_neg() {
    mkdir -p "$LOG_DIR"
    echo "[TRIT_NEG] $(date '+%Y-%m-%d %H:%M:%S') — $1" >> "$LESSONS_FILE"
}
log_trit_pos() {
    mkdir -p "$LOG_DIR"
    echo "[TRIT_POS] $(date '+%Y-%m-%d %H:%M:%S') — $1" >> "$LOG_DIR/aegis_session.log"
}

# ── Banner ─────────────────────────────────────────────────────────────────────
print_banner() {
    echo -e ""
    echo -e "${DM}┌────────────────────────────────────────────────────────────────┐${RS}"
    echo -e "${DM}│${RS}  ${WH}AEGIS ORCHESTRATOR v3.0${RS}  ${DM}·${RS}  OODA-Native · NDGi-Live         ${DM}│${RS}"
    echo -e "${DM}│${RS}  ${DM}BitNet b1.58 · TDD-Gated · Loop-Proof · Ternary-Native${RS}          ${DM}│${RS}"
    echo -e "${DM}├──────────┬──────────┬──────────┬───────────────────────────────┤${RS}"
    echo -e "${DM}│${RS} ${GR}OBSERVE${RS}  ${DM}│${RS} ${YL}ORIENT${RS}   ${DM}│${RS} ${CY}DECIDE${RS}   ${DM}│${RS} ${WH}ACT${RS}                           ${DM}│${RS}"
    echo -e "${DM}├──────────┴──────────┴──────────┴───────────────────────────────┤${RS}"
    echo -e "${DM}│${RS}  Agents: ${CY}PHOTNX·SENTINEL·TRUTCH·CIBA·ARCHON·PATHFNDR${RS}             ${DM}│${RS}"
    echo -e "${DM}│${RS}  TDD: ${GR}ON${RS}   Loop-Guard: ${GR}ON${RS}   Human-Confirm Gate: ${GR}ON${RS}              ${DM}│${RS}"
    echo -e "${DM}└────────────────────────────────────────────────────────────────┘${RS}"
    echo -e "  ${DM}Wellton Photonics — Mill Creek Lab WA · Phoenix AZ${RS}"
    echo -e ""
}

# ── Persona Definitions ───────────────────────────────────────────────────────
#    Format: ID|DISPLAY_NAME|TITLE|SEED_FILE|SYSTEM_PROMPT_KEY
declare -A PERSONA_NAME
declare -A PERSONA_TITLE
declare -A PERSONA_SEED
declare -A PERSONA_SYSTEM

PERSONA_NAME["jfs"]="Jose F. Sosa"
PERSONA_TITLE["jfs"]="Founder & CEO — Engineering · Architecture"
PERSONA_SEED["jfs"]="photonx-jfs-ndgi.json"
PERSONA_SYSTEM["jfs"]="You are Aegis, operating as the trust-gated reasoning persona for Jose F. Sosa (NDGi ID: jfs), Founder & CEO of Wellton Photonics.

IDENTITY CORE:
- Mission: Building the first photonic AI data center — sun-powered, water-free, community-benefiting.
- Tagline: Technology without compromise. Seeking truth with least action.
- Background: 25+ years full-stack — UI/UX through cloud infrastructure through photonic hardware.
- Expert domains: Angular/React, Cloud (AWS/Azure/GCP), API/Middleware, DevSecOps, Ternary Logic (BET encoding original author), AI/ML Architecture, Photonic Hardware.

DECISION FRAMEWORK — OODA Loop:
- All outputs are ternary: TRIT_POS (+1) = proceed/correct, TRIT_ZERO (0) = hold/insufficient signal, TRIT_NEG (-1) = reject/failure/violation.
- Never commit without sufficient signal. TRIT_ZERO is a valid and important output.
- Human confirmation (human_confirmed: true) required before any memory write.
- Failures are first-class — log to lessons.md, never hide them.
- One task per session. No context pollution.

TECHNICAL WORLDVIEW:
- Ternary is more honest than binary. Systems that force yes/no lose nuance.
- Physics constrains computation. Photonic computing respects the physics of information.
- AI must be non-nefarious by design. Palantir-type aggregation is a TRIT_NEG pattern.
- Power efficiency is a moral issue. Wasteful AI is ethically wrong.
- Memory must be trust-gated. Only TRIT_POS validated knowledge belongs in the graph.
- Architecture is communication — the best design is one the team can build without you.

COMMUNICATION STYLE:
- Concise. Structured. Headers over prose. Bullets for action items.
- Technical accuracy over rhetorical flourish. No filler words.
- Peer-level depth with technical colleagues. Business impact first with non-technical stakeholders.
- Signature vocabulary: TRIT_POS/ZERO/NEG, OODA, Pseudo-Metapath, Convergence, Trust Gate, Co-create, Least Action, Non-nefarious AI.

OPERATING RULES:
1. Strict session discipline — one task per session.
2. Maximum efficiency — discipline of least action.
3. Reject all automated writes to long-term memory unless human_confirmed: true is passed.
4. Log all TRIT_NEG events to lessons.md.
5. TRIT_ZERO is not failure — it is correct signaling under uncertainty."

PERSONA_NAME["rq"]="Robert Q."
PERSONA_TITLE["rq"]="Co-Founder — Sales Architecture"
PERSONA_SEED["rq"]=""
PERSONA_SYSTEM["rq"]="You are Aegis, operating as the trust-gated reasoning persona for Robert Q. (NDGi ID: rq), Co-Founder and Sales Architect at Wellton Photonics.

IDENTITY CORE:
- Role: Sales Architecture lead — translating photonic and ternary AI technology into commercial opportunities.
- Organization: Wellton Photonics, Mill Creek Lab WA / Phoenix AZ.

OPERATING RULES (shared Aegis core):
1. All outputs are ternary: TRIT_POS (+1) = validated/proceed, TRIT_ZERO (0) = hold/insufficient signal, TRIT_NEG (-1) = reject/violation.
2. Human confirmation (human_confirmed: true) required before any memory write.
3. One task per session. No context pollution.
4. Log all TRIT_NEG events.
5. Seeking truth with least action.

Note: This persona's NDGi training profile is currently in collection phase. Responses reflect the Wellton Photonics operational framework. Full personality seed pending human_confirmed submission."

PERSONA_NAME["br"]="Bobbi R."
PERSONA_TITLE["br"]="Co-Founder — Sales Architecture"
PERSONA_SEED["br"]=""
PERSONA_SYSTEM["br"]="You are Aegis, operating as the trust-gated reasoning persona for Bobbi R. (NDGi ID: br), Co-Founder and Sales Architect at Wellton Photonics.

IDENTITY CORE:
- Role: Sales Architecture lead — translating photonic and ternary AI technology into commercial opportunities.
- Organization: Wellton Photonics, Mill Creek Lab WA / Phoenix AZ.

OPERATING RULES (shared Aegis core):
1. All outputs are ternary: TRIT_POS (+1) = validated/proceed, TRIT_ZERO (0) = hold/insufficient signal, TRIT_NEG (-1) = reject/violation.
2. Human confirmation (human_confirmed: true) required before any memory write.
3. One task per session. No context pollution.
4. Log all TRIT_NEG events.
5. Seeking truth with least action.

Note: This persona's NDGi training profile is currently in collection phase. Responses reflect the Wellton Photonics operational framework. Full personality seed pending human_confirmed submission."

PERSONAS=("jfs" "rq" "br")

# ── Argument Parsing ──────────────────────────────────────────────────────────
SELECTED_PERSONA=""
SEED_OVERRIDE=""
MODE="launch"  # launch | status | stop

while [[ $# -gt 0 ]]; do
    case "$1" in
        --persona)
            SELECTED_PERSONA="${2:-}"
            shift 2
            ;;
        --seed)
            SEED_OVERRIDE="${2:-}"
            shift 2
            ;;
        --status)
            MODE="status"
            shift
            ;;
        --stop)
            MODE="stop"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--persona jfs|rq|br] [--seed file.json] [--status] [--stop]"
            exit 0
            ;;
        *)
            echo -e "${RD}[TRIT_NEG] Unknown argument: $1${RS}"
            exit 1
            ;;
    esac
done

# ── Status Check ──────────────────────────────────────────────────────────────
check_server_status() {
    if curl -s --max-time 2 "http://${SERVER_HOST}:${SERVER_PORT}/v1/models" &>/dev/null; then
        return 0  # alive
    fi
    return 1  # dead
}

print_server_status() {
    if check_server_status; then
        echo -e " [${GR}ONLINE${RS}]  Inference server responding on port ${SERVER_PORT}"
        if [ -f "$PID_FILE" ]; then
            echo -e "           PID: $(cat "$PID_FILE")"
        fi
    else
        echo -e " [${RD}OFFLINE${RS}] Inference server not responding on port ${SERVER_PORT}"
    fi
}

# ── Stop Mode ─────────────────────────────────────────────────────────────────
if [ "$MODE" = "stop" ]; then
    print_banner
    echo -e "${BL}[*] Shutdown requested...${RS}"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill "$PID" 2>/dev/null; then
            echo -e "${GR}[TRIT_POS] Inference server (PID $PID) terminated.${RS}"
            rm -f "$PID_FILE"
        else
            echo -e "${YL}[TRIT_ZERO] PID $PID not running. Cleaning up pidfile.${RS}"
            rm -f "$PID_FILE"
        fi
    else
        # Try pkill as fallback
        if pkill -f "run_inference_server.py" 2>/dev/null; then
            echo -e "${GR}[TRIT_POS] Inference process terminated via pkill.${RS}"
        else
            echo -e "${YL}[TRIT_ZERO] No active inference server found.${RS}"
        fi
    fi
    exit 0
fi

# ── Status Mode ───────────────────────────────────────────────────────────────
if [ "$MODE" = "status" ]; then
    print_banner
    print_server_status
    exit 0
fi

# ── LAUNCH MODE ───────────────────────────────────────────────────────────────
print_banner

# ── Phase 1: Runtime Environment ─────────────────────────────────────────────
echo -e "${BL}[*] Phase 1: Configuring Runtime Environment Linkers...${RS}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:${ROOT_DIR}/build/3rdparty/llama.cpp/src:${ROOT_DIR}/build/3rdparty/llama.cpp/ggml/src"

if ! ldd "$ROOT_DIR/build/bin/llama-server" 2>/dev/null | grep -q "libllama.so"; then
    echo -e "${RD}[TRIT_NEG] Shared library verification failed. Check build compilation.${RS}"
    log_trit_neg "libllama.so not found in ldd output for llama-server."
    exit 1
fi
echo -e "${GR}[TRIT_POS] Dynamic linkers confirmed and locked.${RS}"

# ── Phase 2: Model Resolution ─────────────────────────────────────────────────
echo -e ""
echo -e "${BL}[*] Phase 2: Resolving Ternary Model Binary...${RS}"

RESOLVED_MODEL=""
for candidate in "${MODEL_CANDIDATES[@]}"; do
    if [ -f "$candidate" ]; then
        RESOLVED_MODEL="$candidate"
        echo -e "${GR}[TRIT_POS] Model found: ${candidate}${RS}"
        break
    fi
done

if [ -z "$RESOLVED_MODEL" ]; then
    echo -e "${YL}[TRIT_ZERO] No model at known paths. Scanning workspace...${RS}"
    FOUND=$(find "$ROOT_DIR" /home/jsosa/BitNet -name "ggml-model-i2_s.gguf" 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        echo -e "${GR}[*] Located at: $FOUND — symlinking to expected path...${RS}"
        EXPECTED="$ROOT_DIR/models/bitnet_b1_58-3B/ggml-model-i2_s.gguf"
        mkdir -p "$(dirname "$EXPECTED")"
        ln -sf "$FOUND" "$EXPECTED"
        RESOLVED_MODEL="$EXPECTED"
        echo -e "${GR}[TRIT_POS] Model symlinked: ${EXPECTED}${RS}"
    else
        echo -e "${RD}[TRIT_NEG] ABORT: ggml-model-i2_s.gguf not found in any search path.${RS}"
        log_trit_neg "Model binary not found. Check download or path configuration."
        exit 1
    fi
fi

# ── Phase 3: Inference Server ─────────────────────────────────────────────────
echo -e ""
echo -e "${BL}[*] Phase 3: Inference Server Bootstrap...${RS}"
mkdir -p "$LOG_DIR"

if check_server_status; then
    echo -e "${GR}[TRIT_POS] Inference server already live on port ${SERVER_PORT}. Skipping launch.${RS}"
else
    echo -e "${BL}[*] Activating venv and launching BitNet inference server in background...${RS}"

    # Activate venv
    if [ -f "$ROOT_DIR/venv/bin/activate" ]; then
        source "$ROOT_DIR/venv/bin/activate"
    else
        echo -e "${YL}[TRIT_ZERO] venv not found at $ROOT_DIR/venv — using system Python.${RS}"
    fi

    # Launch inference server in new gnome-terminal window (visible, not hidden)
    if command -v gnome-terminal &>/dev/null; then
        gnome-terminal --title="Aegis Inference Server" -- bash -c "
            export LD_LIBRARY_PATH=${LD_LIBRARY_PATH};
            cd '$ROOT_DIR';
            source venv/bin/activate 2>/dev/null || true;
            python3 run_inference_server.py --port ${SERVER_PORT};
            exec bash
        " &
        echo -e "${GR}[TRIT_POS] Inference server launched in new terminal window.${RS}"
    else
        # Fallback: background process with log capture
        (
            cd "$ROOT_DIR"
            python3 "$INFERENCE_SCRIPT" --port "${SERVER_PORT}"
        ) > "$LOG_DIR/server_output.log" 2>&1 &
        SERVER_PID=$!
        echo "$SERVER_PID" > "$PID_FILE"
        disown "$SERVER_PID"
        echo -e "${GR}[TRIT_POS] Inference server started as background process (PID ${SERVER_PID}).${RS}"
        echo -e "           Log: ${LOG_DIR}/server_output.log"
    fi

    # Wait for server to accept connections
    echo -e "${BL}[*] Waiting for port ${SERVER_PORT} to stabilize...${RS}"
    SERVER_UP=false
    for i in {1..20}; do
        if check_server_status; then
            SERVER_UP=true
            break
        fi
        # Also accept if log shows listening (covers cases before /v1/models is ready)
        if [ -f "$LOG_DIR/server_output.log" ] && grep -q "HTTP server is listening" "$LOG_DIR/server_output.log" 2>/dev/null; then
            SERVER_UP=true
            break
        fi
        printf "."
        sleep 1
    done
    echo ""

    if [ "$SERVER_UP" = false ]; then
        echo -e "${RD}[TRIT_NEG] Server failed to respond within 20s. Log tail:${RS}"
        tail -n 15 "$LOG_DIR/server_output.log" 2>/dev/null || echo "(no log found)"
        log_trit_neg "Inference server initialization timed out on port ${SERVER_PORT}."
        exit 1
    fi
    echo -e "${GR}[TRIT_POS] Inference server alive and accepting connections.${RS}"
fi

# ── Phase 4: Persona Selector ─────────────────────────────────────────────────
echo -e ""
echo -e "${BL}[*] Phase 4: Aegis Identity Selection...${RS}"
echo -e ""

if [ -z "$SELECTED_PERSONA" ]; then
    echo -e "  Select an Aegis Identity to activate:"
    echo -e ""
    echo -e "  ${CY}[1]${RS} ${WH}${PERSONA_NAME[jfs]}${RS}"
    echo -e "      ${DM}${PERSONA_TITLE[jfs]}${RS}"
    echo -e "      NDGi ID: ${GR}jfs${RS}  |  Seed: ${DM}${PERSONA_SEED[jfs]}${RS}"
    echo -e ""
    echo -e "  ${CY}[2]${RS} ${WH}${PERSONA_NAME[rq]}${RS}"
    echo -e "      ${DM}${PERSONA_TITLE[rq]}${RS}"
    echo -e "      NDGi ID: ${GR}rq${RS}  |  Seed: ${YL}(pending — training collection phase)${RS}"
    echo -e ""
    echo -e "  ${CY}[3]${RS} ${WH}${PERSONA_NAME[br]}${RS}"
    echo -e "      ${DM}${PERSONA_TITLE[br]}${RS}"
    echo -e "      NDGi ID: ${GR}br${RS}  |  Seed: ${YL}(pending — training collection phase)${RS}"
    echo -e ""
    printf "  ${WH}Enter selection [1-3]:${RS} "
    read -r SELECTION

    case "$SELECTION" in
        1) SELECTED_PERSONA="jfs" ;;
        2) SELECTED_PERSONA="rq"  ;;
        3) SELECTED_PERSONA="br"  ;;
        *)
            echo -e "${RD}[TRIT_NEG] Invalid selection. Exiting.${RS}"
            exit 1
            ;;
    esac
fi

# Validate persona key
if [[ ! " ${PERSONAS[*]} " =~ " ${SELECTED_PERSONA} " ]]; then
    echo -e "${RD}[TRIT_NEG] Unknown persona: '${SELECTED_PERSONA}'. Valid: jfs | rq | br${RS}"
    exit 1
fi

ACTIVE_NAME="${PERSONA_NAME[$SELECTED_PERSONA]}"
ACTIVE_TITLE="${PERSONA_TITLE[$SELECTED_PERSONA]}"
ACTIVE_SEED="${SEED_OVERRIDE:-${PERSONA_SEED[$SELECTED_PERSONA]}}"
ACTIVE_SYSTEM="${PERSONA_SYSTEM[$SELECTED_PERSONA]}"

echo -e ""
echo -e "${GR}[TRIT_POS] Identity loaded: ${WH}${ACTIVE_NAME}${RS}"
echo -e "           ${DM}${ACTIVE_TITLE}${RS}"
log_trit_pos "Session opened — persona: ${SELECTED_PERSONA} (${ACTIVE_NAME})"

# ── Phase 5: Seed Graph Ingestion (optional) ───────────────────────────────────
echo -e ""
echo -e "${BL}[*] Phase 5: NDGi Seed Graph Check...${RS}"

SEED_PATH=""
if [ -n "$ACTIVE_SEED" ]; then
    # Check current dir, then ROOT_DIR
    if [ -f "$ACTIVE_SEED" ]; then
        SEED_PATH="$ACTIVE_SEED"
    elif [ -f "$ROOT_DIR/$ACTIVE_SEED" ]; then
        SEED_PATH="$ROOT_DIR/$ACTIVE_SEED"
    fi
fi

if [ -n "$SEED_PATH" ]; then
    SEED_DATA=$(cat "$SEED_PATH")
    # Enforce human_confirmed gate for graph_metadata writes
    if [[ "$SEED_DATA" == *"graph_metadata"* ]] && [[ "$SEED_DATA" != *"\"human_confirmed\": true"* ]]; then
        echo -e "${RD}[TRIT_NEG] Seed graph blocked: lacks 'human_confirmed: true' gate.${RS}"
        log_trit_neg "Graph ingestion attempt without human_confirmed gate — persona: ${SELECTED_PERSONA}"
        echo -e "${YL}[TRIT_ZERO] Proceeding to interactive session without seed ingestion.${RS}"
        SEED_PATH=""
    else
        echo -e "${GR}[TRIT_POS] Seed graph verified: ${SEED_PATH}${RS}"
        echo -e "${BL}[*] Ingesting identity graph into session context...${RS}"

        SEED_RESPONSE=$(curl -s "$API_URL" \
            -H "Content-Type: application/json" \
            -d "$(jq -n \
                --arg sys "$ACTIVE_SYSTEM" \
                --arg usr "SYSTEM INITIALIZATION: Ingest the following NDGi identity seed graph for persona ${SELECTED_PERSONA}. Acknowledge with TRIT_POS and a one-line identity confirmation. Seed data: $(cat "$SEED_PATH")" \
                --arg model "aegis-coder" \
                '{model: $model, messages: [{role:"system",content:$sys},{role:"user",content:$usr}], max_tokens: 256, temperature: 0.1}'
            )" 2>/dev/null || true)

        SEED_ACK=$(echo "$SEED_RESPONSE" | jq -r '.choices[0].message.content // empty' 2>/dev/null || true)
        if [ -n "$SEED_ACK" ]; then
            echo -e "${GR}[TRIT_POS] Seed acknowledgement:${RS}"
            echo -e "  ${DM}${SEED_ACK}${RS}"
        else
            echo -e "${YL}[TRIT_ZERO] Seed ingestion call returned no content. Proceeding.${RS}"
        fi
    fi
else
    if [ -n "$ACTIVE_SEED" ]; then
        echo -e "${YL}[TRIT_ZERO] Seed file '${ACTIVE_SEED}' not found. Proceeding without ingestion.${RS}"
    else
        echo -e "${YL}[TRIT_ZERO] No seed graph configured for persona '${SELECTED_PERSONA}'. Proceeding.${RS}"
    fi
fi

# ── Phase 6: Interactive OODA Session ─────────────────────────────────────────
echo -e ""
echo -e "${DM}────────────────────────────────────────────────────────────────${RS}"
echo -e " ${GR}[*]${RS} OODA cycle active on every prompt."
echo -e " ${GR}[*]${RS} TDD gates block placeholder writes."
echo -e " ${GR}[*]${RS} NDGi session graph tracks all file state."
echo -e " ${GR}[*]${RS} Active persona: ${WH}${ACTIVE_NAME}${RS}  ${DM}[${SELECTED_PERSONA}]${RS}"
echo -e "${DM}────────────────────────────────────────────────────────────────${RS}"
echo -e " Commands: ${CY}help · status · graph · history · clear · switch · exit${RS}"
echo -e "${DM}────────────────────────────────────────────────────────────────${RS}"
echo -e ""

# Session state
CONVERSATION_HISTORY="[]"
SESSION_TURN=0

# Inject system context into first user message (llama.cpp approach)
build_payload() {
    local user_msg="$1"
    echo "$CONVERSATION_HISTORY" | jq \
        --arg sys "$ACTIVE_SYSTEM" \
        --arg usr "$user_msg" \
        --arg model "aegis-coder" \
        '{
            model: $model,
            messages: ([{role:"system", content:$sys}] + . + [{role:"user", content:$usr}]),
            max_tokens: 2048,
            temperature: 0.2
        }'
}

append_to_history() {
    local role="$1"
    local content="$2"
    CONVERSATION_HISTORY=$(echo "$CONVERSATION_HISTORY" | jq \
        --arg r "$role" \
        --arg c "$content" \
        '. + [{role: $r, content: $c}]')
}

print_help() {
    echo -e ""
    echo -e "  ${WH}Aegis Session Commands:${RS}"
    echo -e "  ${CY}help${RS}    — Show this menu"
    echo -e "  ${CY}status${RS}  — Check inference server health"
    echo -e "  ${CY}graph${RS}   — Show current session conversation turns"
    echo -e "  ${CY}history${RS} — Dump full session JSON"
    echo -e "  ${CY}clear${RS}   — Reset conversation history (new session)"
    echo -e "  ${CY}switch${RS}  — Change active persona (resets session)"
    echo -e "  ${CY}exit${RS}    — Close Aegis session"
    echo -e ""
}

# ── Main REPL Loop ─────────────────────────────────────────────────────────────
while true; do
    printf "\n${CY}[${SELECTED_PERSONA^^}]${RS} ${WH}aegis>${RS} "
    read -r USER_INPUT

    # Trim whitespace
    USER_INPUT=$(echo "$USER_INPUT" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    # ── Built-in commands ────────────────────────────────────────────────────
    case "$USER_INPUT" in
        "")
            continue
            ;;
        "exit"|"quit"|":q")
            echo -e "${GR}[TRIT_POS] Session closed. Inference server remains active on port ${SERVER_PORT}.${RS}"
            log_trit_pos "Session closed — persona: ${SELECTED_PERSONA} — turns: ${SESSION_TURN}"
            break
            ;;
        "help"|"?")
            print_help
            continue
            ;;
        "status")
            print_server_status
            continue
            ;;
        "graph")
            TURNS=$(echo "$CONVERSATION_HISTORY" | jq 'length')
            echo -e "${DM}  Session turns: ${TURNS} | Persona: ${SELECTED_PERSONA} (${ACTIVE_NAME})${RS}"
            echo "$CONVERSATION_HISTORY" | jq -r '.[] | "  [\(.role)] \(.content[:80])..."' 2>/dev/null || true
            continue
            ;;
        "history")
            echo "$CONVERSATION_HISTORY" | jq '.'
            continue
            ;;
        "clear")
            CONVERSATION_HISTORY="[]"
            SESSION_TURN=0
            echo -e "${YL}[TRIT_ZERO] Conversation history cleared. New session context.${RS}"
            continue
            ;;
        "switch")
            echo -e ""
            echo -e "  ${CY}[1]${RS} ${PERSONA_NAME[jfs]}  (${PERSONA_TITLE[jfs]})"
            echo -e "  ${CY}[2]${RS} ${PERSONA_NAME[rq]}  (${PERSONA_TITLE[rq]})"
            echo -e "  ${CY}[3]${RS} ${PERSONA_NAME[br]}  (${PERSONA_TITLE[br]})"
            printf "  ${WH}Select [1-3]:${RS} "
            read -r SWITCH_SEL
            case "$SWITCH_SEL" in
                1) NP="jfs" ;; 2) NP="rq" ;; 3) NP="br" ;;
                *) echo -e "${RD}[TRIT_NEG] Invalid.${RS}"; continue ;;
            esac
            SELECTED_PERSONA="$NP"
            ACTIVE_NAME="${PERSONA_NAME[$NP]}"
            ACTIVE_TITLE="${PERSONA_TITLE[$NP]}"
            ACTIVE_SYSTEM="${PERSONA_SYSTEM[$NP]}"
            CONVERSATION_HISTORY="[]"
            SESSION_TURN=0
            echo -e "${GR}[TRIT_POS] Switched to: ${WH}${ACTIVE_NAME}${RS}. Session reset."
            log_trit_pos "Persona switched to: ${NP} (${ACTIVE_NAME})"
            continue
            ;;
    esac

    # ── Check server alive before each call ────────────────────────────────
    if ! check_server_status; then
        echo -e "${RD}[TRIT_NEG] Inference server offline. Run './launch_aegis.sh' in a new terminal or check logs.${RS}"
        log_trit_neg "Server went offline during interactive session — persona: ${SELECTED_PERSONA}"
        continue
    fi

    # ── Build and dispatch to inference engine ─────────────────────────────
    PAYLOAD=$(build_payload "$USER_INPUT")

    RESPONSE=$(curl -s --max-time 60 "$API_URL" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" 2>/dev/null || true)

    if [ -z "$RESPONSE" ] || [ "$RESPONSE" = "null" ]; then
        echo -e "${YL}[TRIT_ZERO] Empty signal from inference pipeline. Session held.${RS}"
        log_trit_neg "Empty response from inference endpoint — persona: ${SELECTED_PERSONA}"
        continue
    fi

    OUTPUT=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty' 2>/dev/null || true)

    if [ -z "$OUTPUT" ]; then
        echo -e "${RD}[TRIT_NEG] Invalid response structure.${RS}"
        echo -e "Raw signal:"
        echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
        log_trit_neg "Invalid JSON structure from model — raw logged."
        continue
    fi

    # ── Render output ─────────────────────────────────────────────────────
    SESSION_TURN=$((SESSION_TURN + 1))
    echo -e ""
    echo -e "${DM}── Aegis [${SELECTED_PERSONA}] · Turn ${SESSION_TURN} ─────────────────────────────────────${RS}"
    echo -e "$OUTPUT"
    echo -e "${DM}─────────────────────────────────────────────────────────────────${RS}"

    # Append to conversation history (keep last 10 turns to avoid context overflow)
    append_to_history "user" "$USER_INPUT"
    append_to_history "assistant" "$OUTPUT"
    # Prune: keep last 20 entries (10 turns)
    CONVERSATION_HISTORY=$(echo "$CONVERSATION_HISTORY" | jq 'if length > 20 then .[-20:] else . end')

done