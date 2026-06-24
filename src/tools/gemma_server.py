#!/usr/bin/env python3
"""
Gemma 4 Local GPU Inference Server
Air-gapped, CUDA-accelerated FastAPI endpoint with dynamic model selection.

Usage:
    python gemma4_server.py                          # interactive model picker
    python gemma4_server.py --model gemma-4-12b-it   # direct launch by alias
    python gemma4_server.py --list                   # show registered models

Wellton Photonics — Aegis Local Inference Stack
"""

import os
import sys
import time
import argparse

import torch
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM

# ==========================================
# STRICT AIR-GAPPED OFFLINE SAFEGUARDS
# ==========================================
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

# ==========================================
# MODEL REGISTRY — add models here
# ==========================================
MODELS_ROOT = os.getenv("AEGIS_MODELS_ROOT", "/home/jsosa/workspace/BitNet/models")

MODEL_REGISTRY = {
    "gemma-4-12b-it": {
        "path": f"{MODELS_ROOT}/gemma-4-12b-it",
        "description": "Gemma 4 12B Instruct (Google)",
        "dtype": "bfloat16",
        "owned_by": "google",
    },
    "bitnet-b1.58-2b": {
        "path": f"{MODELS_ROOT}/BitNet-b1.58-2B-4T",
        "description": "BitNet b1.58 2B-4T (Microsoft)",
        "dtype": "float32",  # ternary weights, no half-precision benefit
        "owned_by": "microsoft",
    },
    # Add new models here:
    # "model-alias": {
    #     "path": f"{MODELS_ROOT}/model-directory",
    #     "description": "Human-readable name",
    #     "dtype": "bfloat16",
    #     "owned_by": "org",
    # },
}

# ==========================================
# MODEL SELECTION
# ==========================================
def resolve_dtype(dtype_str: str) -> torch.dtype:
    return {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[dtype_str]


def select_model_interactive() -> str:
    """Present a numbered menu and return the chosen alias."""
    entries = list(MODEL_REGISTRY.items())
    print("\n╔══════════════════════════════════════════╗")
    print("║       AEGIS LOCAL MODEL SELECTOR         ║")
    print("╠══════════════════════════════════════════╣")
    for i, (alias, meta) in enumerate(entries, 1):
        exists = "✓" if os.path.isdir(meta["path"]) else "✗"
        print(f"║  [{i}] {exists}  {alias:<28} ║")
        print(f"║       {meta['description']:<34} ║")
    print("╚══════════════════════════════════════════╝")

    while True:
        try:
            choice = int(input(f"\nSelect model [1-{len(entries)}]: "))
            if 1 <= choice <= len(entries):
                alias = entries[choice - 1][0]
                print(f"→ Selected: {alias}")
                return alias
        except (ValueError, KeyboardInterrupt):
            pass
        print("Invalid selection. Try again.")


def parse_args() -> str:
    """Parse CLI args and return the selected model alias."""
    parser = argparse.ArgumentParser(description="Aegis Local Inference Server")
    parser.add_argument("--model", "-m", type=str, help="Model alias from registry")
    parser.add_argument("--list", "-l", action="store_true", help="List available models")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Server port (default: 8080)")
    args = parser.parse_args()

    if args.list:
        for alias, meta in MODEL_REGISTRY.items():
            exists = "✓" if os.path.isdir(meta["path"]) else "✗"
            print(f"  {exists}  {alias:<24} → {meta['path']}")
        sys.exit(0)

    if args.model:
        if args.model not in MODEL_REGISTRY:
            print(f"Unknown model '{args.model}'. Available: {', '.join(MODEL_REGISTRY.keys())}")
            sys.exit(1)
        return args.model, args.port

    return select_model_interactive(), args.port


# Global state — set after arg parsing
SELECTED_ALIAS: str = ""
SELECTED_META: dict = {}
PORT: int = 8080
tokenizer = None
model = None

# ==========================================
# FASTAPI LIFESPAN
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global tokenizer, model
    meta = SELECTED_META
    model_path = meta["path"]
    target_dtype = resolve_dtype(meta["dtype"])

    print(f"\n[AEGIS] Loading '{SELECTED_ALIAS}' from {model_path}")
    print(f"[AEGIS] dtype={meta['dtype']}  device_map=auto  flash_attn=eager")

    if not os.path.isdir(model_path):
        print(f"\n[FATAL] Model path does not exist: {model_path}")
        print("Download the model or update MODEL_REGISTRY with the correct path.")
        sys.exit(1)

    t0 = time.time()
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)

        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            torch_dtype=target_dtype,       # ← FIXED: was 'dtype' (silently ignored → float32)
            local_files_only=True,
            attn_implementation="eager",     # use "flash_attention_2" if flash-attn is installed
        )

        # Optional: torch.compile for steady-state speedup (adds ~30s warmup)
        # Uncomment after verifying base inference works:
        # model = torch.compile(model, mode="reduce-overhead")

        elapsed = time.time() - t0
        vram = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
        print(f"[AEGIS] Model loaded in {elapsed:.1f}s  |  VRAM: {vram:.1f} GB")
        print(f"[AEGIS] Inference endpoint ready at http://127.0.0.1:{PORT}/v1/chat/completions\n")

    except Exception as e:
        print(f"\n[FATAL] Model load failed: {e}")
        print("Verify model files are complete and path is correct.")
        raise

    yield

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("[AEGIS] Shutdown complete.")


