#!/bin/bash
# ==============================================================================
# Aegis Unified Automation Pipeline v1.0
# Wellton Photonics | NDGi Core Engine Launcher
# Principle: Seeking Truth with Least Action
# ==============================================================================

set -euo pipefail

ROOT_DIR="/home/jsosa/workspace/BitNet"
JSON_SEED="$ROOT_DIR/photonx-jfs-ndgi.json"
LAUNCHER_SCRIPT="$ROOT_DIR/utils/aegis.sh"
MODEL_PATH="$ROOT_DIR/models/bitnet_b1_58-3B/ggml-model-i2_s.gguf"

echo -e "\033[0;34m[*] Phase 1: Configuring Runtime Environment Linkers...\033[0m"
# Statically declare the verified library paths to avoid dynamic lookup failures
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$ROOT_DIR/build/3rdparty/llama.cpp/src:$ROOT_DIR/build/3rdparty/llama.cpp/ggml/src

# Fast verification check
if ! ldd "$ROOT_DIR/build/bin/llama-server" | grep -q "libllama.so"; then
    echo -e "\033[0;31m[TRIT_NEG] Shared library verification broken. Check compilation space.\033[0m"
    exit 1
fi
echo -e "\033[0;32m[TRIT_POS] Dynamic linkers confirmed and locked.\033[0m"

echo -e "\033[0;34m[*] Phase 2: Verifying Weights and Models Matrix...\033[0m"
if [ ! -f "$MODEL_PATH" ]; then
    echo -e "\033[0;33m[TRIT_ZERO] Target weight binary missing at: $MODEL_PATH\033[0m"
    echo "Searching root directory for your GGUF model file..."
    FOUND_MODEL=$(find "$ROOT_DIR" -name "ggml-model-i2_s.gguf" -print -quit)
    
    if [ -n "$FOUND_MODEL" ]; then
        echo -e "\033[0;32m[*] Found weights at $FOUND_MODEL. Relocating to expected pathing structure...\033[0m"
        mkdir -p "$(dirname "$MODEL_PATH")"
        cp "$FOUND_MODEL" "$MODEL_PATH"
    else
        echo -e "\033[0;31m[TRIT_NEG] Aborting: 'ggml-model-i2_s.gguf' not found in workspace tree.\033[0m"
        exit 1
    fi
fi
echo -e "\033[0;32m[TRIT_POS] Ternary model binary verified at destination path.\033[0m"

echo -e "\033[0;34m[*] Phase 3: Launching 1.58-Bit Ternary Inference Server (Background Process)...\033[0m"
# Activate your python virtual environment securely
source "$ROOT_DIR/venv/bin/activate"

# Start the python engine execution loop as a decoupled background service
python3 "$ROOT_DIR/run_inference_server.py" --port 8080 > "$ROOT_DIR/logs/server_output.log" 2>&1 &
SERVER_PID=$!

# Trap sequence ensures the background server terminates if this script breaks early
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

echo -e "\033[0;34m[*] Waiting for port 8080 to stabilize and accept handshakes...\033[0m"
for i in {1..15}; do
    if curl -s http://127.0.0.1:8080/v1/models &>/dev/null || grep -q "HTTP server is listening" "$ROOT_DIR/logs/server_output.log" 2>/dev/null; then
        echo -e "\033[0;32m[TRIT_POS] Local Inference Server is alive and listening.\033[0m"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "\033[0;31m[TRIT_NEG] Server initialization timed out. Inspection log tail:\033[0m"
        tail -n 10 "$ROOT_DIR/logs/server_output.log"
        exit 1
    fi
    sleep 1
done

echo -e "\033[0;34m[*] Phase 4: Setting Permissions and Initializing Identity Graph Ingestion...\033[0m"
chmod +x "$LAUNCHER_SCRIPT"

if [ -f "$JSON_SEED" ]; then
    # Ingest the personality profile directly into the freshly spawned discrete logic loop
    "$LAUNCHER_SCRIPT" "$JSON_SEED"
else
    echo -e "\033[0;33m[TRIT_ZERO] No seed graph found at $JSON_SEED. Server left active on port 8080.\033[0m"
fi

# Disown background process so the port stays up and active for subsequent CLI prompts
echo -e "\033[0;32m[TRIT_POS] Aegis Core initialized. System running on PID $SERVER_PID. Ready for commands.\033[0m"
disown $SERVER_PID
trap - EXIT
