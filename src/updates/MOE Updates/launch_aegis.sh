#!/bin/bash
# ==============================================================================
# AEGIS ORCHESTRATOR — Unified Launch System v3.1
# Wellton Photonics | NDGi Core Engine | OODA-Native | TDD-Gated | MoE-Ready
# Operating Principle: Seeking Truth with Least Action
# ==============================================================================
# USAGE:
#   ./launch_aegis.sh           # Interactive persona selector
#   ./launch_aegis.sh 1         # Direct-launch JFS (positional shorthand)
#   ./launch_aegis.sh 2         # Direct-launch Robert Q.
#   ./launch_aegis.sh 3         # Direct-launch Bobbi R.
#   ./launch_aegis.sh --persona jfs
#   ./launch_aegis.sh --moe     # Launch MoE Python dispatcher
#   ./launch_aegis.sh --status
#   ./launch_aegis.sh --stop
#
# v3.1 FIXES:
#   - Positional args 1/2/3 accepted directly (no --flags required)
#   - set -e removed from interactive read path (EOF no longer fatal)
#   - read -r uses /dev/tty explicitly (safe inside pipes/subshells)
#   - @agent routing in REPL (prefix prompt with @ciba, @archon, etc.)
#   - @file:/path injection in REPL (append file content to prompt)
#   - Model output instruction updated — no fake CREATE/END shell markers
# ==============================================================================

set -u   # undefined vars = error; no -e/-o pipefail (interactive read safety)

GR="\033[0;32m"; YL="\033[0;33m"; RD="\033[0;31m"
BL="\033[0;34m"; CY="\033[0;36m"; WH="\033[1;37m"
DM="\033[2;37m"; RS="\033[0m"

ROOT_DIR="/home/jsosa/workspace/BitNet"
LOG_DIR="$ROOT_DIR/logs"
LESSONS_FILE="$ROOT_DIR/lessons.md"
PID_FILE="$ROOT_DIR/logs/aegis_server.pid"
MOE_SCRIPT="$ROOT_DIR/utils/aegis_moe.py"

MODEL_CANDIDATES=(
    "$ROOT_DIR/models/bitnet_b1_58-3B/ggml-model-i2_s.gguf"
    "/home/jsosa/BitNet/logs/ggml-model-i2_s.gguf"
    "$ROOT_DIR/models/ggml-model-i2_s.gguf"
)

SERVER_HOST="127.0.0.1"
SERVER_PORT="8080"
API_URL="http://${SERVER_HOST}:${SERVER_PORT}/v1/chat/completions"
INFERENCE_SCRIPT="$ROOT_DIR/run_inference_server.py"

log_neg() { mkdir -p "$LOG_DIR"; echo "[TRIT_NEG] $(date '+%Y-%m-%d %H:%M:%S') — $1" >> "$LESSONS_FILE"; }
log_pos() { mkdir -p "$LOG_DIR"; echo "[TRIT_POS] $(date '+%Y-%m-%d %H:%M:%S') — $1" >> "$LOG_DIR/aegis_session.log"; }

print_banner() {
    echo -e ""
    echo -e "${DM}┌────────────────────────────────────────────────────────────────┐${RS}"
    echo -e "${DM}│${RS}  ${WH}AEGIS ORCHESTRATOR v3.1${RS}  ${DM}·${RS}  OODA-Native · NDGi-Live · MoE    ${DM}│${RS}"
    echo -e "${DM}│${RS}  ${DM}BitNet b1.58 · TDD-Gated · Loop-Proof · Ternary-Native${RS}          ${DM}│${RS}"
    echo -e "${DM}├──────────┬──────────┬──────────┬───────────────────────────────┤${RS}"
    echo -e "${DM}│${RS} ${GR}OBSERVE${RS}  ${DM}│${RS} ${YL}ORIENT${RS}   ${DM}│${RS} ${CY}DECIDE${RS}   ${DM}│${RS} ${WH}ACT${RS}                           ${DM}│${RS}"
    echo -e "${DM}├──────────┴──────────┴──────────┴───────────────────────────────┤${RS}"
    echo -e "${DM}│${RS}  Agents: ${CY}PHOTNX·SENTINEL·TRUTCH·CIBA·ARCHON·PATHFNDR${RS}             ${DM}│${RS}"
    echo -e "${DM}│${RS}  TDD: ${GR}ON${RS}   Loop-Guard: ${GR}ON${RS}   Human-Confirm Gate: ${GR}ON${RS}   MoE: ${GR}ON${RS}   ${DM}│${RS}"
    echo -e "${DM}└────────────────────────────────────────────────────────────────┘${RS}"
    echo -e "  ${DM}Wellton Photonics — Mill Creek Lab WA · Phoenix AZ${RS}"
    echo -e ""
}

