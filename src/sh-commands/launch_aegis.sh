#!/bin/bash
# ==============================================================================
# AEGIS ORCHESTRATOR — Unified Launch System v3.2
# Wellton Photonics | NDGi Core Engine | OODA-Native | TDD-Gated | MoE-Ready
# Operating Principle: Seeking Truth with Least Action
# ==============================================================================
# USAGE:
#   ./launch_aegis.sh [1|2|3]           # Persona shorthand
#   ./launch_aegis.sh --persona jfs
#   ./launch_aegis.sh --moe             # Python MoE dispatcher
#   ./launch_aegis.sh --status
#   ./launch_aegis.sh --stop
#
# v3.2 CHANGES:
#   - ASCII spinner during inference (OBSERVE→ORIENT→DECIDE→ACT animation)
#   - CUDA/GPU detection: auto-sets -ngl 99 when nvidia-smi confirms GPU
#   - Thread count auto-tuned: P-cores only on i7-13700HX (12 threads default)
#   - OODA checklist executor: 'checklist' command breaks task into OODA steps
#     and executes each as a separate inference call with progress tracking
#   - tok/s readout after each inference call
#   - run_inference_server.py args passthrough for CUDA flags
# ==============================================================================

set -u

GR="\033[0;32m"; YL="\033[0;33m"; RD="\033[0;31m"
BL="\033[0;34m"; CY="\033[0;36m"; WH="\033[1;37m"
DM="\033[2;37m"; MG="\033[0;35m"; RS="\033[0m"

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

# ── CUDA / thread config (auto-detected at launch) ────────────────────────────
GPU_LAYERS=0          # set to 99 if CUDA confirmed
CPU_THREADS=12        # i7-13700HX: 8 P-cores × HT = 16 logical; 12 = safe P-core ceiling
BATCH_THREADS=12

log_neg() { mkdir -p "$LOG_DIR"; echo "[TRIT_NEG] $(date '+%Y-%m-%d %H:%M:%S') — $1" >> "$LESSONS_FILE"; }
log_pos() { mkdir -p "$LOG_DIR"; echo "[TRIT_POS] $(date '+%Y-%m-%d %H:%M:%S') — $1" >> "$LOG_DIR/aegis_session.log"; }

# ── CUDA detection ────────────────────────────────────────────────────────────
detect_cuda() {
    # Check 1: nvidia-smi responds
    if ! command -v nvidia-smi &>/dev/null || ! nvidia-smi &>/dev/null; then
        echo -e "${YL}  [CUDA] nvidia-smi not available or GPU offline.${RS}"
        return 1
    fi
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    echo -e "${GR}  [CUDA] GPU detected: ${GPU_NAME} (${GPU_MEM}MB VRAM)${RS}"

    # Check 2: llama-server built with CUDA (libcuda or libcublas in ldd)
    if ldd "$ROOT_DIR/build/bin/llama-server" 2>/dev/null | grep -qiE "cuda|cublas"; then
        echo -e "${GR}  [CUDA] llama-server compiled with CUDA support.${RS}"
        GPU_LAYERS=99
        return 0
    else
        echo -e "${YL}  [CUDA] llama-server NOT compiled with CUDA (CPU-only build).${RS}"
        echo -e "${YL}  [CUDA] To enable: rebuild with cmake -DGGML_CUDA=ON${RS}"
        echo -e "${DM}          cd $ROOT_DIR && cmake -B build -DGGML_CUDA=ON && cmake --build build -j\$(nproc)${RS}"
        GPU_LAYERS=0
        return 1
    fi
}

# ── Thread auto-tune ──────────────────────────────────────────────────────────
detect_threads() {
    TOTAL=$(nproc 2>/dev/null || echo 24)
    # i7-13700HX: 6 P-cores + 8 E-cores = 14 physical, 24 logical
    # E-cores are slower for serial token generation — use P-cores only
    # Heuristic: min(16, total/2 + 2) caps at 16 for generation thread
    CPU_THREADS=$(( TOTAL / 2 + 2 ))
    [ "$CPU_THREADS" -gt 16 ] && CPU_THREADS=16
    [ "$CPU_THREADS" -lt 4 ]  && CPU_THREADS=4
    BATCH_THREADS=$CPU_THREADS
    echo -e "${GR}  [CPU] Threads: ${CPU_THREADS} gen / ${BATCH_THREADS} batch (of ${TOTAL} logical cores)${RS}"
}

