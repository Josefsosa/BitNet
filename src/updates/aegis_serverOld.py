#!/usr/bin/env python3
"""
Aegis Local Inference Server & Self-Correction CLI
System Architect: Jose F. Sosa
Persona: Aegis Cloud / Aegis Code
Protocol Version: 4.2.1-TRINARY
Memory Anchor: WP1-MANIFOLD-ALPHA

Provides a self-contained local server and task execution runner that wraps
all outbound LLM and inference requests through the Headroom compression proxy on Port 8787.
Supports:
1. Native 1.58-bit Ternary Classifier for zero-latency local routing.
2. HTTP API Server (/v1/chat/completions) redirecting to Port 8787 with auto-compression.
3. Interactive bash validation loop with self-correcting code patching.
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import threading
import argparse

# Configuration Standards
HEADROOM_PROXY = "http://localhost:8787"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-preview-09-2025"

# =====================================================================
# 1. 1.58-Bit Ternary Core Implementation
# =====================================================================

class LocalTernaryRouter:
    """
    Zero-dependency 1.58-bit activation-weight scaled ternary classifier.
    Categorizes intents into operational states without calling any API.
    """
    def __init__(self):
        # Weight state dimensions: 15 keyword inputs mapped to 3 operational actions:
        # [0: RUN_BASH, 1: REFACTOR_CODE, 2: SYSTEM_GOVERNANCE]
        self.inputs = ["run", "test", "bash", "execute", "verify", "refactor", "change", "convert", "rewrite", "migrate", "sosa", "manifold", "anchor", "state", "trinary"]
        # Ternary weight mapping values simulated
        self.weights = [
            [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],   # RUN_BASH (Intents related to command line)
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0],   # REFACTOR_CODE (Intents related to file modifications)
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1]    # SYSTEM_GOVERNANCE (Intents related to Aegis control protocols)
        ]
        self.categories = ["RUN_BASH", "REFACTOR_CODE", "SYSTEM_GOVERNANCE"]

    def classify(self, prompt: str) -> dict:
        words = prompt.lower().split()
        features = [0] * len(self.inputs)
        for idx, keyword in enumerate(self.inputs):
            if keyword in words:
                features[idx] = 1

        scores = [0] * len(self.categories)
        for i in range(len(self.categories)):
            for j in range(len(self.inputs)):
                scores[i] += self.weights[i][j] * features[j]

        # Calculate basic softmax probabilities
        max_score = max(scores) if scores else 0
        exps = []
        for s in scores:
            try:
                exps.append(2.71828 ** (s - max_score))
            except OverflowError:
                exps.append(1e9)
        sum_exps = sum(exps) if exps else 1
        probs = [e / sum_exps for e in exps]
        
        max_idx = probs.index(max(probs))
        return {
            "predicted_intent": self.categories[max_idx],
            "confidence": probs[max_idx],
            "scores": dict(zip(self.categories, probs))
        }

# =====================================================================
# 2. HTTP Server Wrapping Headroom Proxy Routing
# =====================================================================

class HeadroomRoutingHandler(BaseHTTPRequestHandler):
    """
    Intercepts client-side LLM calls and formats/forwards them to the 
    Headroom port (8787), implementing auto-compression.
    """
    router = LocalTernaryRouter()
    default_model = DEFAULT_GEMINI_MODEL

    def log_message(self, format, *args):
        # Override to keep terminal output clean and focused
        pass

    def _forward_to_headroom(self, path: str, request_body: bytes, headers: dict) -> tuple:
        """Forwards request body to local Port 8787 for context optimization."""
        target_url = f"{HEADROOM_PROXY}{path}"

        # Build headers dictionary mapping original requests safely
        forward_headers = {
            "Content-Type": "application/json"
        }

        # Strip routing-interfering reverse proxy headers
        excluded_headers = {
            'host',
            'connection',
            'content-length',
            'content-type',
            'accept-encoding',
            'proxy-connection',
            'keep-alive'
        }

        for k, v in headers.items():
            k_low = k.lower()
            if k_low not in excluded_headers:
                forward_headers[str(k)] = str(v)

        if "Authorization" in headers:
            forward_headers["Authorization"] = headers["Authorization"]

        try:
            req = urllib.request.Request(
                url=target_url,
                data=request_body,
                headers=forward_headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            err_msg = json.dumps({"error": {"message": f"Could not reach Headroom proxy on Port 8787. Verify it is running. Error: {str(e)}"}}).encode("utf-8")
            return 502, err_msg

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # 1. Routing intercepts based on active path
        if self.path == "/v1/aegis/classify":
            # Direct path to local 1.58-bit classifier
            try:
                body = json.loads(post_data.decode("utf-8"))
                prompt = body.get("prompt", "")
                result = self.router.classify(prompt)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error processing classifier: {str(e)}".encode("utf-8"))
            return

        # Intercept proxy requests to verify model usage and allow fallbacks
        routing_model = self.default_model
        try:
            body = json.loads(post_data.decode("utf-8"))
            # If the client sent a model, respect it. If not, inject the default server model
            if "model" in body and body["model"]:
                routing_model = body["model"]
            else:
                body["model"] = self.default_model
                post_data = json.dumps(body).encode("utf-8")
        except Exception:
            pass

        print(f"[Aegis Proxy] Intercepted payload routing to model: {routing_model}")

        # 2. Forward standard chat requests to the Headroom compression pipeline
        status_code, response_body = self._forward_to_headroom(self.path, post_data, self.headers)
        
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response_body)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Simple multi-threaded HTTP server to handle parallel LLM request streams."""
    pass