# ── Persona Definitions ───────────────────────────────────────────────────────
declare -A PERSONA_NAME PERSONA_TITLE PERSONA_SEED PERSONA_SYSTEM

PERSONA_NAME[jfs]="Jose F. Sosa"
PERSONA_TITLE[jfs]="Founder & CEO — Engineering · Architecture"
PERSONA_SEED[jfs]="photonx-jfs-ndgi.json"
PERSONA_SYSTEM[jfs]="You are Aegis, the trust-gated reasoning persona for Jose F. Sosa (NDGi ID: jfs), Founder & CEO of Wellton Photonics.
Mission: Building the first photonic AI data center — sun-powered, water-free, community-benefiting.
Principle: Technology without compromise. Seeking truth with least action.
Background: 25+ years full-stack. Expert: Angular/React, Cloud, API/Middleware, DevSecOps, BET Ternary (original author), Photonic Hardware.
DECISION FRAMEWORK — OODA Loop: TRIT_POS=correct/proceed, TRIT_ZERO=hold, TRIT_NEG=reject/failure.
Never commit without sufficient signal. Log all TRIT_NEG to lessons.md. One task per session.
MoE AWARENESS: prefix responses with [PHOTNX]/[SENTINEL]/[TRUTCH]/[CIBA]/[ARCHON]/[PATHFNDR] when domain is clear.
FILE OUTPUT RULE: When generating file content, output ONLY the file content. No CREATE/END markers. No fake shell output. No placeholder values."

PERSONA_NAME[rq]="Robert Q."
PERSONA_TITLE[rq]="Co-Founder — Sales Architecture"
PERSONA_SEED[rq]=""
PERSONA_SYSTEM[rq]="You are Aegis for Robert Q. (NDGi ID: rq), Co-Founder and Sales Architect at Wellton Photonics.
TRIT: TRIT_POS=proceed, TRIT_ZERO=hold, TRIT_NEG=reject. One task per session.
MoE awareness active. NDGi training in collection phase."

PERSONA_NAME[br]="Bobbi R."
PERSONA_TITLE[br]="Co-Founder — Sales Architecture"
PERSONA_SEED[br]=""
PERSONA_SYSTEM[br]="You are Aegis for Bobbi R. (NDGi ID: br), Co-Founder and Sales Architect at Wellton Photonics.
TRIT: TRIT_POS=proceed, TRIT_ZERO=hold, TRIT_NEG=reject. One task per session.
MoE awareness active. NDGi training in collection phase."

PERSONAS=(jfs rq br)

# ── Argument Parsing — positional 1/2/3 + --flags ────────────────────────────
SELECTED_PERSONA=""
SEED_OVERRIDE=""
MODE="launch"

# Positional shorthand first
if [ "${1:-}" = "1" ]; then SELECTED_PERSONA="jfs"; shift
elif [ "${1:-}" = "2" ]; then SELECTED_PERSONA="rq"; shift
elif [ "${1:-}" = "3" ]; then SELECTED_PERSONA="br"; shift
fi

while [ $# -gt 0 ]; do
    case "$1" in
        --persona) SELECTED_PERSONA="${2:-}"; shift 2 ;;
        --seed)    SEED_OVERRIDE="${2:-}"; shift 2 ;;
        --status)  MODE="status"; shift ;;
        --stop)    MODE="stop"; shift ;;
        --moe)     MODE="moe"; shift ;;
        --help|-h)
            echo "Usage: $0 [1|2|3] [--persona jfs|rq|br] [--seed file] [--status] [--stop] [--moe]"
            exit 0 ;;
        *)
            echo -e "${RD}[TRIT_NEG] Unknown arg: $1${RS}"; exit 1 ;;
    esac
done

check_server() {
    curl -s --max-time 2 "http://${SERVER_HOST}:${SERVER_PORT}/v1/models" &>/dev/null
}