# ── Spinner ───────────────────────────────────────────────────────────────────
# Runs in background during blocking curl calls.
# Usage: start_spinner "label"; ... work ...; stop_spinner $verdict
SPINNER_PID=""
SPINNER_FRAMES=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
OODA_PHASES=("OBSERVE" "ORIENT " "DECIDE " "ACT    ")

start_spinner() {
    local label="${1:-Thinking}"
    local phase_idx=0
    local frame_idx=0
    local dots=""
    local tick=0

    (
        tput civis 2>/dev/null || true   # hide cursor
        while true; do
            frame="${SPINNER_FRAMES[$((frame_idx % 10))]}"
            phase="${OODA_PHASES[$((phase_idx % 4))]}"
            dots_count=$(( tick % 6 ))
            dots=$(printf '.%.0s' $(seq 1 $((dots_count + 1))))
            printf "\r  ${CY}${frame}${RS} ${DM}[${phase}]${RS} ${WH}${label}${RS}${DM}${dots}${RS}      " >&2
            sleep 0.12
            frame_idx=$((frame_idx + 1))
            tick=$((tick + 1))
            # Advance OODA phase every ~10 frames (~1.2s)
            [ $((frame_idx % 10)) -eq 0 ] && phase_idx=$((phase_idx + 1))
        done
    ) &
    SPINNER_PID=$!
    disown "$SPINNER_PID" 2>/dev/null || true
}

stop_spinner() {
    local verdict="${1:-TRIT_POS}"
    local latency="${2:-}"
    if [ -n "$SPINNER_PID" ]; then
        kill "$SPINNER_PID" 2>/dev/null || true
        wait "$SPINNER_PID" 2>/dev/null || true
        SPINNER_PID=""
    fi
    tput cnorm 2>/dev/null || true   # restore cursor
    printf "\r%-70s\r" " "           # clear spinner line

    case "$verdict" in
        TRIT_POS)  printf "  ${GR}[TRIT_POS]${RS}" ;;
        TRIT_ZERO) printf "  ${YL}[TRIT_ZERO]${RS}" ;;
        TRIT_NEG)  printf "  ${RD}[TRIT_NEG]${RS}" ;;
    esac
    [ -n "$latency" ] && printf " ${DM}${latency}${RS}"
    printf "\n"
}

