import { EventEmitter } from 'events';
import { spawn, exec } from 'child_process';
import path from 'path';
import fs from 'fs';
import { promisify } from 'util';
import axios from 'axios';

const execAsync = promisify(exec);

interface LlamaModel {
  id: string;
  name: string;
  path: string;
  size: number;
  isDownloaded: boolean;
}

interface LlamaRequest {
  prompt: string;
  model: string;
  max_tokens?: number;
  temperature?: number;
  top_p?: number;
  stream?: boolean;
  system?: string;
}

interface LlamaResponse {
  content: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  model: string;
  finish_reason: string;
}

interface LlamaConfig {
  modelPath: string;
  serverPort: number;
  gpuLayers: number;
  contextSize: number;
  threadCount: number;
  maxPromptLength: number;
}

export class LlamaCPPBackend extends EventEmitter {
  private config: LlamaConfig;
  private serverProcess: any = null;
  private isRunning = false;
  private modelsPath: string;
  private serverPort: number;
  private baseUrl: string;

  constructor(config?: Partial<LlamaConfig>) {
    super();

    this.config = {
      modelPath: config?.modelPath || './models/llama.cpp',
      serverPort: config?.serverPort || 8080,
      gpuLayers: config?.gpuLayers || 0,
      contextSize: config?.contextSize || 4096,
      threadCount: config?.threadCount || 4,
      maxPromptLength: config?.maxPromptLength || 2048
    };

    this.modelsPath = path.join(__dirname, '../../models');
    this.serverPort = this.config.serverPort;
    this.baseUrl = `http://localhost:${this.serverPort}`;

    this.ensureLlamaDir();
  }

  private ensureLlamaDir(): void {
    if (!fs.existsSync(this.modelsPath)) {
      fs.mkdirSync(this.modelsPath, { recursive: true });
    }
  }

  async downloadModel(modelId: string): Promise<void> {
    const modelUrl = this.getModelUrl(modelId);
    const modelPath = path.join(this.modelsPath, `${modelId}.gguf`);

    this.emit('download-start', { modelId, path: modelPath });

    if (!fs.existsSync(modelPath)) {
      const response = await axios({
        method: 'get',
        url: modelUrl,
        responseType: 'stream'
      });

      const writer = fs.createWriteStream(modelPath);
      response.data.pipe(writer);

      return new Promise((resolve, reject) => {
        writer.on('finish', () => {
          this.emit('download-complete', { modelId, path: modelPath });
          resolve();
        });
        writer.on('error', reject);
      });
    }

    this.emit('download-complete', { modelId, path: modelPath });
  }

  private getModelUrl(modelId: string): string {
    const modelUrls = {
      'llama-3-8b': 'https://huggingface.co/bartowski/Llama-3-8B-Instruct-GGUF/resolve/main/Llama-3-8B-Instruct-IQ2_M.gguf',
      'llama-3-70b': 'https://huggingface.co/bartowski/Llama-3-70B-Instruct-GGUF/resolve/main/Llama-3-70B-Instruct-IQ2_M.gguf',
      'mistral-7b': 'https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf',
      'deepseek-7b': 'https://huggingface.co/TheBloke/deepseek-llm-7b-chat-GGUF/resolve/main/deepseek-llm-7b-chat.Q4_K_M.gguf'
    };
    return modelUrls[modelId] || modelUrls['llama-3-8b'];
  }

  async installLlamaCpp(): Promise<void> {
    const platform = process.platform;
    const arch = process.arch;

    let url = '';
    if (platform === 'win32') {
      url = 'https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1708-bin-win-avx-x64.zip';
    } else if (platform === 'darwin') {
      url = 'https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1708-bin-macos-arm64.zip';
