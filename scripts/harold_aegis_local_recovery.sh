#!/usr/bin/env bash
# Aegis local setup/recovery for Harold's macOS BitNet workspace.
# Run from anywhere inside the BitNet repo:
#   bash scripts/harold_aegis_local_recovery.sh gemma4-coding-q2-k

set -u

MODEL_ALIAS="${1:-gemma4-coding-q2-k}"
API_PORT="${AEGIS_API_PORT:-5510}"
BACKEND_PORT="${AEGIS_BACKEND_PORT:-5511}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$REPO_ROOT/src"
LOG_DIR="$REPO_ROOT/logs"
LOG_FILE="$LOG_DIR/harold_aegis_local_recovery.log"
STATUS_FILE="$LOG_DIR/harold_aegis_status.txt"

mkdir -p "$LOG_DIR"
: > "$LOG_FILE"
: > "$STATUS_FILE"

log() {
  printf '%s\n' "$*" | tee -a "$LOG_FILE"
}

step() {
  log ""
  log "== $* =="
}

run() {
  log "+ $*"
  "$@" 2>&1 | tee -a "$LOG_FILE"
  local code=${PIPESTATUS[0]}
  if [ "$code" -ne 0 ]; then
    log "[TRIT_NEG] Command failed with exit code $code: $*"
    return "$code"
  fi
  return 0
}

find_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
  elif command -v python3.10 >/dev/null 2>&1; then
    command -v python3.10
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    return 1
  fi
}

find_llama_server() {
  if [ -n "${LLAMA_SERVER_PATH:-}" ] && [ -x "$LLAMA_SERVER_PATH" ]; then
    printf '%s\n' "$LLAMA_SERVER_PATH"
    return 0
  fi
  if [ -x "$REPO_ROOT/build/bin/llama-server" ]; then
    printf '%s\n' "$REPO_ROOT/build/bin/llama-server"
    return 0
  fi
  if command -v llama-server >/dev/null 2>&1; then
    command -v llama-server
    return 0
  fi
  find "$REPO_ROOT" -type f -name llama-server -perm +111 2>/dev/null | head -n 1
}

write_status() {
  {
    echo "Aegis local recovery status"
    echo "repo=$REPO_ROOT"
    echo "model_alias=$MODEL_ALIAS"
    echo "api_port=$API_PORT"
    echo "backend_port=$BACKEND_PORT"
    echo
    echo "date:"
    date
    echo
    echo "pwd:"
    pwd
    echo
    echo "git_head:"
    git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || true
    echo
    echo "git_status:"
    git -C "$REPO_ROOT" status --short --branch 2>/dev/null || true
    echo
    echo "python:"
    if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
      "$REPO_ROOT/.venv/bin/python" --version 2>&1 || true
    else
      python3 --version 2>&1 || true
    fi
    echo
    echo "submodule_requirements:"
    ls -l "$REPO_ROOT/3rdparty/llama.cpp/requirements/requirements-convert_legacy_llama.txt" 2>&1 || true
    echo
    echo "llama_server:"
    find_llama_server 2>/dev/null || true
    echo
    echo "model_list:"
    if [ -x "$REPO_ROOT/.venv/bin/python" ] && [ -f "$SRC_DIR/aegis_local_inference_server.py" ]; then
      (cd "$SRC_DIR" && "$REPO_ROOT/.venv/bin/python" aegis_local_inference_server.py list) 2>&1 || true
    fi
    echo
    echo "last_120_log_lines:"
    tail -n 120 "$LOG_FILE" 2>/dev/null || true
  } > "$STATUS_FILE"
}

trap write_status EXIT

step "OBSERVE: workspace"
log "Repo root: $REPO_ROOT"
log "Requested model alias: $MODEL_ALIAS"
if [ ! -f "$SRC_DIR/aegis_local_inference_server.py" ]; then
  log "[TRIT_NEG] Missing $SRC_DIR/aegis_local_inference_server.py"
  log "Run this script from a complete BitNet checkout."
  exit 1
fi

cd "$REPO_ROOT" || exit 1
run pwd || exit 1
run git status --short --branch || true

step "OBSERVE: required tools"
PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  log "[TRIT_NEG] No python found. Install Python 3.11, then rerun."
  log "macOS: brew install python@3.11"
  exit 1
fi
log "Python selected: $PYTHON_BIN"
"$PYTHON_BIN" --version 2>&1 | tee -a "$LOG_FILE"

if ! command -v git >/dev/null 2>&1; then
  log "[TRIT_NEG] git is missing. Install Xcode Command Line Tools: xcode-select --install"
  exit 1
fi

if ! command -v cmake >/dev/null 2>&1; then
  log "[TRIT_ZERO] cmake is missing."
  if command -v brew >/dev/null 2>&1; then
    log "Attempting: brew install cmake"
    run brew install cmake || log "[TRIT_ZERO] brew could not install cmake automatically."
  else
    log "Install it manually: brew install cmake"
  fi
fi

step "ORIENT: repair submodules"
if [ ! -f "$REPO_ROOT/3rdparty/llama.cpp/requirements/requirements-convert_legacy_llama.txt" ]; then
  log "llama.cpp requirements are missing. Initializing submodules."
  run git submodule update --init --recursive || {
    log "[TRIT_NEG] Submodule repair failed."
    exit 1
  }