print_banner() {
    local cuda_label="OFF"
    [ "$GPU_LAYERS" -gt 0 ] && cuda_label="${GR}ON${RS}" || cuda_label="${YL}CPU${RS}"
    echo -e ""
    echo -e "${DM}┌────────────────────────────────────────────────────────────────┐${RS}"
    echo -e "${DM}│${RS}  ${WH}AEGIS ORCHESTRATOR v3.2${RS}  ${DM}·${RS}  OODA-Native · NDGi-Live · MoE    ${DM}│${RS}"
    echo -e "${DM}│${RS}  ${DM}BitNet b1.58 · TDD-Gated · Loop-Proof · Ternary-Native${RS}          ${DM}│${RS}"
    echo -e "${DM}├──────────┬──────────┬──────────┬───────────────────────────────┤${RS}"
    echo -e "${DM}│${RS} ${GR}OBSERVE${RS}  ${DM}│${RS} ${YL}ORIENT${RS}   ${DM}│${RS} ${CY}DECIDE${RS}   ${DM}│${RS} ${WH}ACT${RS}                           ${DM}│${RS}"
    echo -e "${DM}├──────────┴──────────┴──────────┴───────────────────────────────┤${RS}"
    echo -e "${DM}│${RS}  Agents: ${CY}PHOTNX·SENTINEL·TRUTCH·CIBA·ARCHON·PATHFNDR${RS}             ${DM}│${RS}"
    echo -e "${DM}│${RS}  TDD:${GR}ON${RS}  Guard:${GR}ON${RS}  HCGate:${GR}ON${RS}  MoE:${GR}ON${RS}  CUDA:${cuda_label}  t:${WH}${CPU_THREADS}${RS}   ${DM}│${RS}"
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

DECISION FRAMEWORK — OODA Loop:
TRIT_POS=correct/proceed · TRIT_ZERO=hold/insufficient signal · TRIT_NEG=reject/failure
Never commit without sufficient signal. Log all TRIT_NEG to lessons.md. One task per session.

MoE AGENT AWARENESS: prefix responses with [PHOTNX]/[SENTINEL]/[TRUTCH]/[CIBA]/[ARCHON]/[PATHFNDR] when domain is clear.

FILE OUTPUT RULE: When generating file content, output ONLY the file content. No CREATE/END markers. No fake shell output. No placeholder values. Real data only.

CHECKLIST EXECUTION RULE: When asked to execute a checklist or multi-step task, format each step as:
[ ] STEP N — <action>
  OBSERVE: <what you examined>
  ORIENT:  <what it means>
  DECIDE:  <your decision>
  ACT:     <exact output or command>
  RESULT:  TRIT_POS / TRIT_ZERO / TRIT_NEG
Mark [x] when complete. Never skip steps. Never produce placeholder output."

PERSONA_NAME[rq]="Robert Q."
PERSONA_TITLE[rq]="Co-Founder — Sales Architecture"
PERSONA_SEED[rq]=""
PERSONA_SYSTEM[rq]="You are Aegis for Robert Q. (NDGi ID: rq), Co-Founder and Sales Architect at Wellton Photonics.
TRIT: TRIT_POS=proceed, TRIT_ZERO=hold, TRIT_NEG=reject. One task per session. No placeholders.
MoE awareness active. NDGi training in collection phase."

PERSONA_NAME[br]="Bobbi R."
PERSONA_TITLE[br]="Co-Founder — Sales Architecture"
PERSONA_SEED[br]=""
PERSONA_SYSTEM[br]="You are Aegis for Bobbi R. (NDGi ID: br), Co-Founder and Sales Architect at Wellton Photonics.
TRIT: TRIT_POS=proceed, TRIT_ZERO=hold, TRIT_NEG=reject. One task per session. No placeholders.
MoE awareness active. NDGi training in collection phase."

PERSONAS=(jfs rq br)

# ── Argument Parsing ──────────────────────────────────────────────────────────
SELECTED_PERSONA=""
SEED_OVERRIDE=""
MODE="launch"

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
        --mode)
            AEGIS_MODE="${2:-full}"
            case "$AEGIS_MODE" in
                coding|ops|full) ;;
                *) echo -e "${RD}[TRIT_NEG] Invalid mode: $AEGIS_MODE (expected: coding|ops|full)${RS}"; exit 1 ;;
            esac
            export AEGIS_MODE
            shift 2 ;;
        --help|-h)
            echo "Usage: $0 [1|2|3] [--persona jfs|rq|br] [--seed file] [--status] [--stop] [--moe] [--mode coding|ops|full]"
            echo ""
            echo "Options:"
            echo "  1|2|3              Persona shorthand (jfs/rq/br)"
            echo "  --persona NAME     Select persona by name"
            echo "  --seed FILE        Override seed graph file"
            echo "  --status           Show server status and exit"
            echo "  --stop             Stop inference server"
            echo "  --moe              Launch Python MoE dispatcher"
            echo "  --mode MODE        Set Aegis mode:"
            echo "                       coding - code analysis, generation, htop"
            echo "                       ops    - operations focus, system monitor"
            echo "                       full   - all features enabled (default)"
            echo ""
            echo "Commands available in aegis-cli.py:"
            echo "  analyze <path>     Codebase analysis (files, languages, functions)"
            echo "  htop               System monitor (CPU, memory, disk, processes)"
            echo "  create <desc> py   Generate code from templates"
            echo "  status             BitNet + NDGi health check"
            echo "  graph              NDGi session graph"
            echo "  help               Full command reference"
            exit 0 ;;
        *) echo -e "${RD}[TRIT_NEG] Unknown arg: $1${RS}"; exit 1 ;;
    esac
done

# Default mode if not set
AEGIS_MODE="${AEGIS_MODE:-full}"
export AEGIS_MODE

check_server() {
    curl -s --max-time 2 "http://${SERVER_HOST}:${SERVER_PORT}/v1/models" &>/dev/null
}