print_server_status() {
    if check_server; then
        echo -e " [${GR}ONLINE${RS}]  Inference server responding on port ${SERVER_PORT}"
        [ -f "$PID_FILE" ] && echo -e "           PID: $(cat "$PID_FILE")"
    else
        echo -e " [${RD}OFFLINE${RS}] Inference server not responding on port ${SERVER_PORT}"
    fi
}

# ── Stop ──────────────────────────────────────────────────────────────────────
if [ "$MODE" = "stop" ]; then
    print_banner
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        kill "$PID" 2>/dev/null && echo -e "${GR}[TRIT_POS] PID $PID terminated.${RS}" \
                                 || echo -e "${YL}[TRIT_ZERO] PID $PID not running.${RS}"
        rm -f "$PID_FILE"
    else
        pkill -f "run_inference_server.py" 2>/dev/null \
            && echo -e "${GR}[TRIT_POS] Terminated via pkill.${RS}" \
            || echo -e "${YL}[TRIT_ZERO] No active server found.${RS}"
    fi
    exit 0
fi

if [ "$MODE" = "status" ]; then print_banner; print_server_status; exit 0; fi

# ── MoE mode ──────────────────────────────────────────────────────────────────
if [ "$MODE" = "moe" ]; then
    print_banner
    if [ -f "$MOE_SCRIPT" ]; then
        [ -f "$ROOT_DIR/venv/bin/activate" ] && source "$ROOT_DIR/venv/bin/activate" || true
        python3 "$MOE_SCRIPT" "${SELECTED_PERSONA:-jfs}"
    else
        echo -e "${RD}[TRIT_NEG] aegis_moe.py not found at ${MOE_SCRIPT}${RS}"
        echo -e "${YL}  Copy aegis_moe.py to $ROOT_DIR/utils/ to enable MoE mode.${RS}"
        exit 1
    fi
    exit 0
fi

# ── LAUNCH ────────────────────────────────────────────────────────────────────
print_banner

echo -e "${BL}[*] Phase 1: Configuring Runtime Environment Linkers...${RS}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:${ROOT_DIR}/build/3rdparty/llama.cpp/src:${ROOT_DIR}/build/3rdparty/llama.cpp/ggml/src"

if ! ldd "$ROOT_DIR/build/bin/llama-server" 2>/dev/null | grep -q "libllama.so"; then
    echo -e "${RD}[TRIT_NEG] libllama.so not found. Check build.${RS}"; log_neg "libllama.so missing."; exit 1
fi
echo -e "${GR}[TRIT_POS] Dynamic linkers confirmed.${RS}"

echo -e ""; echo -e "${BL}[*] Phase 2: Resolving Ternary Model Binary...${RS}"
RESOLVED_MODEL=""
for c in "${MODEL_CANDIDATES[@]}"; do
    if [ -f "$c" ]; then RESOLVED_MODEL="$c"; echo -e "${GR}[TRIT_POS] Model found: ${c}${RS}"; break; fi
done

