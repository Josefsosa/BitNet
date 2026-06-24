#!/usr/bin/env bash
# Aegis local setup/recovery for Harold's macOS BitNet workspace.
# Run from anywhere inside the BitNet repo:
#   bash scripts/harold_aegis_local_recovery.sh
#   bash scripts/harold_aegis_local_recovery.sh gemma4-coding-q2-k

set -u

MODEL_ALIAS="${1:-}"
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
  elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    printf '%s\n' "$REPO_ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    return 1
  fi
}

python_minor_version() {
  "$1" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "unknown"
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
  if [ -x "$REPO_ROOT/build/llama-server" ]; then
    printf '%s\n' "$REPO_ROOT/build/llama-server"
    return 0
  fi
  if command -v llama-server >/dev/null 2>&1; then
    command -v llama-server
    return 0
  fi
  find "$REPO_ROOT" -type f -name llama-server -perm +111 2>/dev/null | head -n 1
}

ensure_runtime_imports() {
  "$PY" - <<'PYIMPORT'
import importlib
missing = []
for name in ("fastapi", "uvicorn"):
    try:
        importlib.import_module(name)
    except Exception:
        missing.append(name)
if missing:
    raise SystemExit("missing:" + ",".join(missing))
print("fastapi/uvicorn import check: ok")
PYIMPORT
}

ready_model_aliases() {
  cd "$SRC_DIR" || return 1
  LLAMA_SERVER_PATH="${LLAMA_SERVER_PATH:-}" "$PY" aegis_local_inference_server.py list 2>/dev/null \
    | awk 'NR > 4 && $2 == "yes" {print $1}'
}

select_model_alias() {
  cd "$SRC_DIR" || return 1
  log "Available serve-ready local models:"
  LLAMA_SERVER_PATH="${LLAMA_SERVER_PATH:-}" "$PY" aegis_local_inference_server.py list 2>&1 | tee -a "$LOG_FILE"

  mapfile -t aliases < <(ready_model_aliases)
  if [ "${#aliases[@]}" -eq 0 ]; then
    log "[TRIT_NEG] No serve-ready local GGUF models were found."
    return 1
  fi

  if [ -n "$MODEL_ALIAS" ]; then
    for alias in "${aliases[@]}"; do
      if [ "$alias" = "$MODEL_ALIAS" ]; then
        log "Selected model from argument: $MODEL_ALIAS"
        return 0
      fi
    done
    log "[TRIT_ZERO] Requested alias '$MODEL_ALIAS' is not currently ready. Choose from the ready models below."
  fi

  if [ ! -t 0 ]; then
    MODEL_ALIAS="${aliases[0]}"
    log "No interactive terminal detected. Defaulting to first ready model: $MODEL_ALIAS"
    return 0
  fi

  log ""
  log "Choose a model to serve:"
  local i=1
  for alias in "${aliases[@]}"; do
    log "  $i) $alias"
    i=$((i + 1))
  done

  printf "Model number [1]: "
  read -r choice
  choice="${choice:-1}"
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#aliases[@]}" ]; then
    log "[TRIT_NEG] Invalid model selection: $choice"
    return 1
  fi

  MODEL_ALIAS="${aliases[$((choice - 1))]}"
  log "Selected model: $MODEL_ALIAS"
  return 0
}

write_status() {
  {
    echo "Aegis local recovery status"
    echo "repo=$REPO_ROOT"
    echo "model_alias=${MODEL_ALIAS:-<none>}"
    echo "api_port=$API_PORT"
    echo "backend_port=$BACKEND_PORT"
    echo
    echo "date:"
    date
    echo
    echo "git_head:"
    git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || true
    echo
    echo "git_status:"
    git -C "$REPO_ROOT" status --short --branch 2>/dev/null || true
    echo
    echo "python:"
    if [ -n "${PY:-}" ] && [ -x "$PY" ]; then
      "$PY" --version 2>&1 || true
    elif command -v python3 >/dev/null 2>&1; then
      python3 --version 2>&1 || true
    fi
    echo
    echo "fastapi_uvicorn:"
    if [ -n "${PY:-}" ] && [ -x "$PY" ]; then
      ensure_runtime_imports 2>&1 || true
    fi
    echo
    echo "llama_cpp_requirements:"
    ls -l "$REPO_ROOT/3rdparty/llama.cpp/requirements/requirements-convert_legacy_llama.txt" 2>&1 || true
    echo
    echo "llama_server:"
    find_llama_server 2>/dev/null || true
    echo
    echo "model_list:"
    if [ -n "${PY:-}" ] && [ -x "$PY" ] && [ -f "$SRC_DIR/aegis_local_inference_server.py" ]; then
      (cd "$SRC_DIR" && LLAMA_SERVER_PATH="${LLAMA_SERVER_PATH:-}" "$PY" aegis_local_inference_server.py list) 2>&1 || true
    fi
    echo
    echo "last_160_log_lines:"
    tail -n 160 "$LOG_FILE" 2>/dev/null || true
  } > "$STATUS_FILE"
}