print_server_status() {
    if check_server; then
        echo -e " [${GR}ONLINE${RS}]  port ${SERVER_PORT}  t:${CPU_THREADS}  ngl:${GPU_LAYERS}"
        [ -f "$PID_FILE" ] && echo -e "           PID: $(cat "$PID_FILE")"
    else
        echo -e " [${RD}OFFLINE${RS}] Inference server not responding on port ${SERVER_PORT}"
    fi
}

# ── Stop ──────────────────────────────────────────────────────────────────────
if [ "$MODE" = "stop" ]; then
    detect_threads; detect_cuda 2>/dev/null || true; print_banner
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

# ── Phase 1: Environment + CUDA detect ───────────────────────────────────────
echo -e "${BL}[*] Phase 1: Hardware + Runtime Environment...${RS}"
detect_threads
detect_cuda || true
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:${ROOT_DIR}/build/3rdparty/llama.cpp/src:${ROOT_DIR}/build/3rdparty/llama.cpp/ggml/src"

# Also add CUDA lib paths if present
for cuda_lib in /usr/local/cuda/lib64 /usr/lib/x86_64-linux-gnu; do
    [ -d "$cuda_lib" ] && export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${cuda_lib}"
done

if ! ldd "$ROOT_DIR/build/bin/llama-server" 2>/dev/null | grep -q "libllama.so"; then
    echo -e "${RD}[TRIT_NEG] libllama.so not found. Check build.${RS}"; log_neg "libllama.so missing."; exit 1
fi
echo -e "${GR}[TRIT_POS] Runtime confirmed. GPU_LAYERS=${GPU_LAYERS} THREADS=${CPU_THREADS}${RS}"

# ── Activate venv if present ──────────────────────────────────────────────────
VENV_DIR="$ROOT_DIR/venv"
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate" 2>/dev/null || true
    echo -e "${GR}  [VENV] Activated: ${VENV_DIR}${RS}"
fi

# ── Auto-install missing Python dependencies into venv ───────────────────────
AEGIS_DEPS=(psutil requests)
for dep in "${AEGIS_DEPS[@]}"; do
    if python3 -c "import ${dep}" 2>/dev/null; then
        echo -e "${GR}  [DEP] ${dep}: installed${RS}"
    else
        echo -e "${YL}  [DEP] ${dep}: missing — installing into venv...${RS}"
        python3 -m pip install "$dep" --quiet 2>/dev/null \
            && echo -e "${GR}  [DEP] ${dep}: installed successfully${RS}" \
            || echo -e "${RD}  [DEP] ${dep}: install failed — feature will be disabled${RS}"
    fi
done

if [ "$MODE" = "status" ]; then print_banner; print_server_status; exit 0; fi
if [ "$MODE" = "moe" ]; then
    print_banner
    if [ -f "$MOE_SCRIPT" ]; then
        [ -f "$ROOT_DIR/venv/bin/activate" ] && source "$ROOT_DIR/venv/bin/activate" || true
        python3 "$MOE_SCRIPT" "${SELECTED_PERSONA:-jfs}"
    else
        echo -e "${RD}[TRIT_NEG] aegis_moe.py not found at ${MOE_SCRIPT}${RS}"
        echo -e "${YL}  Copy aegis_moe.py to $ROOT_DIR/utils/${RS}"
        exit 1
    fi
    exit 0
fi

print_banner

# ── Phase 2: Model ────────────────────────────────────────────────────────────
echo -e "${BL}[*] Phase 2: Resolving Ternary Model Binary...${RS}"
RESOLVED_MODEL=""
for c in "${MODEL_CANDIDATES[@]}"; do
    if [ -f "$c" ]; then RESOLVED_MODEL="$c"; echo -e "${GR}[TRIT_POS] Model: ${c}${RS}"; break; fi
done