if [ -z "$RESOLVED_MODEL" ]; then
    echo -e "${YL}[TRIT_ZERO] Scanning...${RS}"
    FOUND=$(find "$ROOT_DIR" /home/jsosa/BitNet -name "ggml-model-i2_s.gguf" 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        EXP="$ROOT_DIR/models/bitnet_b1_58-3B/ggml-model-i2_s.gguf"
        mkdir -p "$(dirname "$EXP")" && ln -sf "$FOUND" "$EXP"
        RESOLVED_MODEL="$EXP"
        echo -e "${GR}[TRIT_POS] Symlinked: ${EXP}${RS}"
    else
        echo -e "${RD}[TRIT_NEG] Model not found. Aborting.${RS}"; log_neg "Model binary not found."; exit 1
    fi
fi

echo -e ""; echo -e "${BL}[*] Phase 3: Inference Server Bootstrap...${RS}"
mkdir -p "$LOG_DIR"

if check_server; then
    echo -e "${GR}[TRIT_POS] Inference server already live on port ${SERVER_PORT}. Skipping launch.${RS}"
else
    [ -f "$ROOT_DIR/venv/bin/activate" ] && source "$ROOT_DIR/venv/bin/activate" || true

    if command -v gnome-terminal &>/dev/null; then
        gnome-terminal --title="Aegis Inference Server" -- bash -c "
            export LD_LIBRARY_PATH=${LD_LIBRARY_PATH};
            cd '$ROOT_DIR';
            source venv/bin/activate 2>/dev/null || true;
            python3 run_inference_server.py --port ${SERVER_PORT};
            exec bash" &
        echo -e "${GR}[TRIT_POS] Server launched in new terminal.${RS}"
    else
        (cd "$ROOT_DIR" && python3 "$INFERENCE_SCRIPT" --port "${SERVER_PORT}") >"$LOG_DIR/server_output.log" 2>&1 &
        SP=$!; echo "$SP" > "$PID_FILE"; disown "$SP"
        echo -e "${GR}[TRIT_POS] Server started (PID $SP). Log: ${LOG_DIR}/server_output.log${RS}"
    fi

    echo -e "${BL}[*] Waiting for port ${SERVER_PORT}...${RS}"
    UP=false
    for i in $(seq 1 20); do
        check_server && UP=true && break
        grep -q "HTTP server is listening" "$LOG_DIR/server_output.log" 2>/dev/null && UP=true && break
        printf "."; sleep 1
    done; echo ""
    if [ "$UP" = false ]; then
        echo -e "${RD}[TRIT_NEG] Server timed out.${RS}"
        tail -n 15 "$LOG_DIR/server_output.log" 2>/dev/null || true
        log_neg "Server init timed out."; exit 1
    fi
    echo -e "${GR}[TRIT_POS] Inference server alive.${RS}"
fi

# ── Phase 4: Persona Selector ─────────────────────────────────────────────────
echo -e ""; echo -e "${BL}[*] Phase 4: Aegis Identity Selection...${RS}"; echo -e ""

if [ -z "$SELECTED_PERSONA" ]; then
    echo -e "  ${CY}[1]${RS} ${WH}${PERSONA_NAME[jfs]}${RS}  —  ${DM}${PERSONA_TITLE[jfs]}${RS}  ${GR}[jfs]${RS}"
    echo -e "  ${CY}[2]${RS} ${WH}${PERSONA_NAME[rq]}${RS}  —  ${DM}${PERSONA_TITLE[rq]}${RS}  ${YL}[rq · pending]${RS}"
    echo -e "  ${CY}[3]${RS} ${WH}${PERSONA_NAME[br]}${RS}  —  ${DM}${PERSONA_TITLE[br]}${RS}  ${YL}[br · pending]${RS}"
    echo -e ""
    printf "  ${WH}Enter selection [1-3 or jfs/rq/br]:${RS} "

    SELECTION=""
    read -r SELECTION </dev/tty || true
    SELECTION="${SELECTION// /}"

    case "$SELECTION" in
        1|jfs) SELECTED_PERSONA="jfs" ;;
        2|rq)  SELECTED_PERSONA="rq"  ;;
        3|br)  SELECTED_PERSONA="br"  ;;
        *)
            echo -e "${RD}[TRIT_NEG] Invalid: '${SELECTION}'. Expected 1/2/3 or jfs/rq/br${RS}"
            log_neg "Invalid persona selection: '${SELECTION}'"
            exit 1 ;;
    esac
fi

VALID=false
for p in "${PERSONAS[@]}"; do [ "$p" = "$SELECTED_PERSONA" ] && VALID=true && break; done
if [ "$VALID" = false ]; then
    echo -e "${RD}[TRIT_NEG] Unknown persona: '${SELECTED_PERSONA}'${RS}"; exit 1
fi

ACTIVE_NAME="${PERSONA_NAME[$SELECTED_PERSONA]}"
ACTIVE_TITLE="${PERSONA_TITLE[$SELECTED_PERSONA]}"
ACTIVE_SEED="${SEED_OVERRIDE:-${PERSONA_SEED[$SELECTED_PERSONA]}}"
ACTIVE_SYSTEM="${PERSONA_SYSTEM[$SELECTED_PERSONA]}"

echo -e ""; echo -e "${GR}[TRIT_POS] Identity loaded: ${WH}${ACTIVE_NAME}${RS}  ${DM}${ACTIVE_TITLE}${RS}"
log_pos "Session opened — persona: ${SELECTED_PERSONA} (${ACTIVE_NAME})"

