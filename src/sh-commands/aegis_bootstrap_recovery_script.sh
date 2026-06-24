#!/usr/bin/env bash
# ==============================================================================
# ARCHITECT: Jose F. Sosa
# PERSONA: Aegis Code (Cloud Recovery Utility)
# PROTOCOL: 4.2.1-TRINARY [WP1-MANIFOLD-ALPHA]
# DESCRIPTION: Automates verification, compilation, path locating, and health
#              checking for the BitNet/llama-server backend and Aegis proxy.
# ==============================================================================

set -euo pipefail

# --- Configurations ---
WORKSPACE_DIR="$HOME/workspace/BitNet"
DEFAULT_MODEL="/home/jsosa/models/your_model.gguf"
MODELS_DIR="/home/jsosa/models"
PORT=8080
THREADS=6
CTX_SIZE=8192

# Stylized Output UI
info() { echo -e "\e[34m[AEGIS INFO]\e[0m $*"; }
success() { echo -e "\e[32m[AEGIS SUCCESS]\e[0m $*"; }
warn() { echo -e "\e[33m[AEGIS WARNING]\e[0m $*"; }
error() { echo -e "\e[31m[AEGIS ERROR]\e[0m $*"; exit 1; }

echo "========================================================="
echo "   AEGIS SYSTEM RESTORATION & INFRASTRUCTURE INTEGRITY   "
echo "========================================================="

# 1. Verify Directory Structure
if [ ! -d "$WORKSPACE_DIR" ]; then
    error "BitNet workspace directory not found at: $WORKSPACE_DIR"
fi
info "Verified workspace directory: $WORKSPACE_DIR"

# 2. Check Model File Availability & Dynamic Search
if [ ! -f "$DEFAULT_MODEL" ]; then
    warn "Target model placeholder not found at: $DEFAULT_MODEL"
    
    if [ -d "$MODELS_DIR" ]; then
        info "Scanning directory '$MODELS_DIR' for available GGUF files..."
        
        # Use find to populate array of gguf files safely
        IFS=$'\n' read -r -d '' -a FOUND_MODELS < <(find "$MODELS_DIR" -maxdepth 2 -type f -name "*.gguf" 2>/dev/null) || true
        
        if [ ${#FOUND_MODELS[@]} -gt 0 ]; then
            success "Discovered ${#FOUND_MODELS[@]} available model(s):"
            for i in "${!FOUND_MODELS[@]}"; do
                echo "  [$((i+1))] $(basename "${FOUND_MODELS[i]}")"
            done
            echo ""
            echo -n "Select a model index to launch (1-${#FOUND_MODELS[@]}) or press Enter for manual path: "
            read -r selection
            
            if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#FOUND_MODELS[@]}" ]; then
                DEFAULT_MODEL="${FOUND_MODELS[$((selection-1))]}"
            fi
        fi
    fi
fi

# Fallback to manual input if default/selection is still invalid
if [ ! -f "$DEFAULT_MODEL" ]; then
    warn "No valid model selected yet."
    echo -n "Please type the absolute path to your active .gguf model: "
    read -r user_model_path
    if [ -n "$user_model_path" ]; then
        DEFAULT_MODEL="$user_model_path"
    fi
fi

# Final validation gate
if [ -f "$DEFAULT_MODEL" ]; then
    success "Verified model asset: $DEFAULT_MODEL"
else
    error "Cannot proceed without a valid model file target."
fi

# 3. Locate llama-server Binary
info "Searching for compiled llama-server binary in $WORKSPACE_DIR..."
FOUND_SERVER=$(find "$WORKSPACE_DIR" -type f -name "llama-server" -perm /111 2>/dev/null | head -n 1)

if [ -n "$FOUND_SERVER" ]; then
    success "Located llama-server binary at: $FOUND_SERVER"
else
    warn "llama-server binary was NOT found in the workspace."
    echo -n "Would you like to compile/recompile BitNet with server support now? [y/N]: "
    read -r compile_choice
    if [[ "$compile_choice" =~ ^[Yy]$ ]]; then
        info "Initiating compilation sequence..."
        cd "$WORKSPACE_DIR"
        
        # Ensure build directory exists
        mkdir -p build
        cd build
        
        # Configure with server compilation enabled
        info "Running CMake configuration..."
        cmake .. -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_SERVER=ON
        
        info "Compiling targets using $(nproc) threads..."
        make -j"$(nproc)"
        
        FOUND_SERVER=$(find "$WORKSPACE_DIR" -type f -name "llama-server" -perm /111 2>/dev/null | head -n 1)
        if [ -n "$FOUND_SERVER" ]; then
            success "Successfully compiled! Binary located at: $FOUND_SERVER"
        else
            error "Compilation finished, but llama-server executable could not be resolved."
        fi
    else
        error "Unable to start server: executable binary is missing."
    fi
fi

# 4. Check Port Occupancy
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    warn "Port $PORT is already in use."
    echo "Currently listening process details:"
    lsof -i :$PORT
    echo -n "Would you like to kill the process blocking port $PORT? [y/N]: "
    read -r kill_choice
    if [[ "$kill_choice" =~ ^[Yy]$ ]]; then
        lsof -t -i:$PORT | xargs kill -9
        success "Port $PORT has been cleared."
    else
        error "Port $PORT is occupied. Please assign a different port or clear the bind manually."
    fi
fi

# 5. Launch Backend Inference Engine
info "Starting llama-server with the following parameters:"
echo "   - Model:    $DEFAULT_MODEL"
echo "   - Port:     $PORT"
echo "   - Context:  $CTX_SIZE"
echo "   - Threads:  $THREADS"
echo "========================================================="

# Execute the server from its absolute directory to prevent context directory issues
SERVER_DIR=$(dirname "$FOUND_SERVER")
cd "$SERVER_DIR"

# Launching server
set +e
./llama-server \
  --model "$DEFAULT_MODEL" \
  --port "$PORT" \
  --ctx-size "$CTX_SIZE" \
  --flash-attn \
  --threads "$THREADS"

# Catch failures
if [ $? -ne 0 ]; then
    error "llama-server subprocess failed to start or terminated unexpectedly."
fi
