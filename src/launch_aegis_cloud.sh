#!/bin/bash
# =============================================================================
# launch_aegis_cloud.sh — Aegis Model Server Launcher
# Wellton Photonics | Mill Creek Lab
# Protocol: 4.2.2-TRINARY-CLOUD | Target: Jose F. Sosa (jfs)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/aegis_server.log"

# 1. Check for Gemini credentials
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" == "REPLACE_WITH_YOUR_SECURED_API_KEY" ]; then
    echo "[-] Error: GEMINI_API_KEY environment variable is not set."
    echo "    Please get a key from Google AI Studio (aistudio.google.com)"
    echo "    and run: export GEMINI_API_KEY=\"your_key_here\""
    exit 1
fi

echo "[+] Credentials verified: GEMINI_API_KEY is active."

# 2. Clear lingering ports
echo "[*] Cleaning socket allocations on port 5000..."
fuser -k 5000/tcp 2>/dev/null || kill -9 $(lsof -t -i:5000) 2>/dev/null || true

# 3. Spin up local server (HYBRID routing mode)
echo "[*] Spinning up Aegis Local Router on Port 5000..."
python3 "$SCRIPT_DIR/aegis_server.py" serve \
    --port 5000 \
    --route-mode hybrid \
    --api-key "$GEMINI_API_KEY" > "$LOG_FILE" 2>&1 &

SERVER_PID=$!

# Give the server a moment to spin up
sleep 2

# Verify the process is still alive and socket is active
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[-] Error: aegis_server.py exited immediately. Log output:"
    cat "$LOG_FILE"
    exit 1
fi

if ! lsof -i:5000 > /dev/null 2>&1; then
    echo "[-] Error: Failed to bind port 5000. Check $LOG_FILE"
    exit 1
fi

echo "[+] Aegis Model Server started successfully (PID: $SERVER_PID)."
echo "[+] Listening on: http://localhost:5000"
echo "[+] OpenAI-compatible endpoint: http://localhost:5000/v1/chat/completions"
echo "[+] Log file: $LOG_FILE"
echo ""
echo "[*] Server running in background. To stop: kill $SERVER_PID"
