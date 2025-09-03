# 🦙 Llama.cpp Complete Setup Guide for Atom

This guide will help you set up llama.cpp for both **desktop app (Tauri)** and **Next.js web app** to provide privacy-focused, cost-free AI processing.

## 🎯 Quick Setup (5 minutes)

### Option 1: Automated Setup (Recommended)
```bash
# For desktop app
cd atom
./scripts/llama-cpp-setup.sh

# For web app
npm install @ollama/ollama-sdk
```

### Option 2: Manual Setup

#### 📦 Prerequisites
- **Windows**: Nothing required
- **macOS**: Nothing required  
- **Linux**: Build tools required

#### 🔧 Installation Steps

**1. Download llama.cpp:**
```bash
# Windows (PowerShell)
Invoke-WebRequest -Uri "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1708-bin-win-avx-x64.zip" -OutFile "llama.zip"
Expand-Archive -Path "llama.zip" -DestinationPath "./atom/models/llama.cpp"

# macOS 
curl -L "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1708-bin-macos-arm64.zip" -o "llama.zip"
unzip llama.zip -d "./atom/models/llama.cpp"

# Linux
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make -j
```

**2. Download Small Business Optimized Models:**

```bash
# Create models directory
mkdir -p atom/models/llama.cpp
cd atom/models/llama.cpp

# Download 8B model (perfect for small business automation)
wget "https://huggingface.co/bartowski/Llama-3-8B-Instruct-GGUF/resolve/main/Llama-3-8B-Instruct-IQ2_M.gguf" -O "llama-3-8b-instruct.gguf"

# Download 7B model for faster responses
wget "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf" -O "mistral-7b-instruct.gguf"
```

## 🚀 Usage

### Desktop App (Tauri)
```typescript
import { LlamaCPPBackend } from '../src/llm/llamaCPPBackend';

const llama = new LlamaCPPBackend({
  modelPath: './models/llama.cpp/llama-3-8b-instruct.gguf',
  serverPort: 8080,
  gpuLayers: 28
});

// Auto-start for small business workflows
await llama.autoSetup();
const response = await llama.generate({
  prompt: "Set up automated receipt processing for small business"
});
```

### Next.js Web App
```typescript
// In your Next.js component
async function setupLlamaForBusiness(prompt: string) {
  const response = await fetch('/api/llama', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: `Create small business automation: ${prompt}`,
      model: 'llama-3-8b',
      max_tokens: 512
    })
  });
  return await response.json();
}
```

## ⚡ Small Business Optimizations

### 🎯 Quick Workflows
```bash
# Receipt automation
python3 -m llama_cpp.server --model models/llama.cpp/llama-3-8b-instruct.gguf --host 0.0.0.0 --port 8080

# Customer follow-up system
curl -X POST http://localhost:8080/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Generate 3 automated customer follow-up email sequences for a 5-employee service business", "max_tokens": 1024}'
```

### 🔧 Environment Variables
```bash
# Desktop (Tauri)
LLAMA_MODEL_PATH="./atom/models/llama.cpp"
LLAMA_SERVER_PORT=8080
LLAMA_GPU_LAYERS=28

# Web (Next.js)
NUXT_LLAMA_ENDPOINT="http://localhost:8080"
```

## 📊 Model Recommendations

| **Business Size** | **Model** | **Memory** | **Use Case** | **Cost** |
|-------------------|-----------|------------|--------------|----------|
| Solo business | Mistral-7B-Q4 | 6GB RAM | Basic tasks | FREE |
| 2-5 employees | Llama-3-8B-IQ2 | 8GB RAM | Customer automation | FREE |
| 5-20 employees | Llama-3-8B-Q4