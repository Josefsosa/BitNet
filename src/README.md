# BitNet CPU Inference Optimization

This update provides significant performance improvements for BitNet inference on CPU through paralleled kernel implementations, native I2_S GEMM/GEMV support, configurable tiling block size and embedding quantization.

## Update

- **Parallel Weight & Activation Computation**  
  Implemented parallel processing of weights and activations in the W2A8 vet_dot kernel, achieving improved throughput on both x86 and ARM architectures.

- **Native I2_S GEMM & GEMV Support**  
  Integrated I2_S GEMM and GEMV operations into ggml library, making them fully compatible with the llama.cpp architecture. This enables seamless integration with existing inference pipelines.

- **Configurable Tiling & Parallelism**  
  Introduced configurable GEMM & GEMV block sizes and parallelism levels, allowing performance fine-tuning for different CPU architectures.

- **Embedding Quantization**  
  Added support for embedding layer quantization with Q6_K format, reducing memory footprint and improving inference speed while maintaining high accuracy.

## Usage

### Configuration Options

The `include/gemm-config.h` file controls kernel behavior:

```c
#define ROW_BLOCK_SIZE 4
#define COL_BLOCK_SIZE 128
#define PARALLEL_SIZE 4
```

Modify these values based on your CPU cache size and architecture for optimal performance. Users can fine-tune performance on their machine through `include/gemm-config.h`.

### Enabling Embedding Quantization

To use embedding quantization for additional speedup:

**Using setup_env.py:**
```bash
python setup_env.py --quant-embd
```
This automatically converts embeddings to Q6_K format.

**Manual conversion:**
```bash
build/bin/llama-quantize --token-embedding-type Q6_K models/BitNet-b1.58-2B-4T/ggml-model-f32.gguf models/BitNet-b1.58-2B-4T/ggml-model-i2_s-embed-q6_k.gguf I2_S 1 1
```

## Optimizations

### 1. Weight & Activation Parallelism

The kernel implements two parallelization strategies:

- **Weight Parallel:** Processes multiple weight rows/columns in a single kernel call, reducing kernel launch overhead.

- **Activation Parallel:** Built on top of weight parallel, amortizes the I2_S weight unpacking cost across multiple activation elements.

**Recommendation:** For I2_S quantization format, activation parallel is recommended due to the unpack operation benefits. The current kernel defaults to activation parallel.

**Kernel Performance Comparison:**

<div align="center">

Test configuration: AMD EPYC 7V13 (x86), 1 threads, time in milliseconds (mean±std)

| Matrix Size | No Parallel | Weight Parallel | Activation Parallel |
|:---:|:---:|:---:|:---:|
| [1, 2048] × [2048, 2048] | 0.075±0.012 | **0.058±0.007** | 0.076±0.011 |
| [32, 2048] × [2048, 2048] | 2.400±0.041 | 1.599±0.020 | **1.202±0.018** |
| [128, 2048] × [2048, 2048] | 10.820±0.039 | 6.458±0.168 | **5.805±0.039** |
| [256, 2048] × [2048, 2048] | 21.669±0.080 | 12.739±0.183 | **11.882±0.040** |
| [512, 2048] × [2048, 2048] | 43.257±0.083 | 25.680±0.335 | **23.342±0.082** |
| [2048, 2048] × [2048, 2048] | 173.175±0.214 | 103.112±0.552 | **93.276±0.612** |
| [128, 2048] × [2048, 8192] | 43.345±0.090 | 25.541±0.239 | **23.528±0.052** |
| [128, 8192] × [8192, 2048] | 38.085±0.162 | 23.866±0.096 | **22.569±0.132** |

</div>

### 2. GEMM/GEMV Integration with llama.cpp

Integrated I2_S quantization format into llama.cpp's compute graph:

- **GEMV Operations:** Optimized matrix-vector multiplication for token generation.
- **GEMM Operations:** Efficient matrix-matrix multiplication for prompt processing.
- **Tiling Strategy:** Configurable block sizes for optimal cache utilization.

### 3. Configuration Fine-tuning

Fine-tuning kernel parameters for optimal performance on specific hardware:

**Example Configuration (x86, AMD EPYC 7V13):**
- Method: Activation Parallel
- Threads: 8
- Workload: 128 prompt tokens (pp128)

**Fine-tuning Parameters:**
- **Parallelism Degree:** [2, 4, 8]
- **Row Block Size:** [2, 4, 8, 16, 32]
- **Column Block Size:** [32, 64, 128, 256, 512, 1024]