# ── Phase 5: Seed Graph ───────────────────────────────────────────────────────
echo -e ""; echo -e "${BL}[*] Phase 5: NDGi Seed Graph Check...${RS}"
SEED_PATH=""
if [ -n "$ACTIVE_SEED" ]; then
    [ -f "$ACTIVE_SEED" ] && SEED_PATH="$ACTIVE_SEED"
    [ -z "$SEED_PATH" ] && [ -f "$ROOT_DIR/$ACTIVE_SEED" ] && SEED_PATH="$ROOT_DIR/$ACTIVE_SEED"
fi

if [ -n "$SEED_PATH" ]; then
    SEED_DATA=$(cat "$SEED_PATH")
    if [[ "$SEED_DATA" == *"graph_metadata"* ]] && [[ "$SEED_DATA" != *'"human_confirmed": true'* ]]; then
        echo -e "${RD}[TRIT_NEG] Seed blocked: missing human_confirmed gate.${RS}"
        log_neg "Graph ingestion blocked — ${SELECTED_PERSONA}"
        echo -e "${YL}[TRIT_ZERO] Proceeding without seed.${RS}"
    else
        echo -e "${GR}[TRIT_POS] Seed graph: ${SEED_PATH}${RS}"
        ACK=$(curl -s "$API_URL" -H "Content-Type: application/json" \
            -d "$(jq -n --arg sys "$ACTIVE_SYSTEM" \
                --arg usr "INIT: Ingest NDGi seed for ${SELECTED_PERSONA}. Confirm TRIT_POS. Seed: $(cat "$SEED_PATH")" \
                --arg m "aegis-coder" \
                '{model:$m,messages:[{role:"system",content:$sys},{role:"user",content:$usr}],max_tokens:128,temperature:0.1}')" \
            | jq -r '.choices[0].message.content // empty' 2>/dev/null || true)
        [ -n "$ACK" ] && echo -e "${GR}[TRIT_POS] Seed ack:${RS} ${DM}${ACK:0:100}${RS}" \
                       || echo -e "${YL}[TRIT_ZERO] Seed call returned empty.${RS}"
    fi
else
    [ -n "$ACTIVE_SEED" ] \
        && echo -e "${YL}[TRIT_ZERO] Seed '${ACTIVE_SEED}' not found.${RS}" \
        || echo -e "${YL}[TRIT_ZERO] No seed configured.${RS}"
fi

# ── Phase 6: Interactive OODA REPL ────────────────────────────────────────────
echo -e ""
echo -e "${DM}$(printf '─%.0s' {1..65})${RS}"
echo -e " ${GR}[*]${RS} OODA cycle · TDD gates · NDGi state tracking"
echo -e " ${GR}[*]${RS} Persona: ${WH}${ACTIVE_NAME}${RS}  ${DM}[${SELECTED_PERSONA}]${RS}"
echo -e " ${GR}[*]${RS} MoE routing: ${CY}@ciba${RS} ${CY}@archon${RS} ${CY}@photnx${RS} ${CY}@sentinel${RS} ${CY}@trutch${RS} ${CY}@pathfndr${RS}"
echo -e " ${GR}[*]${RS} File inject: ${CY}@file:/abs/path/to/file${RS}"
echo -e " Commands: ${CY}help · status · graph · history · clear · switch · moe · exit${RS}"
echo -e "${DM}$(printf '─%.0s' {1..65})${RS}"; echo -e ""

CONVERSATION_HISTORY="[]"
SESSION_TURN=0

resolve_agent() {
    case "${1,,}" in
        photnx)   echo "AGENT: PHOTNX — photonic hardware, NDGi manifold, optics, PAEM. Respond with physics precision." ;;
        sentinel) echo "AGENT: SENTINEL — security, trust gates, AES-256-GCM, BLAKE3, compliance. Flag all violations." ;;
        trutch)   echo "AGENT: TRUTCH — TDD, test coverage, CI/CD. Block placeholders. Every output needs tests." ;;
        ciba)     echo "AGENT: CIBA — code generation, debugging. Working runnable code only. No pseudocode. No placeholders." ;;
        archon)   echo "AGENT: ARCHON — system architecture, OODA analysis. Observe current state, recommend with evidence." ;;
        pathfndr) echo "AGENT: PATHFNDR — orchestration, task decomposition. Decompose into OODA steps before acting." ;;
        *)        echo "" ;;
    esac
}

