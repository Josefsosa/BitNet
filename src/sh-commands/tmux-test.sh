#!/bin/bash
# ==============================================================================
# Aegis Tmux Multi-Terminal Orchestration Pipeline
# ==============================================================================

set -euo pipefail

SESSION_NAME="aegis-bitnet"
ROOT_DIR="/home/jsosa/workspace/BitNet"
JSON_SEED="$ROOT_DIR/photonx-jfs-ndgi.json"
LAUNCHER_SCRIPT="$ROOT_DIR/utils/aegis.sh"

# 1. Kill any existing session with the same name to prevent overlaps
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "[*] Existing Tmux session found. Killing '$SESSION_NAME'..."
    tmux kill-session -t "$SESSION_NAME"
fi

# 2. Check and clear port 8080 if lingering from previous manual runs
if lsof -i :8080 -t >/dev/null; then
    echo "[*] Port 8080 is busy. Clearing legacy inference workers..."
    kill $(lsof -i :8080 -t) 2>/dev/null || true
    sleep 1
fi

echo "[*] Spawning Aegis Core Tmux Orchestrator..."

# 3. Start a new detached Tmux session (Window 0: Server Log Console)
tmux new-session -d -s "$SESSION_NAME" -n "Aegis-Server" -c "$ROOT_DIR"

# 4. Phase 1 & 2: Environment Config passed directly to the environment
# We send the export string so it lives inside the target pane's environment
tmux send-keys -t "$SESSION_NAME:0" "export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:$ROOT_DIR/build/3rdparty/llama.cpp/src:$ROOT_DIR/build/3rdparty/llama.cpp/ggml/src" C-m
tmux send-keys -t "$SESSION_NAME:0" "source $ROOT_DIR/venv/bin/activate" C-m

# Launch the live 1.58-Bit inference engine directly in Pane 0 (No background decoupling needed!)
tmux send-keys -t "$SESSION_NAME:0" "python3 $ROOT_DIR/run_inference_server.py --port 8080" C-m

# 5. Create Window 1: Interactive Workspace & CLI Engine Ingestion
tmux new-window -t "$SESSION_NAME" -n "Aegis-CLI" -c "$ROOT_DIR"

# Wait actively for port 8080 to stabilize before triggering Phase 4 in the CLI window
echo "[*] Waiting for 1.58-Bit Ternary Inference Server to spin up..."
for i in {1..15}; do
    if curl -s http://127.0.0.1:8080/v1/models &>/dev/null; then
        echo -e "\033[0;32m[TRIT_POS] Local Inference Server is alive.\033[0m"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "\033[0;31m[TRIT_NEG] Server setup timed out. Attaching session for inspection.\033[0m"
        tmux attach-session -t "$SESSION_NAME"
        exit 1
    fi
    sleep 1
done

# 6. Phase 4: Handle Graph Ingestion in Window 1 (Aegis-CLI)
tmux send-keys -t "$SESSION_NAME:1" "chmod +x $LAUNCHER_SCRIPT" C-m

if [ -f "$JSON_SEED" ]; then
    echo "[*] Injecting seed graph identity profile..."
    tmux send-keys -t "$SESSION_NAME:1" "$LAUNCHER_SCRIPT $JSON_SEED" C-m
else
    echo -e "\033[0;33m[TRIT_ZERO] No seed graph detected. Dropping to default workspace shell.\033[0m"
fi

# 7. Open up the workspace window layout automatically
tmux select-window -t "$SESSION_NAME:1"
tmux attach-session -t "$SESSION_NAME"