**Fine-tuning Results:**

<div align="center">

<img src="./assets/fine_tuning_result.png" alt="fine_tune_result" width="800"/>

*Shows throughput (tokens/s) for various configurations.*

</div>

**Optimal Configuration:** Under this setup (x86, 8 threads, pp128), the best performance is achieved with parallelism degree = 4, row block size = 4, and column block size = 128.

### 4. Embedding Quantization

Evaluated multiple embedding quantization formats to balance memory usage, model quality, and inference speed:

**Perplexity Comparison:**

<div align="center">

Test configuration: BitNet-b1.58-2B-4T, TG128

| Embedding Type | Wikitext | PTB | LAMBADA | IMDB | AG NEWS |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **F32** | 17.1090±0.1278 | 33.0858±0.4886 | 43.2850±0.6363 | 29.3016±0.2890 | 36.7686±0.3920 |
| **F16** | 17.1090±0.1278 | 33.0858±0.4886 | 43.2850±0.6363 | 29.3016±0.2890 | 36.7686±0.3920 |
| **Q8_0** | 17.1197±0.1280 | 33.1181±0.4893 | 43.2891±0.6364 | 29.3133±0.2892 | 36.7740±0.3920 |
| **Q6_K** | 17.1487±0.1282 | 33.2203±0.4914 | 43.3046±0.6362 | 29.3491±0.2897 | 36.7972±0.3921 |
| **Q5_0** | 17.2379±0.1288 | 33.2439±0.4907 | 43.4631±0.6379 | 29.5481±0.2920 | 36.8539±0.3924 |
| **Q4_0** | 17.3529±0.1300 | 33.7754±0.5001 | 44.4552±0.6559 | 30.1044±0.2978 | 37.3985±0.3997 |
| **Q3_K** | 17.6434±0.1320 | 34.3914±0.5089 | 45.4591±0.6735 | 30.8476±0.3069 | 39.5692±0.4259 |
| **I2_S** | N/A | N/A | N/A | N/A | N/A |

**N/A indicates model failure due to extreme quantization.*

</div>

**Inference Speed Comparison:**

<div align="center">

<img src="./assets/embedding_throughput.png" alt="embedding_throughput" width="800"/>

*Token generation throughput (tg128) for different embedding quantization types.*

</div>

**Recommendation:** Based on comprehensive evaluation of memory footprint, perplexity preservation, and inference speed, **Q6_K** is selected as the optimal embedding quantization format.

## Performance

Comparison of optimized parallel kernels vs. original implementation:

**Test Configuration:**
- Model: BitNet-b1.58-2B-4T
- Hardware: AMD EPYC 7V13
- Threads: 1 / 2 / 4 / 8 / 12 / 16
- Test: 128 prompt tokens (pp128) + 128 generated tokens (tg128)
- Method: Activation Parallel

<div align="center">

<img src="./assets/performance_comparison_amd_epyc.png" alt="performance_comparison_amd_epyc" width="800"/>

</div>

**Test Configuration:**
- Model: BitNet-b1.58-2B-4T
- Hardware: Intel i7-13800H
- Threads: 1 / 2 / 4 / 6
- Test: 128 prompt tokens (pp128) + 128 generated tokens (tg128)
- Method: Activation Parallel

<div align="center">

<img src="./assets/performance_comparison_i7-13800h.png" alt="performance_comparison_i7-13800h" width="800"/>

</div>

**Test Configuration:**
- Model: BitNet-b1.58-2B-4T
- Hardware: Cobalt 100
- Threads: 1 / 2 / 4 / 8
- Test: 128 prompt tokens (pp128) + 128 generated tokens (tg128)
- Method: Activation Parallel

<div align="center">

<img src="./assets/performance_comparison_cobalt100_dotprod.png" alt="performance_comparison_cobalt100_dotprod" width="800"/>

</div>

## Technical Details

### Key Files Modified

- `src/ggml-bitnet-mad.cpp`: Parallel kernel implementations
- `3rdparty/llama.cpp/ggml/src/ggml.c`: GEMM/GEMV integration
- `include/gemm-config.h`: Configuration file

### Supported Architectures

- ✅ x86-64 with AVX2
- ✅ ARM with NEON
- ✅ ARM with DOTPROD extension

## Aegis Local Inference Runbook

Use `src/aegis_local_inference_server.py` as the canonical local LLM entrypoint.
This file is local-only by default: it starts a local `llama-server` backend and
exposes an OpenAI-compatible API at `/v1/chat/completions`.

