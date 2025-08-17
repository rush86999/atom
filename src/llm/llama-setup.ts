<file_path>
atom/src/llm/llama-setup.ts
</file_path>

import { spawn, exec } from 'child_process';
import path from 'path';
import fs from 'fs';
import { EventEmitter } from 'events';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

export class LlamaCPPManager extends EventEmitter {
  private modelsDir: string;
  private binaryDir: string;
  private serverPort: number;
  private process: any = null;
  private serverUrl: string;

  constructor() {
    super();
    this.modelsDir = path.join(__dirname, '../../models/llama.cpp');
    this.binaryDir = path.join(__dirname, '../../bin/llama.cpp');
    this.serverPort = 8080;
    this.serverUrl = `http://localhost:${this.serverPort}`;

    this.ensureDirectories();
  }

  private ensureDirectories() {
    [this.modelsDir, this.binaryDir].forEach(dir => {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    });
  }

  async downloadLlamaCPP() {
    const platform = process.platform;
    const arch = process.arch;

    // Maps to actual llama.cpp release URLs
    const urls: Record<string, string> = {
      'win32-x64': 'https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-win-avx2-x64.zip',
      'darwin-arm64': 'https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-macos-arm64.zip',
      'darwin-x64': 'https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-macos-x64.zip',
      'linux-x64': 'https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-ubuntu-x64.zip'
    };

    const downloadUrl = urls[`${platform}-${arch}`];
    if (!downloadUrl) {
      throw new Error(`Unsupported platform: ${platform}-${arch}`);
    }

    this.emit('download-start', { platform, arch, url: downloadUrl });

    // Download and extract
    const zipPath = path.join(this.binaryDir, 'llama.zip');
    const response = await axios({
      method: 'get',
      url: downloadUrl,
      responseType: 'stream'
    });

    const writer = fs.createWriteStream(zipPath);
    response.data.pipe(writer);

    return new Promise((resolve, reject) => {
      writer.on('finish', () => {
        // Would extract here in real implementation
        this.emit('download-complete', { path: this.binaryDir });
        resolve(true);
      });
      writer.on('error', reject);
    });
  }

  async downloadModel(modelId: string, size: 'small' | 'medium' | 'large' = 'small'): Promise<string> {
    const models = {
      'small': {
        'llama-3-8b': 'https://huggingface.co/bartowski/Llama-3-8B-Instruct-GGUF/resolve/main/Llama-3-8B-Instruct-Q4_K_M.gguf',
        'mistral-7b': 'https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf'
      },
      'medium': {
        'llama-3-8b': 'https://huggingface.co/bartowski/Llama-3-8B-Instruct-GGUF/resolve/main/Llama-3-8B-Instruct-IQ2_M.gguf'
      },
      'large': {
        'llama-3-70b': 'https://huggingface.co/bartowski/Llama-3-70B-Instruct-GGUF/resolve/main/Llama-3-70B-Instruct-IQ2_M.gguf'
      }
    };

    const url = models[size][modelId];
    if (!url) {
      throw new Error(`Model ${modelId} not found for size ${size}`);
    }

    const modelPath = path.join(this.modelsDir, `${modelId}-${size}.gguf`);

    this.emit('model-download-start', { modelId, size, path: modelPath });

    if (fs.existsSync(modelPath)) {
      this.emit('model-download-complete', { modelId, path: modelPath, cached: true });
      return modelPath;
    }

    const response = await axios({
      method: 'get',
      url: url,
      responseType: 'stream'
    });
