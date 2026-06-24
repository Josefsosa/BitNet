#!/usr/bin/env python3
"""
Aegis Local Inference Server — Unified Backend
Supports transformers (safetensors/folders) and existing llama.cpp (GGUF) models
through a single /v1/chat/completions endpoint.

GGUF backend auto-discovers your existing llama-server binary — no rebuild needed.

Usage:
    python aegis_server.py                        # interactive model picker
    python aegis_server.py -m gemma-4-12b-gguf    # direct launch by alias
    python aegis_server.py --list                  # show registered models
    python aegis_server.py -m bitnet-2b -p 9090   # custom port

Wellton Photonics — Aegis Local Inference Stack
"""

import os
import sys
import time
import shutil
import signal
import socket
import argparse
import subprocess
from enum import Enum
from abc import ABC, abstractmethod
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

import httpx

# ==========================================
# STRICT AIR-GAPPED OFFLINE SAFEGUARDS
# ==========================================
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"


# ==========================================
# BACKEND ENUM
# ==========================================
class Backend(str, Enum):
    TRANSFORMERS = "transformers"
    LLAMACPP = "llama.cpp"


# ==========================================
# MODEL REGISTRY
# ==========================================
MODELS_ROOT = os.getenv("AEGIS_MODELS_ROOT", "/home/jsosa/workspace/BitNet/models")

# Where to look for existing llama-server builds (searched in order)
LLAMA_SERVER_SEARCH_PATHS = [
    os.getenv("LLAMA_SERVER_PATH", ""),
    "/home/jsosa/workspace/llama-cpp-main/build/bin/llama-server",
    "/home/jsosa/workspace/oakland-cli/llama.cpp/build/bin/llama-server",
    "/home/jsosa/workspace/llama-cpp-main/build/llama-server",
    "/home/jsosa/workspace/oakland-cli/llama.cpp/build/llama-server",
]

# Internal port for llama-server subprocess (not exposed externally)
LLAMA_BACKEND_PORT = 8090

MODEL_REGISTRY = {
    # ── Transformers-backend models (folders) ──
    "bitnet-b1.58-2b": {
        "path": f"{MODELS_ROOT}/BitNet-b1.58-2B-4T",
        "backend": Backend.TRANSFORMERS,
        "description": "BitNet b1.58 2B-4T (Microsoft)",
        "dtype": "float32",
        "owned_by": "microsoft",
    },
    "bitnet-b1.58-3b": {
        "path": f"{MODELS_ROOT}/bitnet_b1_58-3B",
        "backend": Backend.TRANSFORMERS,
        "description": "BitNet b1.58 3B (Microsoft)",
        "dtype": "float32",
        "owned_by": "microsoft",
    },
    "gemma-4-12b-it": {
        "path": f"{MODELS_ROOT}/gemma-4-12b-it",
        "backend": Backend.TRANSFORMERS,
        "description": "Gemma 4 12B IT (GPU Accelerated - local)",
        "dtype": "float16",
        "owned_by": "google",
    },

    # ── llama.cpp-backend models (GGUF, uses existing llama-server) ──
    "gemma-4-12b-gguf": {
        "path": f"{MODELS_ROOT}/gemma-4-12B-Queen-it-qat-q4_0-unquantized.i1-IQ2_XXS.gguf",
        "backend": Backend.LLAMACPP,
        "description": "Gemma 4 12B Queen IQ2_XXS (GGUF)",
        "n_gpu_layers": -1,
        "n_ctx": 4096,
        "owned_by": "google",
    },
    "llama-3-8b-gguf": {
        "path": f"{MODELS_ROOT}/llama-3-8b-Instruct-Q4_K_M.gguf",
        "backend": Backend.LLAMACPP,
        "description": "Llama 3 8B Instruct Q4_K_M (GGUF)",
        "n_gpu_layers": -1,
        "n_ctx": 4096,
        "owned_by": "meta",
    },
    "qwen2.5-coder-7b-gguf": {
        "path": f"{MODELS_ROOT}/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "backend": Backend.LLAMACPP,
        "description": "Qwen 2.5 Coder 7B Instruct Q4_K_M (GGUF)",
        "n_gpu_layers": -1,
        "n_ctx": 4096,
        "owned_by": "alibaba",
    },
}