Do not use `aegis_server.py` when the goal is local model evaluation. That file
is the older Headroom/Gemini router and can redirect traffic to port `8787`.

### OODA Startup Steps

1. **Observe**: list what models are available and whether each is ready.

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py list
```

2. **Orient**: check a model before serving it.

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py check-model bitnet-2b
```

3. **Decide**: choose the alias and ports for the test run.

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model bitnet-2b --port 5510
```

4. **Act**: test the OpenAI-compatible endpoint.

```bash
curl -s -X POST http://127.0.0.1:5510/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"local","messages":[{"role":"user","content":"Reply with exactly: local-ok"}],"temperature":0,"max_tokens":16}'
```

### Shorthand Model Switching

Start one model per server process. To switch models, stop the running server
with `Ctrl+C`, then start the next alias.

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model bitnet-2b --port 5510
```

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model bitnet-3b --port 5510
```

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model qwen-coder-7b --port 5510
```

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model gemma-12b --port 5510
```

Use a different internal backend port when running two local servers at once:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model bitnet-2b --port 5510 --backend-port 5511
```

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model qwen-coder-7b --port 5520 --backend-port 5521
```

### Current Model Aliases

| Alias | Backend | Description | Path |
| --- | --- | --- | --- |
| `bitnet-2b` | `llama.cpp` | BitNet b1.58 2B-4T I2_S GGUF | `/home/jsosa/workspace/BitNet/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf` |
| `bitnet-3b` | `llama.cpp` | BitNet b1.58 3B I2_S GGUF | `/home/jsosa/workspace/BitNet/models/bitnet_b1_58-3B/ggml-model-i2_s.gguf` |
| `qwen-coder-7b` | `llama.cpp` | Qwen 2.5 Coder 7B Instruct Q4_K_M GGUF | `/home/jsosa/workspace/BitNet/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` |
| `gemma-12b` | `llama.cpp` | Gemma 12B Queen IQ2_XXS GGUF | `/home/jsosa/workspace/BitNet/models/gemma-4-12B-Queen-it-qat-q4_0-unquantized.i1-IQ2_XXS.gguf` |
| `llama-3-8b` | `llama.cpp` | Llama 3 8B Instruct Q4_K_M GGUF | `/home/jsosa/workspace/BitNet/models/llama-3-8b-Instruct-Q4_K_M.gguf` |
| `gsl` | `transformers` | GSL Safetensors checkpoint placeholder | `/home/jsosa/workspace/BitNet/models/model-00001-of-00282.safetensors` |

### Adding Downloaded Models

For a new GGUF model:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py add-model /home/jsosa/workspace/BitNet/models/new-model.gguf --alias new-model
python3 aegis_local_inference_server.py check-model new-model
python3 aegis_local_inference_server.py serve --model new-model --port 5510
```

For a Transformers/Safetensors model directory:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py add-model /home/jsosa/workspace/BitNet/models/new-transformers-model --alias new-transformers --backend transformers
python3 aegis_local_inference_server.py check-model new-transformers
```

Transformers/Safetensors models require a complete checkpoint directory,
including `config.json`, tokenizer files, all shard files or
`model.safetensors.index.json`, and Python packages `torch`, `transformers`,
`safetensors`, and `accelerate`.

### GSL Status

`gsl` is registered, but it is not serve-ready yet. The current file is only:

```text
/home/jsosa/workspace/BitNet/models/model-00001-of-00282.safetensors
```

That filename indicates shard `1` of `282`. Before serving `gsl`, complete the
download and make sure the model directory contains the full shard set,
`model.safetensors.index.json`, `config.json`, and tokenizer files. Verify with:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py check-model gsl
```

### tmux Remote Access Wrapper

Use `--tmux` when you want the local server to keep running after your SSH or
remote shell disconnects. The wrapper starts a detached tmux session from
`/home/jsosa/workspace/BitNet/src` and prints the attach/stop commands.

Start a model in tmux:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model bitnet-2b --port 5510 --tmux --session aegis-local
```

Attach while traveling or after reconnecting:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py tmux-attach --session aegis-local
```

Detach without stopping the server:

```text
Ctrl+B, then D
```

List running tmux sessions:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py tmux-list
```

Stop the tmux-hosted server:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py tmux-stop --session aegis-local
```

