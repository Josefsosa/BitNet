from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Load model and tokenizer
model_name = "1bitLLM/bitnet_b1_58-2B-4T"
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    device_map="auto",
    trust_remote_code=True,
    torch_dtype=torch.float16
)

# Generate text
prompt = "Hello world"
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_length=50, temperature=0.8)
result = tokenizer.decode(outputs[0], skip_special_tokens=True)

print(result)