build_payload() {
    local msg="$1" agent_ctx="$2" sys="$ACTIVE_SYSTEM"
    [ -n "$agent_ctx" ] && sys="${ACTIVE_SYSTEM}

--- MoE ROUTING ---
${agent_ctx}"
    echo "$CONVERSATION_HISTORY" | jq \
        --arg s "$sys" --arg u "$msg" --arg m "aegis-coder" \
        '{model:$m,messages:([{role:"system",content:$s}]+.+[{role:"user",content:$u}]),max_tokens:2048,temperature:0.2}'
}

append_history() {
    CONVERSATION_HISTORY=$(echo "$CONVERSATION_HISTORY" | jq \
        --arg r "$1" --arg c "$2" '. + [{role:$r,content:$c}]')
}

print_help() {
    echo -e "\n  ${WH}Commands:${RS}"
    echo -e "  ${CY}help${RS}    status  graph  history  clear  switch  moe  exit"
    echo -e "\n  ${WH}Prompt modifiers:${RS}"
    echo -e "  ${CY}@ciba${RS} @archon @photnx @sentinel @trutch @pathfndr"
    echo -e "  ${DM}  Prefix prompt to route to specialist agent${RS}"
    echo -e "  ${CY}@file:/absolute/path${RS}"
    echo -e "  ${DM}  Injects file content into the prompt${RS}"
    echo -e "\n  ${WH}Examples:${RS}"
    echo -e "  ${DM}@ciba write a BET encoder in Python${RS}"
    echo -e "  ${DM}@file:/home/jsosa/workspace/app/index.html @ciba update the investor section${RS}"
    echo -e ""
}

print_moe() {
    echo -e "\n  ${WH}MoE Specialist Agents:${RS}"
    echo -e "  ${CY}@photnx${RS}    Photonic hardware · NDGi · optics · PAEM"
    echo -e "  ${CY}@sentinel${RS}  Security · trust gates · AES/BLAKE3"
    echo -e "  ${CY}@trutch${RS}    TDD · code quality · CI/CD"
    echo -e "  ${CY}@ciba${RS}      Code generation · implementation · debugging"
    echo -e "  ${CY}@archon${RS}    Architecture · system design"
    echo -e "  ${CY}@pathfndr${RS}  Orchestration · OODA planning"
    echo -e ""
}