You can keep separate sessions for different tests by changing both the public
port and tmux session name:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model qwen-coder-7b --port 5520 --backend-port 5521 --tmux --session aegis-qwen
```

### OODA Steps To Complete GSL

Use this flow when `python3 aegis_local_inference_server.py check-model gsl`
reports that GSL is incomplete.

1. **Observe**: confirm what is present now.

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py check-model gsl
ls -lh /home/jsosa/workspace/BitNet/models/model-*-of-*.safetensors | wc -l
ls -lh /home/jsosa/workspace/BitNet/models/config.json /home/jsosa/workspace/BitNet/models/model.safetensors.index.json 2>/dev/null
ls -lh /home/jsosa/workspace/BitNet/models/tokenizer* 2>/dev/null
```

Expected complete state for the current GSL download shape:

```text
282 safetensors shard files
model.safetensors.index.json
config.json
tokenizer files
```

2. **Orient**: identify what is missing from the local model directory.

Current known incomplete state:

```text
Present: /home/jsosa/workspace/BitNet/models/model-00001-of-00282.safetensors
Missing: shards 00002 through 00282, model.safetensors.index.json, config.json, tokenizer files
Missing Python packages: torch, transformers, safetensors, accelerate
```

If the GSL download belongs in its own folder, move the completed files into a
stable directory before registering it, for example:

```bash
mkdir -p /home/jsosa/workspace/BitNet/models/gsl
mv /home/jsosa/workspace/BitNet/models/model-*-of-*.safetensors /home/jsosa/workspace/BitNet/models/gsl/
mv /home/jsosa/workspace/BitNet/models/config.json /home/jsosa/workspace/BitNet/models/gsl/ 2>/dev/null || true
mv /home/jsosa/workspace/BitNet/models/model.safetensors.index.json /home/jsosa/workspace/BitNet/models/gsl/ 2>/dev/null || true
mv /home/jsosa/workspace/BitNet/models/tokenizer* /home/jsosa/workspace/BitNet/models/gsl/ 2>/dev/null || true
```

3. **Decide**: finish one clean model layout and register that path.

For a completed GSL directory:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py add-model /home/jsosa/workspace/BitNet/models/gsl --alias gsl --backend transformers
```

For a single-file GGUF conversion of GSL, register the `.gguf` instead:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py add-model /home/jsosa/workspace/BitNet/models/gsl.gguf --alias gsl-gguf --backend llama.cpp
```

Prefer GGUF for this server today. The current serving path is production-ready
for `llama.cpp`/GGUF models. Transformers/Safetensors validation exists, but
serving Transformers models still requires adding the Transformers runtime path.

4. **Act**: install dependencies only after the full checkpoint is present.

Use the environment you intend to run the server with:

```bash
python3 -m pip install torch transformers safetensors accelerate
```

Then verify again:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py check-model gsl
python3 aegis_local_inference_server.py list
```

5. **Act**: serve only after `Ready: yes`.

For a GGUF GSL model:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model gsl-gguf --port 5510 --tmux --session aegis-gsl
```

For a Transformers GSL model, do not expect `serve --model gsl` to work until
the server has a Transformers backend implementation. Keep using
`check-model gsl` as the gate.

6. **Act**: test the endpoint after startup.

```bash
curl -s -X POST http://127.0.0.1:5510/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"local","messages":[{"role":"user","content":"Reply with exactly: gsl-ok"}],"temperature":0,"max_tokens":16}'
```

### Current Known-Good tmux Setup

As of the latest local smoke test, `qwen-coder-7b` is the known-good running
model for this `llama-server` build.

Start it:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py serve --model qwen-coder-7b --port 5510 --backend-port 5511 --tmux --session aegis-local
```

Health check:

```bash
curl -s http://127.0.0.1:5510/health
```

Chat smoke test:

```bash
curl -s -X POST http://127.0.0.1:5510/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"local","messages":[{"role":"user","content":"Reply with exactly: qwen-ok"}],"temperature":0,"max_tokens":16}'
```

Attach remotely:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py tmux-attach --session aegis-local
```

Stop it:

```bash
cd /home/jsosa/workspace/BitNet/src
python3 aegis_local_inference_server.py tmux-stop --session aegis-local
```

Gemma note: `gemma-12b` validates as a file, but the current
`/home/jsosa/workspace/BitNet/build/bin/llama-server` cannot load it because the
GGUF declares architecture `gemma4`, which this llama-server build reports as
unknown. Use `qwen-coder-7b` or a BitNet GGUF until llama.cpp/BitNet is rebuilt
with Gemma 4 architecture support.