if [ -z "$RESOLVED_MODEL" ]; then
    echo -e "${YL}[TRIT_ZERO] Scanning...${RS}"
    FOUND=$(find "$ROOT_DIR" /home/jsosa/BitNet -name "ggml-model-i2_s.gguf" 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        EXP="$ROOT_DIR/models/bitnet_b1_58-3B/ggml-model-i2_s.gguf"
        mkdir -p "$(dirname "$EXP")" && ln -sf "$FOUND" "$EXP"
        RESOLVED_MODEL="$EXP"; echo -e "${GR}[TRIT_POS] Symlinked: ${EXP}${RS}"
    else
        echo -e "${RD}[TRIT_NEG] Model not found.${RS}"; log_neg "Model binary not found."; exit 1
    fi
fi

# ── Phase 3: Inference Server (CUDA-aware) ────────────────────────────────────
echo -e ""; echo -e "${BL}[*] Phase 3: Inference Server Bootstrap...${RS}"
mkdir -p "$LOG_DIR"

if check_server; then
    echo -e "${GR}[TRIT_POS] Inference server already live on port ${SERVER_PORT}.${RS}"
    echo -e "${DM}  NOTE: Server may be running with old thread/GPU settings.${RS}"
    echo -e "${DM}  To restart with optimal settings: --stop then relaunch.${RS}"
else
    [ -f "$ROOT_DIR/venv/bin/activate" ] && source "$ROOT_DIR/venv/bin/activate" || true

    # Build server args — these override the run_inference_server.py defaults
    SERVER_EXTRA_ARGS="-t ${CPU_THREADS} -tb ${BATCH_THREADS} -ngl ${GPU_LAYERS}"
    [ "$GPU_LAYERS" -gt 0 ] && echo -e "${GR}  [CUDA] Launching with -ngl ${GPU_LAYERS} (full GPU offload)${RS}" \
                              || echo -e "${YL}  [CPU]  Launching with -t ${CPU_THREADS} threads (no GPU offload)${RS}"
    echo -e "${DM}  Tip: rebuild with -DGGML_CUDA=ON to enable GPU. Current: $(ldd build/bin/llama-server 2>/dev/null | grep -c cuda) cuda libs linked.${RS}"

    SERVER_CMD="python3 '$INFERENCE_SCRIPT' --port ${SERVER_PORT}"
    # Pass through extra args via env var (run_inference_server.py must support AEGIS_SERVER_ARGS)
    export AEGIS_SERVER_ARGS="$SERVER_EXTRA_ARGS"

    if command -v gnome-terminal &>/dev/null; then
        gnome-terminal --title="Aegis Inference Server [t:${CPU_THREADS} ngl:${GPU_LAYERS}]" -- bash -c "
            export LD_LIBRARY_PATH='${LD_LIBRARY_PATH}';
            export AEGIS_SERVER_ARGS='${SERVER_EXTRA_ARGS}';
            cd '$ROOT_DIR';
            source venv/bin/activate 2>/dev/null || true;
            python3 run_inference_server.py --port ${SERVER_PORT};
            exec bash" &
        echo -e "${GR}[TRIT_POS] Server launched in new terminal [t:${CPU_THREADS} ngl:${GPU_LAYERS}].${RS}"
    else
        (
            export AEGIS_SERVER_ARGS="$SERVER_EXTRA_ARGS"
            cd "$ROOT_DIR" && python3 "$INFERENCE_SCRIPT" --port "${SERVER_PORT}"
        ) >"$LOG_DIR/server_output.log" 2>&1 &
        SP=$!; echo "$SP" > "$PID_FILE"; disown "$SP"
        echo -e "${GR}[TRIT_POS] Server PID $SP. Log: ${LOG_DIR}/server_output.log${RS}"
    fi

    echo -e "${BL}[*] Waiting for port ${SERVER_PORT}...${RS}"
    UP=false
    for i in $(seq 1 25); do
        check_server && UP=true && break
        grep -q "HTTP server is listening" "$LOG_DIR/server_output.log" 2>/dev/null && UP=true && break
        printf "\r  ${DM}Initializing${RS} $(printf '▪%.0s' $(seq 1 $((i % 8 + 1))))   "
        sleep 1
    done; echo ""
    [ "$UP" = false ] && {
        echo -e "${RD}[TRIT_NEG] Server timed out.${RS}"
        tail -n 15 "$LOG_DIR/server_output.log" 2>/dev/null || true
        log_neg "Server init timed out."; exit 1
    }
    echo -e "${GR}[TRIT_POS] Inference server alive.${RS}"
fi

# ── Phase 4: Persona Selector ─────────────────────────────────────────────────
echo -e ""; echo -e "${BL}[*] Phase 4: Aegis Identity Selection...${RS}"; echo -e ""

if [ -z "$SELECTED_PERSONA" ]; then
    echo -e "  ${CY}[1]${RS} ${WH}${PERSONA_NAME[jfs]}${RS}  —  ${DM}${PERSONA_TITLE[jfs]}${RS}  ${GR}[jfs]${RS}"
    echo -e "  ${CY}[2]${RS} ${WH}${PERSONA_NAME[rq]}${RS}  —  ${DM}${PERSONA_TITLE[rq]}${RS}  ${YL}[rq·pending]${RS}"
    echo -e "  ${CY}[3]${RS} ${WH}${PERSONA_NAME[br]}${RS}  —  ${DM}${PERSONA_TITLE[br]}${RS}  ${YL}[br·pending]${RS}"
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
            log_neg "Invalid persona selection: '${SELECTION}'"; exit 1 ;;
    esac
fi

VALID=false
for p in "${PERSONAS[@]}"; do [ "$p" = "$SELECTED_PERSONA" ] && VALID=true && break; done
[ "$VALID" = false ] && { echo -e "${RD}[TRIT_NEG] Unknown persona: '${SELECTED_PERSONA}'${RS}"; exit 1; }

ACTIVE_NAME="${PERSONA_NAME[$SELECTED_PERSONA]}"
ACTIVE_TITLE="${PERSONA_TITLE[$SELECTED_PERSONA]}"
ACTIVE_SEED="${SEED_OVERRIDE:-${PERSONA_SEED[$SELECTED_PERSONA]}}"
ACTIVE_SYSTEM="${PERSONA_SYSTEM[$SELECTED_PERSONA]}"

echo -e ""; echo -e "${GR}[TRIT_POS] Identity loaded: ${WH}${ACTIVE_NAME}${RS}  ${DM}${ACTIVE_TITLE}${RS}"
log_pos "Session opened — ${SELECTED_PERSONA} (${ACTIVE_NAME})"

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
        echo -e "${RD}[TRIT_NEG] Seed blocked — missing human_confirmed gate.${RS}"
        log_neg "Graph ingestion blocked — ${SELECTED_PERSONA}"
        echo -e "${YL}[TRIT_ZERO] Proceeding without seed.${RS}"
    else
        echo -e "${GR}[TRIT_POS] Seed: ${SEED_PATH}${RS}"
        start_spinner "Ingesting NDGi seed graph"
        ACK=$(curl -s "$API_URL" -H "Content-Type: application/json" \
            -d "$(jq -n --arg sys "$ACTIVE_SYSTEM" \
                --arg usr "INIT: Ingest NDGi seed for ${SELECTED_PERSONA}. Confirm TRIT_POS. Seed: $(cat "$SEED_PATH")" \
                --arg m "aegis-coder" \
                '{model:$m,messages:[{role:"system",content:$sys},{role:"user",content:$usr}],max_tokens:128,temperature:0.1}')" \
            | jq -r '.choices[0].message.content // empty' 2>/dev/null || true)
        stop_spinner "TRIT_POS"
        [ -n "$ACK" ] && echo -e "  ${DM}${ACK:0:120}${RS}" || echo -e "${YL}[TRIT_ZERO] Seed returned empty.${RS}"
    fi
else
    [ -n "$ACTIVE_SEED" ] \
        && echo -e "${YL}[TRIT_ZERO] Seed '${ACTIVE_SEED}' not found — copy to $ROOT_DIR/${RS}" \
        || echo -e "${YL}[TRIT_ZERO] No seed configured for '${SELECTED_PERSONA}'.${RS}"
fi
# ── Phase 6: Hand off to unified Python REPL ─────────────────────────────────
echo -e ""
echo -e "${GR}[TRIT_POS] Launching unified Python REPL...${RS}"
echo -e "${DM}  Persona: ${SELECTED_PERSONA}  GPU: ${GPU_LAYERS}  Threads: ${CPU_THREADS}  Mode: ${AEGIS_MODE}${RS}"
echo -e ""

export AEGIS_GPU_LAYERS="$GPU_LAYERS"
export AEGIS_CPU_THREADS="$CPU_THREADS"
export AEGIS_PERSONA="$SELECTED_PERSONA"

# Crucial: Switch into your tool and library repository context
cd "/home/jsosa/workspace/aegis-ternary"

exec python3 "./src/aegis-cli.py" \
    --persona "$SELECTED_PERSONA" \
    --gpu-layers "$GPU_LAYERS" \
    --threads "$CPU_THREADS" \
    --mode "$AEGIS_MODE"