trap write_status EXIT

step "OBSERVE: workspace"
log "Repo root: $REPO_ROOT"
log "Requested model alias: ${MODEL_ALIAS:-<select from ready models>}"
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
PY_VER="$(python_minor_version "$PYTHON_BIN")"
case "$PY_VER" in
  3.10|3.11|3.12)
    ;;
  *)
    log "[TRIT_ZERO] Python $PY_VER selected. Python 3.10/3.11 is safer for this repo."
    if command -v brew >/dev/null 2>&1 && ! command -v python3.11 >/dev/null 2>&1; then
      log "Attempting: brew install python@3.11"
      run brew install python@3.11 || log "[TRIT_ZERO] brew could not install python@3.11 automatically."
      if command -v python3.11 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3.11)"
        log "Python switched to: $PYTHON_BIN"
        "$PYTHON_BIN" --version 2>&1 | tee -a "$LOG_FILE"
      fi
    fi
    ;;
esac

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

step "ORIENT: repair llama.cpp only"
if [ ! -f "$REPO_ROOT/3rdparty/llama.cpp/requirements/requirements-convert_legacy_llama.txt" ]; then
  log "llama.cpp requirements are missing. Initializing only 3rdparty/llama.cpp."
  run git submodule sync 3rdparty/llama.cpp || true
  run git submodule update --init --recursive 3rdparty/llama.cpp || {
    log "[TRIT_ZERO] Targeted submodule update failed. The unrelated aegis_ternary-math-model gitlink will be ignored."
  }
else
  log "llama.cpp requirements file exists."
fi

if [ ! -f "$REPO_ROOT/3rdparty/llama.cpp/requirements/requirements-convert_legacy_llama.txt" ]; then
  log "[TRIT_ZERO] llama.cpp requirements are still missing. Full requirements install will be skipped."
fi

step "ORIENT: Python environment and FastAPI"
if [ ! -d "$REPO_ROOT/.venv" ]; then
  run "$PYTHON_BIN" -m venv "$REPO_ROOT/.venv" || exit 1
fi
PY="$REPO_ROOT/.venv/bin/python"
PIP="$REPO_ROOT/.venv/bin/pip"
run "$PY" -m pip install --upgrade pip || exit 1

if [ -f "$REPO_ROOT/3rdparty/llama.cpp/requirements/requirements-convert_legacy_llama.txt" ]; then
  run "$PIP" install -r "$REPO_ROOT/requirements.txt" || {
    log "[TRIT_ZERO] Full requirements failed. Installing runtime minimum for Aegis server."
    run "$PIP" install fastapi uvicorn pydantic typing-extensions || exit 1
  }
else
  run "$PIP" install fastapi uvicorn pydantic typing-extensions || exit 1
fi
run "$PIP" install fastapi uvicorn || exit 1
if ! ensure_runtime_imports 2>&1 | tee -a "$LOG_FILE"; then
  log "[TRIT_NEG] FastAPI/Uvicorn import check failed."
  exit 1
fi

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
  log "[TRIT_ZERO] No local llama-server found. Trying Homebrew llama.cpp as a final fallback."
  if command -v brew >/dev/null 2>&1; then
    run brew install llama.cpp || true
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

step "ACT: choose and validate model"
cd "$SRC_DIR" || exit 1
select_model_alias || {
  log "[TRIT_NEG] Could not select a serve-ready model."
  exit 1
}

run "$PY" aegis_local_inference_server.py check-model "$MODEL_ALIAS" || {
  log "[TRIT_NEG] Model alias '$MODEL_ALIAS' is still not serve-ready."
  log "If this is a new GGUF, register it like:"
  log "  cd $SRC_DIR"
  log "  $PY aegis_local_inference_server.py add-model /absolute/path/to/model.gguf --alias $MODEL_ALIAS"
  exit 1
}

step "ACT: launch server"
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
log "Selected model: $MODEL_ALIAS"
log "Status file: $STATUS_FILE"
log "Log file:    $LOG_FILE"
log ""
log "To attach:"
log "  cd $SRC_DIR && $PY aegis_local_inference_server.py tmux-attach --session aegis-local"
log "To stop:"
log "  cd $SRC_DIR && $PY aegis_local_inference_server.py tmux-stop --session aegis-local"
