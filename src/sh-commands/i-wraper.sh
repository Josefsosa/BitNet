#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# Aegis Integrated 4-Pane Workspace — Wellton Photonics
# Coordinated Mainframe Layout & Native Process Layer Isolation
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

SESSION_NAME="aegis-wp1"
WORKSPACE_DIR="/home/jsosa/workspace/BitNet/src"

# Enforce a completely clean environment state by killing ghost threads
pkill -f "run_inference_server.py" || true
pkill -f "llama-server" || true
fuser -k 8080/tcp || true

# Explicitly export shared object linker paths for local weight binaries
export LD_LIBRARY_PATH="/home/jsosa/workspace/BitNet/build/bin:/home/jsosa/workspace/BitNet/build:/home/jsosa/workspace/BitNet/build/3rdparty/llama.cpp/src:/home/jsosa/workspace/BitNet/build/3rdparty/llama.cpp/ggml/src:${LD_LIBRARY_PATH:-}"

if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  # 1. Create the main human user command terminal (Pane 0)
  tmux new-session -d -s "$SESSION_NAME" -c "$WORKSPACE_DIR" -n "Aegis-Dev"

  # 2. Split horizontally to build the right-hand stack column (Initial Pane 1)
  tmux split-window -h -c "$WORKSPACE_DIR" -p 45
  
  # 3. Split Pane 1 vertically to create your Host Monitor (Pane 2)
  tmux split-window -v -c "$WORKSPACE_DIR" -p 66

  # 4. Split Pane 2 vertically to isolate your Local Backend Engine (Pane 3)
  tmux split-window -v -c "$WORKSPACE_DIR" -p 50

  # 5. Enable high-fidelity mouse selection across all 4 boundaries instantly
  tmux set -t "$SESSION_NAME" mouse on

  # 6. Setup Pane 0: Wide open shell context for manual testing and tool calls
  tmux send-keys -t "$SESSION_NAME:0.0" "clear && echo -e '=== AEGIS INTEGRATED WORKSPACE ===\nUse this console window for repository tasks and manual commits.\n'" C-m

  # 7. Setup Pane 1: Fire up the live interactive Aegis AI with your JFS persona prompt
  tmux send-keys -t "$SESSION_NAME:0.1" "bash ./launch_aegis.sh jfs" C-m

  # 8. Setup Pane 2: Initialize un-profiled Aegis passive telemetry metrics loop
  tmux send-keys -t "$SESSION_NAME:0.2" "sleep 2 && python3 ./aegis-cli.py --mode ops" C-m

  # 9. Setup Pane 3: Launch the underlying raw local C++ llama-server engine wrapper
  tmux send-keys -t "$SESSION_NAME:0.3" "python3 run_inference_server.py --port 8080" C-m
  
  # 10. Balance final focus cleanly back to Pane 0 on the left
  tmux select-pane -t "$SESSION_NAME:0.0"
fi

exec tmux attach-session -t "$SESSION_NAME"