# ==========================================
# ABSTRACT INFERENCE ENGINE
# ==========================================
class InferenceEngine(ABC):
    @abstractmethod
    def load(self, meta: dict) -> None:
        ...

    @abstractmethod
    async def generate(self, messages: list, temperature: float, max_tokens: int,
                       stop: Optional[List[str]] = None) -> str:
        ...

    @abstractmethod
    def vram_gb(self) -> float:
        ...

    @abstractmethod
    def cleanup(self) -> None:
        ...


# ==========================================
# TRANSFORMERS ENGINE
# ==========================================
class TransformersEngine(InferenceEngine):
    def __init__(self):
        self.model = None
        self.tokenizer = None

    def _resolve_dtype(self, dtype_str: str):
        import torch
        return {"float32": torch.float32, "float16": torch.float16, "bfloat16": torch.bfloat16}[dtype_str]

    def load(self, meta: dict) -> None:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        target_dtype = self._resolve_dtype(meta["dtype"])
        self.tokenizer = AutoTokenizer.from_pretrained(meta["path"], local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            meta["path"],
            device_map="auto",
            torch_dtype=target_dtype,
            local_files_only=True,
            attn_implementation="eager",
        )

    async def generate(self, messages: list, temperature: float, max_tokens: int,
                       stop: Optional[List[str]] = None) -> str:
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        # Build stopping criteria from stop token strings
        stopping_criteria = StoppingCriteriaList()
        if stop:
            stop_token_ids = []
            for s in stop:
                ids = self.tokenizer.encode(s, add_special_tokens=False)
                if ids:
                    stop_token_ids.append(ids)

            if stop_token_ids:
                class StopOnTokens(StoppingCriteria):
                    def __call__(self, input_ids, scores, **kwargs):
                        for stop_ids in stop_token_ids:
                            slen = len(stop_ids)
                            if input_ids.shape[1] >= slen:
                                if input_ids[0, -slen:].tolist() == stop_ids:
                                    return True
                        return False

                stopping_criteria.append(StopOnTokens())

        # Safely resolve pad token id to avoid crashes
        pad_token_id = self.tokenizer.pad_token_id
        if pad_token_id is None:
            pad_token_id = self.tokenizer.eos_token_id
        if pad_token_id is None:
            pad_token_id = 0

        # Build clean generation kwargs to prevent validation errors (temperature vs do_sample)
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "pad_token_id": pad_token_id,
            "stopping_criteria": stopping_criteria,
        }
        if temperature > 0:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["do_sample"] = True
        else:
            gen_kwargs["do_sample"] = False

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                **gen_kwargs
            )

        input_len = inputs.input_ids.shape[1]
        text = self.tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)

        # Truncate at the first stop string found in the decoded text
        if stop:
            for s in stop:
                idx = text.find(s)
                if idx != -1:
                    text = text[:idx]

        return text

    def vram_gb(self) -> float:
        import torch
        return torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0

    def cleanup(self) -> None:
        import torch
        del self.model
        del self.tokenizer
        self.model = None
        self.tokenizer = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# ==========================================
