#!/usr/bin/env python3
"""
Aegis local inference server.

Runs a local llama.cpp `llama-server` backend and exposes a stable
OpenAI-compatible endpoint at /v1/chat/completions. Models can be selected by
alias from a small JSON registry or by direct GGUF/Transformers path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODELS_ROOT = Path(os.environ.get("AEGIS_MODELS_ROOT", REPO_ROOT / "models"))
DEFAULT_REGISTRY_PATH = Path(
    os.environ.get("AEGIS_MODEL_REGISTRY", Path(__file__).resolve().parent / ".aegis_models.json")
)
DEFAULT_LLAMA_SERVER_PATHS = [
    os.environ.get("LLAMA_SERVER_PATH", ""),
    str(REPO_ROOT / "build" / "bin" / "llama-server"),
    "/home/jsosa/workspace/llama-cpp-main/build/bin/llama-server",
    "/home/jsosa/workspace/oakland-cli/llama.cpp/build/bin/llama-server",
]


BUILTIN_MODELS: dict[str, dict[str, Any]] = {
    "bitnet-2b": {
        "path": str(DEFAULT_MODELS_ROOT / "BitNet-b1.58-2B-4T" / "ggml-model-i2_s.gguf"),
        "description": "BitNet b1.58 2B-4T I2_S GGUF",
        "backend": "llama.cpp",
        "n_ctx": 2048,
        "n_gpu_layers": 0,
    },
    "bitnet-3b": {
        "path": str(DEFAULT_MODELS_ROOT / "bitnet_b1_58-3B" / "ggml-model-i2_s.gguf"),
        "description": "BitNet b1.58 3B I2_S GGUF",
        "backend": "llama.cpp",
        "n_ctx": 2048,
        "n_gpu_layers": 0,
    },
    "gemma-12b": {
        "path": str(DEFAULT_MODELS_ROOT / "gemma-4-12B-Queen-it-qat-q4_0-unquantized.i1-IQ2_XXS.gguf"),
        "description": "Gemma 12B Queen IQ2_XXS GGUF",
        "backend": "llama.cpp",
        "n_ctx": 4096,
        "n_gpu_layers": -1,
    },
    "llama-3-8b": {
        "path": str(DEFAULT_MODELS_ROOT / "llama-3-8b-Instruct-Q4_K_M.gguf"),
        "description": "Llama 3 8B Instruct Q4_K_M GGUF",
        "backend": "llama.cpp",
        "n_ctx": 4096,
        "n_gpu_layers": -1,
    },
    "qwen-coder-7b": {
        "path": str(DEFAULT_MODELS_ROOT / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"),
        "description": "Qwen 2.5 Coder 7B Instruct Q4_K_M GGUF",
        "backend": "llama.cpp",
        "n_ctx": 4096,
        "n_gpu_layers": -1,
    },
    "gsl": {
        "path": str(DEFAULT_MODELS_ROOT / "model-00001-of-00282.safetensors"),
        "description": "GSL Transformers/Safetensors checkpoint",
        "backend": "transformers",
        "n_ctx": 4096,
        "n_gpu_layers": -1,
    },
}


def slugify(value: str) -> str:
    value = value.lower().replace(".safetensors", "").replace(".gguf", "")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "model"


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    models = data.get("models", data)
    if not isinstance(models, dict):
        raise ValueError(f"Registry must contain a model object: {path}")
    return models


def save_registry(models: dict[str, dict[str, Any]], path: Path = DEFAULT_REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "models": dict(sorted(models.items())),
        "notes": "Local Aegis model aliases. Add GGUF paths here or use the add-model command.",
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def discover_gguf_models(models_root: Path = DEFAULT_MODELS_ROOT) -> dict[str, dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}
    if not models_root.exists():
        return discovered

    for path in sorted(models_root.rglob("*.gguf")):
        alias_base = slugify(path.stem)
        alias = alias_base
        counter = 2
        while alias in discovered or alias in BUILTIN_MODELS:
            alias = f"{alias_base}-{counter}"
            counter += 1
        discovered[alias] = {
            "path": str(path),
            "description": f"Auto-discovered GGUF: {path.name}",
            "backend": "llama.cpp",
            "n_ctx": 4096,
            "n_gpu_layers": -1,
            "auto_discovered": True,
        }
    return discovered


def available_models(include_auto: bool = True) -> dict[str, dict[str, Any]]:
    models = dict(BUILTIN_MODELS)
    if include_auto:
        models.update(discover_gguf_models())
    models.update(load_registry())
    return models


def model_exists(meta: dict[str, Any]) -> bool:
    path = Path(str(meta["path"])).expanduser()
    return path.is_file() or path.is_dir()


def model_backend(meta: dict[str, Any]) -> str:
    path = Path(str(meta["path"])).expanduser()
    if meta.get("backend"):
        return str(meta["backend"])
    if path.suffix.lower() == ".gguf":
        return "llama.cpp"
    return "transformers"


def transformers_status(meta: dict[str, Any]) -> tuple[bool, list[str]]:
    path = Path(str(meta["path"])).expanduser()
    model_dir = path if path.is_dir() else path.parent
    missing = []
    if path.suffix.lower() == ".safetensors" and "-of-" in path.name:
        missing.append("complete shard set or model.safetensors.index.json")
    if not (model_dir / "config.json").is_file():
        missing.append("config.json")
    if not any(model_dir.glob("tokenizer*")):
        missing.append("tokenizer files")
    for module in ["torch", "transformers", "safetensors", "accelerate"]:
        try:
            __import__(module)
        except ImportError:
            missing.append(f"python package: {module}")
    return not missing, missing


def validate_model(alias: str, meta: dict[str, Any]) -> tuple[bool, str]:
    if not model_exists(meta):
        return False, f"model path does not exist: {meta['path']}"
    backend_name = model_backend(meta)
    if backend_name == "llama.cpp":
        path = Path(str(meta["path"])).expanduser()
        if path.suffix.lower() != ".gguf":
            return False, "llama.cpp backend requires a .gguf file"
        try:
            find_llama_server()
        except SystemExit as exc:
            return False, str(exc)
        return True, "ready for llama.cpp"
    if backend_name == "transformers":
        ok, missing = transformers_status(meta)
        if ok:
            return True, "Transformers checkpoint appears complete"
        return False, "missing " + ", ".join(dict.fromkeys(missing))
    return False, f"unknown backend '{backend_name}'"


def resolve_model(model: str, include_auto: bool = True) -> tuple[str, dict[str, Any]]:
    candidate = Path(model).expanduser()
    if candidate.suffix.lower() in {".gguf", ".safetensors"} or candidate.is_dir():
        alias = slugify(candidate.stem if candidate.is_file() else candidate.name)
        backend_name = "llama.cpp" if candidate.suffix.lower() == ".gguf" else "transformers"
        return alias, {
            "path": str(candidate),
            "description": f"Direct {backend_name} path",
            "backend": backend_name,
            "n_ctx": 4096,
            "n_gpu_layers": -1,
        }

    models = available_models(include_auto=include_auto)
    if model not in models:
        known = ", ".join(sorted(models))
        raise SystemExit(f"Unknown model alias '{model}'. Known aliases: {known}")
    return model, models[model]


def default_model_alias() -> str:
    preferred = ["bitnet-3b", "bitnet-2b", "qwen-coder-7b", "llama-3-8b", "gemma-12b"]
    models = available_models()
    for alias in preferred:
        if alias in models and model_exists(models[alias]):
            return alias
    for alias, meta in models.items():
        if model_exists(meta):
            return alias
    raise SystemExit(f"No local GGUF models found under {DEFAULT_MODELS_ROOT}")


def find_llama_server() -> str:
    for raw_path in DEFAULT_LLAMA_SERVER_PATHS:
        if not raw_path:
            continue
        path = Path(raw_path).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)

    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_dir) / "llama-server"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    raise SystemExit(
        "No executable llama-server found. Set LLAMA_SERVER_PATH=/path/to/llama-server "
        "or build BitNet so build/bin/llama-server exists."
    )


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def wait_for_health(url: str, process: subprocess.Popen[bytes], timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
            raise SystemExit(f"llama-server exited with code {process.returncode}\n{stderr[-3000:]}")
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise SystemExit(f"llama-server did not become healthy at {url}/health within {timeout}s")


class LocalBackend:
    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen[bytes]] = None
        self.alias = ""
        self.meta: dict[str, Any] = {}
        self.url = ""

    def start(self, alias: str, meta: dict[str, Any], backend_port: int, args: argparse.Namespace) -> None:
        ok, reason = validate_model(alias, meta)
        if not ok:
            raise SystemExit(f"Model '{alias}' is not serve-ready: {reason}")
        if model_backend(meta) != "llama.cpp":
            raise SystemExit(f"Model '{alias}' uses backend '{model_backend(meta)}'. This server currently serves llama.cpp/GGUF models only.")
        if not port_is_free(backend_port):
            raise SystemExit(f"Backend port {backend_port} is already in use. Pick --backend-port or stop that process.")

        llama_server = find_llama_server()
        self.alias = alias
        self.meta = meta
        self.url = f"http://127.0.0.1:{backend_port}"

        cmd = [
            llama_server,
            "-m", str(Path(str(meta["path"])).expanduser()),
            "--host", "127.0.0.1",
            "--port", str(backend_port),
            "-c", str(args.ctx_size or meta.get("n_ctx", 4096)),
            "-ngl", str(args.gpu_layers if args.gpu_layers is not None else meta.get("n_gpu_layers", -1)),
            "-t", str(args.threads),
        ]
        if args.extra_llama_arg:
            cmd.extend(args.extra_llama_arg)

        print(f"[Aegis Local] Model: {alias}")
        print(f"[Aegis Local] Path: {meta['path']}")
        print(f"[Aegis Local] llama-server: {llama_server}")
        print(f"[Aegis Local] Backend: {self.url}")
        print(f"[Aegis Local] Launching backend...")
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        wait_for_health(self.url, self.process)
        print("[Aegis Local] Backend ready.")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            print("[Aegis Local] Stopping backend...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)

    def post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload["model"] = self.alias
        request = urllib.request.Request(
            f"{self.url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=e.code, detail=body) from e


backend = LocalBackend()
SELECTED_ALIAS = ""
SELECTED_META: dict[str, Any] = {}
SERVER_ARGS: Optional[argparse.Namespace] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if SERVER_ARGS is None:
        raise RuntimeError("Server arguments were not initialized.")
    backend.start(SELECTED_ALIAS, SELECTED_META, SERVER_ARGS.backend_port, SERVER_ARGS)
    yield
    backend.stop()


app = FastAPI(title="Aegis Local Inference", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": SELECTED_ALIAS,
        "model_path": SELECTED_META.get("path"),
        "backend": backend.url,
        "endpoint": "/v1/chat/completions",
    }


@app.get("/v1/models")
def list_models_endpoint() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": alias,
                "object": "model",
                "owned_by": "local",
                "exists": model_exists(meta),
                "backend": model_backend(meta),
                "path": meta["path"],
                "description": meta.get("description", ""),
            }
            for alias, meta in sorted(available_models().items())
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict[str, Any]:
    payload = await request.json()
    requested_model = payload.get("model")
    if requested_model and requested_model not in {"local", SELECTED_ALIAS}:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Server is running '{SELECTED_ALIAS}'. Restart with "
                f"`python3 aegis_local_inference_server.py serve --model {requested_model}` to switch models."
            ),
        )
    return backend.post_chat(payload)


def tmux_session_exists(session: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def tmux_command_from_args(args: argparse.Namespace) -> str:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "serve",
        "--model", args.model or default_model_alias(),
        "--port", str(args.port),
        "--backend-port", str(args.backend_port),
        "--ctx-size", str(args.ctx_size),
        "--threads", str(args.threads),
        "--host", args.host,
    ]
    if args.gpu_layers is not None:
        cmd.extend(["--gpu-layers", str(args.gpu_layers)])
    for extra in args.extra_llama_arg:
        cmd.extend(["--extra-llama-arg", extra])
    quoted_cmd = " ".join(shlex.quote(part) for part in cmd)
    return (
        f"cd {shlex.quote(str(Path.cwd()))} && "
        f"echo '[Aegis tmux] {quoted_cmd}' && "
        f"{quoted_cmd}; "
        "status=$?; echo; echo '[Aegis tmux] process exited with status '$status; "
        "echo '[Aegis tmux] press Ctrl+B then D to detach, or exit to close'; exec bash"
    )


def launch_tmux(args: argparse.Namespace) -> None:
    session = args.session
    if tmux_session_exists(session):
        raise SystemExit(
            f"tmux session '{session}' already exists. Attach with: "
            f"tmux attach -t {session}\nStop it with: python3 aegis_local_inference_server.py tmux-stop --session {session}"
        )

    command = tmux_command_from_args(args)
    subprocess.run(["tmux", "new-session", "-d", "-s", session, command], check=True)
    print(f"[Aegis tmux] Started session: {session}")
    print(f"[Aegis tmux] Attach: tmux attach -t {session}")
    print(f"[Aegis tmux] Stop:   python3 aegis_local_inference_server.py tmux-stop --session {session}")
    print(f"[Aegis tmux] API:    http://{args.host}:{args.port}/v1/chat/completions")


def list_tmux_sessions() -> None:
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}: #{session_windows} windows, created #{session_created_string}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        print("No tmux sessions are running.")
        return
    print(result.stdout.rstrip())


def attach_tmux(args: argparse.Namespace) -> None:
    os.execvp("tmux", ["tmux", "attach", "-t", args.session])


def stop_tmux(args: argparse.Namespace) -> None:
    if not tmux_session_exists(args.session):
        print(f"tmux session '{args.session}' is not running.")
        return
    subprocess.run(["tmux", "kill-session", "-t", args.session], check=True)
    print(f"Stopped tmux session: {args.session}")


def print_models() -> None:
    models = available_models()
    print(f"\nRegistry: {DEFAULT_REGISTRY_PATH}")
    print(f"Models root: {DEFAULT_MODELS_ROOT}\n")
    print(f"{'ALIAS':<34} {'OK':<3} {'BACKEND':<12} {'CTX':<6} {'GPU':<5} PATH")
    print("-" * 125)
    for alias, meta in sorted(models.items()):
        ready, _reason = validate_model(alias, meta)
        ok = "yes" if ready else "no"
        print(
            f"{alias:<34} {ok:<3} {model_backend(meta):<12} {str(meta.get('n_ctx', 4096)):<6} "
            f"{str(meta.get('n_gpu_layers', -1)):<5} {meta['path']}"
        )


def add_model(args: argparse.Namespace) -> None:
    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Model path not found: {path}")
    if path.is_file() and path.suffix.lower() not in {".gguf", ".safetensors"}:
        raise SystemExit("Model file must be .gguf or .safetensors. Transformers directories are also accepted.")

    backend_name = args.backend
    if backend_name == "auto":
        backend_name = "llama.cpp" if path.is_file() and path.suffix.lower() == ".gguf" else "transformers"

    registry = load_registry()
    alias = args.alias or slugify(path.stem if path.is_file() else path.name)
    registry[alias] = {
        "path": str(path),
        "description": args.description or f"User model: {path.name}",
        "backend": backend_name,
        "n_ctx": args.ctx_size,
        "n_gpu_layers": args.gpu_layers,
    }
    save_registry(registry)
    ready, reason = validate_model(alias, registry[alias])
    print(f"Added model alias '{alias}' -> {path}")
    print(f"Backend: {backend_name}")
    print(f"Ready: {'yes' if ready else 'no'} ({reason})")
    print(f"Registry updated: {DEFAULT_REGISTRY_PATH}")


def check_model(args: argparse.Namespace) -> None:
    alias, meta = resolve_model(args.model)
    ready, reason = validate_model(alias, meta)
    print(f"Alias: {alias}")
    print(f"Path: {meta['path']}")
    print(f"Backend: {model_backend(meta)}")
    print(f"Ready: {'yes' if ready else 'no'}")
    print(f"Reason: {reason}")


def remove_model(args: argparse.Namespace) -> None:
    registry = load_registry()
    if args.alias not in registry:
        raise SystemExit(f"Alias '{args.alias}' is not in user registry: {DEFAULT_REGISTRY_PATH}")
    del registry[args.alias]
    save_registry(registry)
    print(f"Removed model alias '{args.alias}' from {DEFAULT_REGISTRY_PATH}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aegis local inference server")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Start the local OpenAI-compatible server")
    serve.add_argument("--model", "-m", default="", help="Model alias or direct model path")
    serve.add_argument("--port", "-p", type=int, default=5000, help="Public API port")
    serve.add_argument("--backend-port", type=int, default=8090, help="Internal llama-server port")
    serve.add_argument("--ctx-size", "-c", type=int, default=0, help="Context size override")
    serve.add_argument("--threads", "-t", type=int, default=max(os.cpu_count() or 2, 2), help="CPU threads")
    serve.add_argument("--gpu-layers", "-ngl", type=int, default=None, help="GPU layer override")
    serve.add_argument("--host", default="127.0.0.1", help="Public API host")
    serve.add_argument("--tmux", action="store_true", help="Start this server in a detached tmux session")
    serve.add_argument("--session", default="aegis-local", help="tmux session name for --tmux")
    serve.add_argument(
        "--extra-llama-arg",
        action="append",
        default=[],
        help="Extra argument passed to llama-server. Repeat for multiple args.",
    )

    subparsers.add_parser("list", help="List known local models")
    subparsers.add_parser("--list", help=argparse.SUPPRESS)

    check = subparsers.add_parser("check-model", help="Validate whether a model alias/path is serve-ready")
    check.add_argument("model", help="Model alias or path to check")

    add = subparsers.add_parser("add-model", help="Add or update a model alias in .aegis_models.json")
    add.add_argument("path", help="Path to a local .gguf/.safetensors file or Transformers directory")
    add.add_argument("--alias", "-a", default="", help="Alias to use when serving")
    add.add_argument("--description", "-d", default="", help="Human-readable description")
    add.add_argument("--backend", choices=["auto", "llama.cpp", "transformers"], default="auto", help="Inference backend")
    add.add_argument("--ctx-size", "-c", type=int, default=4096, help="Default context size")
    add.add_argument("--gpu-layers", "-ngl", type=int, default=-1, help="Default GPU layers")

    remove = subparsers.add_parser("remove-model", help="Remove a user model alias")
    remove.add_argument("alias", help="Alias to remove from the user registry")

    subparsers.add_parser("tmux-list", help="List tmux sessions")

    attach = subparsers.add_parser("tmux-attach", help="Attach to the Aegis tmux session")
    attach.add_argument("--session", default="aegis-local", help="tmux session name")

    stop = subparsers.add_parser("tmux-stop", help="Stop the Aegis tmux session")
    stop.add_argument("--session", default="aegis-local", help="tmux session name")

    return parser


def main() -> None:
    global SELECTED_ALIAS, SELECTED_META, SERVER_ARGS

    parser = build_parser()
    if len(sys.argv) > 1 and sys.argv[1] in {"--list", "-l"}:
        print_models()
        return
    if len(sys.argv) == 1:
        sys.argv.append("serve")
    args = parser.parse_args()

    if args.command in {"list", "--list"}:
        print_models()
        return
    if args.command == "add-model":
        add_model(args)
        return
    if args.command == "check-model":
        check_model(args)
        return
    if args.command == "remove-model":
        remove_model(args)
        return
    if args.command == "tmux-list":
        list_tmux_sessions()
        return
    if args.command == "tmux-attach":
        attach_tmux(args)
        return
    if args.command == "tmux-stop":
        stop_tmux(args)
        return
    if args.command != "serve":
        parser.print_help()
        return

    if args.tmux:
        launch_tmux(args)
        return

    if not port_is_free(args.port, args.host):
        raise SystemExit(f"API port {args.port} is already in use. Pick --port or stop that process.")

    selected = args.model or default_model_alias()
    SELECTED_ALIAS, SELECTED_META = resolve_model(selected)
    SERVER_ARGS = args

    def shutdown_handler(sig, frame):
        backend.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    import uvicorn

    print(f"[Aegis Local] API: http://{args.host}:{args.port}")
    print("[Aegis Local] Switch models with: python3 aegis_local_inference_server.py serve --model <alias>")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