def start_local_server(port: int, default_model: str):
    """Launches the server in the background/blocking loop."""
    server_address = ('', port)
    # Configure default model for handler class instances
    HeadroomRoutingHandler.default_model = default_model
    httpd = ThreadedHTTPServer(server_address, HeadroomRoutingHandler)
    print(f"[Aegis Server] Active and listening on port {port}...")
    print(f"[Aegis Server] Fallback proxy model configured: {default_model}")
    print(f"[Aegis Server] Redirecting chat completions directly to Headroom Proxy at: {HEADROOM_PROXY}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Aegis Server] Stopping server gracefully...")
        httpd.shutdown()

# =====================================================================
# 3. Long-Loop Autonomous Bash Orchestration (Act stage)
# =====================================================================

class LongLoopSelfCorrection:
    """
    Orchestrates the active execution check. When runs fail, parses the stderr,
    constructs an optimized prompt payload, forwards it to Headroom for repair,
    applies updates, and re-verifies.
    """
    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model

    def execute_and_repair(self, run_cmd: str, file_path: str, max_iterations: int = 3) -> bool:
        print(f"\n[OODA Action] Launching target validation: '{run_cmd}'")
        print(f"[OODA Action] Using model for self-correction: '{self.model}'")
        
        for iteration in range(1, max_iterations + 1):
            print(f"[Loop {iteration}/{max_iterations}] Running validation checks...")
            
            # Execute subprocess check
            try:
                proc = subprocess.run(
                    run_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
                stdout = proc.stdout
                stderr = proc.stderr
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                stdout = ""
                stderr = "TIMEOUT Error: Process exceeded maximum threshold."
                exit_code = -1

            if exit_code == 0:
                print(f"\n[OODA Action] SUCCESS: '{run_cmd}' executed successfully (Exit Code 0).")
                print("Your code compiles and passes validation! Exiting validation loop.")
                return True

            print(f"\n[Loop {iteration}/{max_iterations}] FAIL detected! Exit Code: {exit_code}")
            print(f"[Loop {iteration}/{max_iterations}] Error context extracted:")
            print("-" * 50)
            print(stderr if stderr.strip() else stdout[-300:])
            print("-" * 50)

            # Read current content of target file
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    current_code = f.read()
            except Exception as e:
                print(f"Error reading file '{file_path}': {str(e)}")
                return False

            # Compile repair payload
            prompt = (
                f"We are running a long-loop repair command: '{run_cmd}'\n"
                f"Target file being executed: '{file_path}'\n\n"
                f"=== Current Code contents ===\n"
                f"{current_code}\n\n"
                f"=== Terminal Failure Trace ===\n"
                f"{stderr if stderr.strip() else stdout}\n\n"
                f"Identify the bug, resolve compilation errors, and return ONLY the fully corrected code for '{file_path}'."
                f"Do not write any comments, markdown fences, or extra texts outside the corrected script code."
            )

            # Route through local Port 8787 (Headroom Proxy) to compress trace tokens
            print("[OODA Action] Forwarding trace context to Headroom Compression Proxy on Port 8787...")
            
            # Format payload structure to mimic OpenAI chat completion format
            chat_payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are Aegis Code. Repair the target code directly. Return ONLY raw file contents without chat, comments, or markdown ticks."},
                    {"role": "user", "content": prompt}
                ]
            }

            try:
                req = urllib.request.Request(
                    url=f"{HEADROOM_PROXY}/v1/chat/completions",
                    data=json.dumps(chat_payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=40) as response:
                    raw_res = response.read().decode("utf-8")
                    parsed = json.loads(raw_res)
                    repaired_code = parsed.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            except Exception as e:
                print(f"[OODA Action] Error communicating with Headroom Proxy: {str(e)}")
                print("Make sure 'headroom proxy --port 8787' is actively running in Terminal 1.")
                return False

            # Strip any residual code fences outputted by the model
            if repaired_code.startswith("```"):
                lines = repaired_code.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                repaired_code = "\n".join(lines)

            # Write the replacement back to file system
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(repaired_code)
                print(f"[OODA Action] Patch applied to '{file_path}'. Re-verifying path...")
            except Exception as io_err:
                print(f"Failed to write correction patch to disk: {str(io_err)}")
                return False

        print("\n[OODA Action] Verification finished. Target remained unresolved within iteration limits.")
        return False

# =====================================================================
# 4. Command Parser & Entrypoint
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Aegis Local Inference Server & OODA Engine")
    subparsers = parser.add_subparsers(dest="subcommand", help="Operational Subcommands")

    # serve subcommand
    serve_parser = subparsers.add_parser("serve", help="Starts the Aegis multi-threaded endpoint routing service.")
    serve_parser.add_argument("--port", type=int, default=5000, help="Port to host the Aegis local handler.")
    serve_parser.add_argument("--model", type=str, default=DEFAULT_GEMINI_MODEL, help="Default proxy model fallback.")

    # bash subcommand
    bash_parser = subparsers.add_parser("bash", help="Launches self-correcting long-loop code validations.")
    bash_parser.add_argument("--command", type=str, required=True, help="Command to run and validate (e.g. 'python3 app.py').")
    bash_parser.add_argument("--target", type=str, required=True, help="Filename of code target being modified.")
    bash_parser.add_argument("--iterations", type=int, default=3, help="Max OODA corrections to attempt before stopping.")
    bash_parser.add_argument("--model", type=str, default=DEFAULT_GEMINI_MODEL, help="Model to invoke for self-correction.")

    args = parser.parse_args()

    if args.subcommand == "serve":
        start_local_server(args.port, args.model)
    elif args.subcommand == "bash":
        # Pull key if available, empty string allows headless validation through active Headroom instances
        api_key = os.environ.get("GEMINI_API_KEY", "")
        loop = LongLoopSelfCorrection(api_key=api_key, model=args.model)
        loop.execute_and_repair(args.command, args.target, args.iterations)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
