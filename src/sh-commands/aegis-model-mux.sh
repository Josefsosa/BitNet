#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# aegis-model-mux.sh — Multi-Pane MCP Client & BitNet Server Environment
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

SESSION="${AEGIS_SESSION:-aegis-models}"

# ── Architectural Path Mapping ────────────────────────────────────────────
# 1. Low-Level Model/Binary Layer
BITNET_ROOT="/home/jsosa/workspace/BitNet"
MODELS_DIR="${MODELS_DIR:-/media/jsosa/One Touch/Models}"
INFERENCE_SCRIPT="$BITNET_ROOT/run_inference_server.py"

# 2. True Development MCP Agent Layer
AEGIS_ROOT="/home/jsosa/workspace/aegis-ternary"
AEGIS_SRC_DIR="$AEGIS_ROOT/src"
AEGIS_CLI="$AEGIS_SRC_DIR/aegis-cli.py"  # Target your massive live version

# Runtime Settings
LLAMA_HOST="127.0.0.1"
LLAMA_PORT="8080"

STATE_DIR="$HOME/.aegis-mux"
PID_FILE="$STATE_DIR/llama-server.pid"
MODEL_FILE="$STATE_DIR/current-model"
LOG_FILE="$STATE_DIR/llama-server.log"

mkdir -p "$STATE_DIR"

# Standardizing explicit linkers across your filesystem trees
BITNET_LD_PATH="$BITNET_ROOT/build/bin:$BITNET_ROOT/build:$BITNET_ROOT/build/3rdparty/llama.cpp/src:$BITNET_ROOT/build/3rdparty/llama.cpp/ggml/src"
export LD_LIBRARY_PATH="$BITNET_LD_PATH:${LD_LIBRARY_PATH:-}"

# ── UI Presentation Components ────────────────────────────────────────────
POS='\033[32m'; ZERO='\033[33m'; NEG='\033[31m'; CYAN='\033[36m'; BLUE='\033[34m'; RST='\033[0m'
ok()   { printf "${POS}[TRIT_POS]${RST}  %s\n" "$*"; }
zero() { printf "${ZERO}[TRIT_ZERO]${RST} %s\n" "$*"; }
neg()  { printf "${NEG}[TRIT_NEG]${RST}  %s\n" "$*" >&2; }

# ── Hardware Auto-Tuning Discovery Engine ─────────────────────────────────
GPU_LAYERS=0
CPU_THREADS=12

detect_hardware_profiles() {
  local total_cores
  total_cores=$(nproc 2>/dev/null || echo 24)
  CPU_THREADS=$(( total_cores / 2 + 2 ))
  [ "$CPU_THREADS" -gt 16 ] && CPU_THREADS=16
  [ "$CPU_THREADS" -lt 4 ]  && CPU_THREADS=4
  
  if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    if ldd "$BITNET_ROOT/build/bin/llama-server" 2>/dev/null | grep -qiE "cuda|cublas"; then
      GPU_LAYERS=99
    fi
  fi
}

server_healthy() {
  curl -fsS -m 2 "http://$LLAMA_HOST:$LLAMA_PORT/health" >/dev/null 2>&1
}

stop_server() {
  if [ -f "$PID_FILE" ]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  fuser -k "${LLAMA_PORT}/tcp" 2>/dev/null || true
  sleep 1
}

start_server() {
  local model="$1"
  stop_server
  detect_hardware_profiles
  zero "Bootstrapping Inference Core [t:${CPU_THREADS} ngl:${GPU_LAYERS}]..."

  if [ -f "$BITNET_ROOT/venv/bin/activate" ]; then
    source "$BITNET_ROOT/venv/bin/activate"
  fi

  export LD_LIBRARY_PATH="$BITNET_LD_PATH:${LD_LIBRARY_PATH:-}"
  export AEGIS_SERVER_ARGS="-t ${CPU_THREADS} -tb ${CPU_THREADS} -ngl ${GPU_LAYERS}"

  python3 "$INFERENCE_SCRIPT" \
      --model "$model" \
      --host "$LLAMA_HOST" \
      --port "$LLAMA_PORT" \
      --threads "$CPU_THREADS" \
      > "$LOG_FILE" 2>&1 &
  
  SERVER_PID=$!
  echo $SERVER_PID > "$PID_FILE"

  for i in {1..30}; do
    if server_healthy; then
      printf '%s' "$model" > "$MODEL_FILE"
      ok "Inference Server Active -> $(basename "$model")"
      return 0
    fi
    sleep 1
  done
  neg "Server initialization timeout. Review logging output pane."
  return 1
}

list_models() {
  find "$MODELS_DIR" -type f -name '*.gguf' 2>/dev/null | sort
}