# LLAMA.CPP ENGINE (uses existing binary)
# ==========================================
class LlamaCppEngine(InferenceEngine):
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.server_url = f"http://127.0.0.1:{LLAMA_BACKEND_PORT}"
        self.binary_path: Optional[str] = None

    def _find_llama_server(self) -> str:
        """Locate existing llama-server binary — no rebuild needed."""
        for path in LLAMA_SERVER_SEARCH_PATHS:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        found = shutil.which("llama-server")
        if found:
            return found

        for root in [Path("/home/jsosa/workspace"), Path.home()]:
            for match in root.rglob("llama-server"):
                if match.is_file() and os.access(str(match), os.X_OK):
                    return str(match)

        return ""

    def load(self, meta: dict) -> None:
        self.binary_path = self._find_llama_server()
        if not self.binary_path:
            print("\n[FATAL] No llama-server binary found on system.")
            print("Searched:")
            for p in LLAMA_SERVER_SEARCH_PATHS:
                if p:
                    print(f"  {p}")
            print("  $PATH (via `which llama-server`)")
            print("\nSet LLAMA_SERVER_PATH=/path/to/llama-server or add to PATH.")
            sys.exit(1)

        print(f"[AEGIS] Found llama-server: {self.binary_path}")

        ensure_port_free(LLAMA_BACKEND_PORT, label="llama-server backend")

        cmd = [
            self.binary_path,
            "-m", meta["path"],
            "--port", str(LLAMA_BACKEND_PORT),
            "--host", "127.0.0.1",
            "-ngl", str(meta.get("n_gpu_layers", -1)),
            "-c", str(meta.get("n_ctx", 4096)),
        ]

        print(f"[AEGIS] Launching: {' '.join(cmd)}")
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Wait for llama-server health check
        print("[AEGIS] Waiting for llama-server...", end="", flush=True)
        max_wait = 120
        start = time.time()
        while time.time() - start < max_wait:
            if self.process.poll() is not None:
                stderr = self.process.stderr.read().decode() if self.process.stderr else ""
                print(f"\n[FATAL] llama-server exited with code {self.process.returncode}")
                if stderr:
                    print(stderr[-2000:])
                sys.exit(1)

            try:
                import urllib.request
                resp = urllib.request.urlopen(f"{self.server_url}/health", timeout=2)
                if resp.status == 200:
                    print(" ready.")
                    return
            except Exception:
                pass

            time.sleep(1)
            print(".", end="", flush=True)

        print(f"\n[FATAL] llama-server did not respond within {max_wait}s")
        self.cleanup()
        sys.exit(1)

    async def generate(self, messages: list, temperature: float, max_tokens: int,
                       stop: Optional[List[str]] = None) -> str:
        """Proxy to llama-server's OpenAI-compatible endpoint."""
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stop:
            payload["stop"] = stop

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{self.server_url}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]

    def vram_gb(self) -> float:
        try:
            import torch
            return torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
        except ImportError:
            return 0

    def cleanup(self) -> None:
        if self.process and self.process.poll() is None:
            print("[AEGIS] Stopping llama-server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            print("[AEGIS] llama-server stopped.")


# ==========================================
# ENGINE FACTORY
# ==========================================
def create_engine(backend: Backend) -> InferenceEngine:
    if backend == Backend.TRANSFORMERS:
        return TransformersEngine()
    elif backend == Backend.LLAMACPP:
        return LlamaCppEngine()
    raise ValueError(f"Unknown backend: {backend}")


# ==========================================
# MODEL SELECTION
# ==========================================
def path_exists(meta: dict) -> bool:
    p = meta["path"]
    return os.path.isdir(p) or os.path.isfile(p)


def select_model_interactive() -> str:
    entries = list(MODEL_REGISTRY.items())
    tf_models = [(a, m) for a, m in entries if m["backend"] == Backend.TRANSFORMERS]
    gguf_models = [(a, m) for a, m in entries if m["backend"] == Backend.LLAMACPP]

    print("\n╔══════════════════════════════════════════════════╗")
    print("║         AEGIS LOCAL MODEL SELECTOR               ║")
    print("╠══════════════════════════════════════════════════╣")

    idx = 1
    index_map = {}

    if tf_models:
        print("║  ── Transformers (safetensors) ──────────────── ║")
        for alias, meta in tf_models:
            exists = "✓" if path_exists(meta) else "✗"
            print(f"║  [{idx}] {exists}  {alias:<38} ║")
            print(f"║       {meta['description']:<42} ║")
            index_map[idx] = alias
            idx += 1

    if gguf_models:
        # Show discovered binary
        probe = LlamaCppEngine()
        binary = probe._find_llama_server()
        tag = f"→ {binary}" if binary else "→ NOT FOUND"
        print(f"║  ── llama.cpp (GGUF) {tag:<27} ║")
        for alias, meta in gguf_models:
            exists = "✓" if path_exists(meta) else "✗"
            print(f"║  [{idx}] {exists}  {alias:<38} ║")
            print(f"║       {meta['description']:<42} ║")
            index_map[idx] = alias
            idx += 1

    print("╚══════════════════════════════════════════════════╝")

    while True:
        try:
            choice = int(input(f"\nSelect model [1-{idx - 1}]: "))
            if choice in index_map:
                alias = index_map[choice]
                print(f"→ Selected: {alias} ({MODEL_REGISTRY[alias]['backend'].value})")
                return alias
        except (ValueError, KeyboardInterrupt):
            pass
        print("Invalid selection.")


def parse_args():
    parser = argparse.ArgumentParser(description="Aegis Local Inference Server")
    parser.add_argument("--model", "-m", type=str, help="Model alias from registry")
    parser.add_argument("--list", "-l", action="store_true", help="List available models")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Server port (default: 8080)")
    args = parser.parse_args()

    if args.list:
        probe = LlamaCppEngine()
        found = probe._find_llama_server()
        print(f"\n{'ALIAS':<24} {'BACKEND':<14} {'EXISTS':<6} PATH")
        print("─" * 90)
        for alias, meta in MODEL_REGISTRY.items():
            exists = "✓" if path_exists(meta) else "✗"
            print(f"{alias:<24} {meta['backend'].value:<14} {exists:<6} {meta['path']}")
        print(f"\nllama-server: {found if found else 'NOT FOUND'}")
        sys.exit(0)

    if args.model:
        if args.model not in MODEL_REGISTRY:
            print(f"Unknown model '{args.model}'. Use --list to see available models.")
            sys.exit(1)
        return args.model, args.port

    return select_model_interactive(), args.port


# ==========================================
# GLOBALS
# ==========================================
SELECTED_ALIAS: str = ""
SELECTED_META: dict = {}
PORT: int = 8080
engine: Optional[InferenceEngine] = None


# ==========================================
# FASTAPI LIFESPAN
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    meta = SELECTED_META

    print(f"\n[AEGIS] Loading '{SELECTED_ALIAS}'")
    print(f"[AEGIS] Backend: {meta['backend'].value}")
    print(f"[AEGIS] Path: {meta['path']}")

    if not path_exists(meta):
        print(f"\n[FATAL] Model not found: {meta['path']}")
        sys.exit(1)

    t0 = time.time()
    try:
        engine = create_engine(meta["backend"])
        engine.load(meta)
        elapsed = time.time() - t0
        vram = engine.vram_gb()
        print(f"[AEGIS] Loaded in {elapsed:.1f}s  |  VRAM: {vram:.1f} GB")
        print(f"[AEGIS] Ready at http://127.0.0.1:{PORT}/v1/chat/completions\n")
    except Exception as e:
        print(f"\n[FATAL] Load failed: {e}")
        raise

    yield

    if engine:
        engine.cleanup()
    print("[AEGIS] Shutdown complete.")


# ==========================================
# API
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
    stop: Optional[List[str]] = None
    stream: Optional[bool] = False


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    if not engine:
        raise HTTPException(status_code=503, detail="Model loading or unavailable.")

    try:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        t0 = time.time()
        response_text = await engine.generate(messages, request.temperature, request.max_tokens,
                                                     stop=request.stop)
        latency = time.time() - t0

        return {
            "id": f"aegis-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": SELECTED_ALIAS,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response_text.strip()},
                "finish_reason": "stop",
            }],
            "usage": {"latency_seconds": round(latency, 2)},
        }
    except Exception as e:
        import traceback
        print("\n[API ERROR 500] Local inference pipeline exception caught:")
        traceback.print_exc()
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
                "owned_by": meta.get("owned_by", "local"),
                "backend": meta["backend"].value,
            }
            for alias, meta in MODEL_REGISTRY.items()
        ],
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": SELECTED_ALIAS,
        "backend": SELECTED_META["backend"].value,
        "vram_gb": round(engine.vram_gb(), 2) if engine else 0,
    }


# ==========================================
# GRACEFUL SHUTDOWN
# ==========================================
def _signal_handler(sig, frame):
    print("\n[AEGIS] Caught interrupt, cleaning up...")
    if engine:
        engine.cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ==========================================
# PORT CONFLICT RESOLUTION
# ==========================================
def ensure_port_free(port, label="server", retries=3):
    """Check that a TCP port is available, killing stale processes if needed."""
    for attempt in range(retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.close()
            return
        except OSError:
            print(f"[AEGIS] Port {port} in use ({label}), attempt {attempt+1}/{retries}...")
            subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)
            time.sleep(1)
    print(f"[FATAL] Port {port} still occupied. Run: fuser -k {port}/tcp")
    sys.exit(1)


# ==========================================
# ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    SELECTED_ALIAS, PORT = parse_args()
    SELECTED_META = MODEL_REGISTRY[SELECTED_ALIAS]

    ensure_port_free(PORT, label="Aegis API")

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)