else
  log "llama.cpp requirements file exists."
fi

if [ ! -f "$REPO_ROOT/3rdparty/llama.cpp/requirements/requirements-convert_legacy_llama.txt" ]; then
  log "[TRIT_NEG] Submodule still incomplete after update."
  exit 1
fi

step "ORIENT: Python environment"
if [ ! -d "$REPO_ROOT/.venv" ]; then
  run "$PYTHON_BIN" -m venv "$REPO_ROOT/.venv" || exit 1
fi
PY="$REPO_ROOT/.venv/bin/python"
PIP="$REPO_ROOT/.venv/bin/pip"
run "$PY" -m pip install --upgrade pip || exit 1
run "$PIP" install -r "$REPO_ROOT/requirements.txt" || {
  log "[TRIT_ZERO] Full requirements failed. Installing runtime minimum for Aegis server."
  run "$PIP" install fastapi uvicorn pydantic typing-extensions || exit 1
}
run "$PIP" install fastapi uvicorn || exit 1

step "DECIDE: locate or build llama-server"
LLAMA_SERVER="$(find_llama_server || true)"
if [ -n "$LLAMA_SERVER" ] && [ -x "$LLAMA_SERVER" ]; then
  log "Found llama-server: $LLAMA_SERVER"
else
  log "No llama-server found. Building with CMake."
  if command -v cmake >/dev/null 2>&1; then
    run cmake -B "$REPO_ROOT/build" -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ || {
      log "[TRIT_ZERO] Direct CMake configure failed."
    }
    run cmake --build "$REPO_ROOT/build" --config Release -j "$(sysctl -n hw.ncpu 2>/dev/null || echo 4)" || {
      log "[TRIT_ZERO] Direct CMake build failed."
    }
  fi
fi

LLAMA_SERVER="$(find_llama_server || true)"
if [ -z "$LLAMA_SERVER" ] || [ ! -x "$LLAMA_SERVER" ]; then
  log "[TRIT_ZERO] CMake did not produce llama-server. Trying setup_env.py if BitNet 2B model directory exists."
  if [ -d "$REPO_ROOT/models/BitNet-b1.58-2B-4T" ]; then
    run "$PY" "$REPO_ROOT/setup_env.py" -md "$REPO_ROOT/models/BitNet-b1.58-2B-4T" -q i2_s || true
  else
    log "Missing $REPO_ROOT/models/BitNet-b1.58-2B-4T, so setup_env.py fallback was skipped."
  fi
fi

LLAMA_SERVER="$(find_llama_server || true)"
if [ -z "$LLAMA_SERVER" ] || [ ! -x "$LLAMA_SERVER" ]; then
  log "[TRIT_NEG] No executable llama-server found after repair/build."
  log "Send back: $STATUS_FILE and $LOG_FILE"
  exit 1
fi
export LLAMA_SERVER_PATH="$LLAMA_SERVER"
log "Using LLAMA_SERVER_PATH=$LLAMA_SERVER_PATH"

step "ACT: validate Aegis model registry"
cd "$SRC_DIR" || exit 1
run "$PY" aegis_local_inference_server.py list || true
run "$PY" aegis_local_inference_server.py check-model "$MODEL_ALIAS" || {
  log "[TRIT_NEG] Model alias '$MODEL_ALIAS' is still not serve-ready."
  log "If this is a new GGUF, register it like:"
  log "  cd $SRC_DIR"
  log "  $PY aegis_local_inference_server.py add-model /absolute/path/to/model.gguf --alias $MODEL_ALIAS"
  exit 1
}

step "ACT: optional server smoke test"
if lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  log "[TRIT_ZERO] API port $API_PORT is already in use. Skipping launch."
else
  log "Starting detached server on API port $API_PORT, backend port $BACKEND_PORT."
  run "$PY" aegis_local_inference_server.py serve \
    --model "$MODEL_ALIAS" \
    --port "$API_PORT" \
    --backend-port "$BACKEND_PORT" \
    --tmux \
    --session aegis-local || {
      log "[TRIT_NEG] tmux launch failed. Try foreground:"
      log "  cd $SRC_DIR"
      log "  LLAMA_SERVER_PATH=\"$LLAMA_SERVER_PATH\" $PY aegis_local_inference_server.py serve --model $MODEL_ALIAS --port $API_PORT --backend-port $BACKEND_PORT"
      exit 1
    }
fi

step "VERIFY: endpoint"
sleep 3
if command -v curl >/dev/null 2>&1; then
  curl -s "http://127.0.0.1:$API_PORT/v1/models" | tee -a "$LOG_FILE" || true
  log ""
fi

write_status
log ""
log "[TRIT_POS] Recovery completed."
log "Status file: $STATUS_FILE"
log "Log file:    $LOG_FILE"
log ""
log "To attach:"
log "  cd $SRC_DIR && $PY aegis_local_inference_server.py tmux-attach --session aegis-local"
log "To stop:"
log "  cd $SRC_DIR && $PY aegis_local_inference_server.py tmux-stop --session aegis-local"