# ==========================================
# API SCHEMA
# ==========================================
app = FastAPI(title="Aegis Local Inference", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "local"
    messages: List[Message]
    temperature: float = 0.7
    max_tokens: int = 512


# ==========================================
# ENDPOINTS
# ==========================================
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    if not model or not tokenizer:
        raise HTTPException(status_code=503, detail="Model loading or unavailable.")

    try:
        conversation = [{"role": m.role, "content": m.content} for m in request.messages]
        prompt = tokenizer.apply_chat_template(
            conversation, tokenize=False, add_generation_prompt=True
        )

        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature if request.temperature > 0 else 1.0,
                do_sample=request.temperature > 0,
                pad_token_id=tokenizer.eos_token_id,
            )

        input_len = inputs.input_ids.shape[1]
        response_text = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)

        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": SELECTED_ALIAS,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text.strip()},
                    "finish_reason": "stop",
                }
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def get_models():
    return {
        "object": "list",
        "data": [
            {
                "id": alias,
                "object": "model",
                "created": int(time.time()),
                "owned_by": meta["owned_by"],
            }
            for alias, meta in MODEL_REGISTRY.items()
        ],
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": SELECTED_ALIAS,
        "vram_gb": round(torch.cuda.memory_allocated() / 1e9, 2) if torch.cuda.is_available() else 0,
    }


# ==========================================
# ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    SELECTED_ALIAS, PORT = parse_args()
    SELECTED_META = MODEL_REGISTRY[SELECTED_ALIAS]

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)

# # To run this Gemma 4 server run this command
# # 1. Navigate to your root workspace directory (up one level from src)
# cd ~/workspace/BitNet

# # 2. Create a clean Python 3.10+ virtual environment named '.venv'
# python3 -m venv .venv

# # 3. Activate the virtual environment
# source .venv/bin/activate

# # 4. Upgrade pip inside your virtual environment
# pip install --upgrade pip

# # 5. Install GPU-optimized PyTorch (with CUDA 12.1 alignment)
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# # 6. Install FastAPI, Uvicorn, Transformers, and Accelerate
# pip install fastapi uvicorn transformers accelerate pydantic hf_transfer

# export LOCAL_MODEL_PATH="/home/jsosa/workspace/BitNet/models/gemma-4-12b-it"
# ../.venv/bin/python3 gemma_server.py