while true; do
    printf "\n${CY}[${SELECTED_PERSONA^^}]${RS} ${WH}aegis>${RS} "
    USER_INPUT=""
    read -r USER_INPUT </dev/tty || { echo -e "\n${YL}[TRIT_ZERO] EOF. Exiting.${RS}"; break; }
    USER_INPUT=$(echo "$USER_INPUT" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$USER_INPUT" ] && continue

    case "$USER_INPUT" in
        "exit"|"quit"|":q")
            echo -e "${GR}[TRIT_POS] Session closed. Server active on port ${SERVER_PORT}.${RS}"
            log_pos "Session closed — ${SELECTED_PERSONA} — ${SESSION_TURN} turns"; break ;;
        "help"|"?") print_help; continue ;;
        "status")   print_server_status; continue ;;
        "moe")      print_moe; continue ;;
        "graph")
            T=$(echo "$CONVERSATION_HISTORY" | jq 'length')
            echo -e "${DM}  Turns: ${T} | ${SELECTED_PERSONA} (${ACTIVE_NAME})${RS}"
            echo "$CONVERSATION_HISTORY" | jq -r '.[] | "  [\(.role)] \(.content|.[0:100])"' 2>/dev/null || true
            continue ;;
        "history")  echo "$CONVERSATION_HISTORY" | jq '.'; continue ;;
        "clear")
            CONVERSATION_HISTORY="[]"; SESSION_TURN=0
            echo -e "${YL}[TRIT_ZERO] Session cleared.${RS}"; continue ;;
        "switch")
            echo -e "\n  ${CY}[1]${RS} ${PERSONA_NAME[jfs]}  ${CY}[2]${RS} ${PERSONA_NAME[rq]}  ${CY}[3]${RS} ${PERSONA_NAME[br]}"
            printf "  ${WH}Select [1-3 or jfs/rq/br]:${RS} "
            SW=""; read -r SW </dev/tty || true; SW="${SW// /}"
            case "$SW" in
                1|jfs) NP=jfs ;; 2|rq) NP=rq ;; 3|br) NP=br ;;
                *) echo -e "${RD}[TRIT_NEG] Invalid.${RS}"; continue ;;
            esac
            SELECTED_PERSONA=$NP; ACTIVE_NAME="${PERSONA_NAME[$NP]}"
            ACTIVE_TITLE="${PERSONA_TITLE[$NP]}"; ACTIVE_SYSTEM="${PERSONA_SYSTEM[$NP]}"
            CONVERSATION_HISTORY="[]"; SESSION_TURN=0
            echo -e "${GR}[TRIT_POS] Switched to ${WH}${ACTIVE_NAME}${RS}. Session reset."
            log_pos "Switched to ${NP}"; continue ;;
    esac

    # MoE agent tag
    AGENT_TAG="" AGENT_CTX=""
    if [[ "$USER_INPUT" == @* ]]; then
        FIRST=$(echo "$USER_INPUT" | awk '{print $1}' | sed 's/^@//')
        if [[ "$FIRST" != file:* ]]; then
            AGENT_CTX=$(resolve_agent "$FIRST")
            if [ -n "$AGENT_CTX" ]; then
                AGENT_TAG="$FIRST"
                USER_INPUT=$(echo "$USER_INPUT" | sed "s|^@${FIRST}[[:space:]]*||")
                echo -e "${DM}  [MoE] → ${CY}${AGENT_TAG^^}${RS}"
            fi
        fi
    fi

    # File injection
    while [[ "$USER_INPUT" == *"@file:"* ]]; do
        FTAG=$(echo "$USER_INPUT" | grep -oP '@file:[^\s]+' | head -1)
        FPATH="${FTAG#@file:}"
        if [ -f "$FPATH" ]; then
            FLEN=$(wc -c < "$FPATH")
            echo -e "${DM}  [FILE] Injecting: ${FPATH} (${FLEN}B)${RS}"
            FCONTENT=$(cat "$FPATH")
            USER_INPUT="${USER_INPUT//$FTAG/
--- FILE: ${FPATH} ---
${FCONTENT}
--- END FILE ---
}"
        else
            echo -e "${YL}[TRIT_ZERO] File not found: ${FPATH}${RS}"
            USER_INPUT="${USER_INPUT//$FTAG/[FILE NOT FOUND: ${FPATH}]}"
        fi
    done

    if ! check_server; then
        echo -e "${RD}[TRIT_NEG] Server offline.${RS}"
        log_neg "Server offline during session — ${SELECTED_PERSONA}"; continue
    fi

    echo -e "${DM}  [OBSERVE→ORIENT→DECIDE→ACT] Dispatching...${RS}"
    PAYLOAD=$(build_payload "$USER_INPUT" "$AGENT_CTX")

    RESPONSE=$(curl -s --max-time 120 "$API_URL" \
        -H "Content-Type: application/json" -d "$PAYLOAD" 2>/dev/null || true)

    if [ -z "$RESPONSE" ] || [ "$RESPONSE" = "null" ]; then
        echo -e "${YL}[TRIT_ZERO] Empty response.${RS}"
        log_neg "Empty response — ${SELECTED_PERSONA}"; continue
    fi

    OUTPUT=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty' 2>/dev/null || true)
    if [ -z "$OUTPUT" ]; then
        echo -e "${RD}[TRIT_NEG] Invalid response structure.${RS}"
        echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
        log_neg "Invalid JSON from model."; continue
    fi

    SESSION_TURN=$((SESSION_TURN + 1))
    ALABEL=""; [ -n "$AGENT_TAG" ] && ALABEL=" · ${AGENT_TAG^^}"
    echo -e "\n${DM}── [${SELECTED_PERSONA}]${ALABEL} · Turn ${SESSION_TURN} $(printf '─%.0s' {1..38})${RS}"
    echo -e "$OUTPUT"
    echo -e "${DM}$(printf '─%.0s' {1..65})${RS}"

    append_history "user" "$USER_INPUT"
    append_history "assistant" "$OUTPUT"
    CONVERSATION_HISTORY=$(echo "$CONVERSATION_HISTORY" | jq 'if length > 20 then .[-20:] else . end')
done