# ══ MODE: __selector (Left-hand Pane Control Center) ══════════════════════
if [ "${1:-}" = "__selector" ]; then
  detect_hardware_profiles
  while true; do
    clear
    printf "${CYAN}═══ AEGIS ARCHITECTURE DEPLOYMENT CORE ═══${RST}\n"
    printf "BitNet Target: %s\n" "$BITNET_ROOT"
    printf "MCP Workspace: %s\n" "$AEGIS_ROOT"
    printf "Hardware Auto: Threads: %s | GPU Layers: %s\n" "$CPU_THREADS" "$GPU_LAYERS"
    printf "Inference State: "
    if server_healthy; then
      printf "${POS}● HOSTING ONLINE${RST}"
      [ -f "$MODEL_FILE" ] && printf " (%s)" "$(basename "$(cat "$MODEL_FILE")")"
      printf "\n"
    else
      printf "${ZERO}○ STANDBY / ENGINE OFFLINE${RST}\n"
    fi
    printf "────────────────────────────────────────────────────────────\n"

    mapfile -t MODELS < <(list_models)
    if [ "${#MODELS[@]}" -eq 0 ]; then
      neg "Storage volume empty or unmounted: $MODELS_DIR"
    else
      local_i=1
      for m in "${MODELS[@]}"; do
        sz="$(du -h "$m" 2>/dev/null | cut -f1)"
        printf "  ${CYAN}%2d${RST}) %-45s %s\n" "$local_i" "$(basename "$m")" "$sz"
        local_i=$((local_i+1))
      done
    fi

    printf "────────────────────────────────────────────────────────────\n"
    printf "  ${CYAN} [ID]${RST} Mount Weight Matrix  ${CYAN} r${RST}) Rescan Volume\n"
    printf "  ${CYAN} s${RST}   Unmount Backend Matrix ${CYAN} q${RST}) Detach Controller\n\n"
    read -rp "aegis-mcp-control > " choice || exit 0

    case "$choice" in
      q) exit 0 ;;
      r) continue ;;
      s) stop_server; rm -f "$MODEL_FILE"; zero "Backend unmounted."; sleep 1 ;;
      '') ;;
      *[!0-9]*) zero "Selection token error."; sleep 1 ;;
      *)
        idx=$((choice-1))
        if [ "$idx" -ge 0 ] && [ "$idx" -lt "${#MODELS[@]}" ]; then
          start_server "${MODELS[$idx]}" || read -rp "Press [Enter] to cycle..." _
          sleep 1
        else
          zero "Index token out of bounds."; sleep 1
        fi
        ;;
    esac
  done
fi

# ══ MODE: __tester (Right-hand Core Evaluation Window) ════════════════════
if [ "${1:-}" = "__tester" ]; then
  detect_hardware_profiles
  while true; do
    clear
    printf "${CYAN}═══ LIVE MCP AGENT PIPELINE RUNNER ═══${RST}\n"
    if ! server_healthy; then
      zero "Awaiting initialization handshake sequence from local port :$LLAMA_PORT..."
      until server_healthy; do sleep 2; done
    fi
    
    ok "Pipeline connected to Model Matrix: $(basename "$(cat "$MODEL_FILE" 2>/dev/null || echo 'Aegis Core')")"
    echo "----------------------------------------------------------------------"
    
    # Force clean directory traversal rules straight to the massive codebase
    cd "$AEGIS_SRC_DIR"
    
    # Activate your primary virtual environment to handle massive dependency trees
    if [ -f "$AEGIS_ROOT/venv/bin/activate" ]; then
      source "$AEGIS_ROOT/venv/bin/activate"
    elif [ -f "$BITNET_ROOT/venv/bin/activate" ]; then
      source "$BITNET_ROOT/venv/bin/activate"
    fi

    if [ -f "$AEGIS_CLI" ]; then
      echo -e "${BLUE}[*] Launching Current Codebase -> $AEGIS_CLI...${RST}\n"
      
      export AEGIS_GPU_LAYERS="$GPU_LAYERS"
      export AEGIS_CPU_THREADS="$CPU_THREADS"
      export AEGIS_MODE="full"

      # Execute your active version directly.
      # If it finishes, it falls back gracefully rather than bricking the input flow.
      python3 "$AEGIS_CLI" \
          --persona "jfs" \
          --gpu-layers "$GPU_LAYERS" \
          --threads "$CPU_THREADS" \
          --mode "full" || neg "Process returned a non-zero exit validation code."
    else
      neg "Core MCP Agent File not found at target path: $AEGIS_CLI"
    fi
    
    printf "\n"
    read -rp "[Execution Paused] Press [Enter] to hot-reload and restart the pipeline..." _
  done
fi

# ══ MODE: kill ════════════════════════════════════════════════════════════
if [ "${1:-}" = "kill" ]; then
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  stop_server
  echo "Aegis MCP environment torn down cleanly."
  exit 0
fi

# ══ RECONSTRUCT PURE MULTIPLEXER TERMINALS ════════════════════════════════
sudo ln -sf /home/linuxbrew/.linuxbrew/bin/brew /bin/brew 2>/dev/null || true

if tmux has-session -t "$SESSION" 2>/dev/null; then
  exec tmux attach -t "$SESSION"
fi

touch "$LOG_FILE"
SELF="$(readlink -f "$0")"

# Build absolute boundaries to guarantee easy structural visibility
tmux new-session -d -s "$SESSION" -x 240 -y 60

# Window Partition 0: Left Side Model Mount Controller Matrix
tmux send-keys -t "$SESSION:0.0" "bash $(printf %q "$SELF") __selector" C-m

# Window Partition 1: Top-Right Dedicated Live Agent Client Pane
pane_test="$(tmux split-window -t "$SESSION:0" -h -P -F '#{pane_id}')"
tmux send-keys -t "$pane_test" "bash $(printf %q "$SELF") __tester" C-m

# Window Partition 2: Bottom-Right Streaming Diagnostics Window
pane_log="$(tmux split-window -t "$pane_test" -v -P -F '#{pane_id}')"
tmux send-keys -t "$pane_log" "tail -F $(printf %q "$LOG_FILE")" C-m

# Geometry Layout Standardization
tmux set-window-option -t "$SESSION:0" main-pane-width 85
tmux select-layout -t "$SESSION:0" main-vertical >/dev/null
tmux select-pane -t "$pane_test" # Land focus straight onto the code tester pane

exec tmux attach -t "$SESSION"