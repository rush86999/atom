#!/usr/bin/env node

/**
 * Llama.cpp Server Management Script
 *
 * This script handles downloading, setup, and management of llama.cpp
 * for the Atom NLU system's local model integration.
 */

import { spawn, exec } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import axios from "axios";
import * as unzipper from "unzipper";
import { promisify } from "util";
import {
  defaultLlamaConfig,
  getDefaultModelConfig,
} from "../config/llama.config";

const execAsync = promisify(exec);

interface DownloadProgress {
  total: number;
  downloaded: number;
  percentage: number;
  speed: number;
}

class LlamaCppManager {
  private config = defaultLlamaConfig;
  private serverProcess: any = null;
  private isServerRunning = false;

  constructor() {
    this.ensureDirectories();
  }

  private ensureDirectories(): void {
    const directories = [
      this.config.basePath,
      this.config.modelsPath,
      this.config.binariesPath,
      this.config.tempPath,
      this.config.cache.modelCachePath,
    ];

    for (const dir of directories) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
        console.log(`Created directory: ${dir}`);
      }
    }
  }

  async downloadLlamaCpp(): Promise<void> {
    const platform = os.platform();
    const arch = os.arch();

    const downloadUrls: Record<string, string> = {
      "win32-x64":
        "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-win-avx2-x64.zip",
      "darwin-arm64":
        "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-macos-arm64.zip",
      "darwin-x64":
        "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-macos-x64.zip",
      "linux-x64":
        "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-b1715-bin-ubuntu-x64.zip",
    };

    const key = `${platform}-${arch}`;
    const downloadUrl = downloadUrls[key];

    if (!downloadUrl) {
      throw new Error(`Unsupported platform/architecture: ${platform}-${arch}`);
    }

    console.log(`Downloading llama.cpp for ${key}...`);
    console.log(`URL: ${downloadUrl}`);

    const zipPath = path.join(this.config.tempPath, "llama.cpp.zip");
    const extractPath = this.config.binariesPath;

    try {
      // Download the file
      const response = await axios({
        method: "GET",
        url: downloadUrl,
        responseType: "stream",
        timeout: 300000, // 5 minutes
      });

      const totalSize = parseInt(response.headers["content-length"] || "0", 10);
      let downloaded = 0;
      let startTime = Date.now();

      const writer = fs.createWriteStream(zipPath);

      response.data.on("data", (chunk: Buffer) => {
        downloaded += chunk.length;
        const percentage = totalSize > 0 ? (downloaded / totalSize) * 100 : 0;
        const elapsed = (Date.now() - startTime) / 1000;
        const speed = elapsed > 0 ? downloaded / elapsed / 1024 / 1024 : 0;

        process.stdout.write(
          `\rDownload progress: ${percentage.toFixed(1)}% (${(downloaded / 1024 / 1024).toFixed(1)}MB/${(totalSize / 1024 / 1024).toFixed(1)}MB) - ${speed.toFixed(1)} MB/s`,
        );
      });

      response.data.pipe(writer);

      await new Promise((resolve, reject) => {
        writer.on("finish", resolve);
        writer.on("error", reject);
      });

      console.log("\nDownload completed. Extracting...");

      // Extract the zip file
      await fs
        .createReadStream(zipPath)
        .pipe(unzipper.Extract({ path: extractPath }))
        .promise();

      console.log("Extraction completed.");

      // Clean up
      fs.unlinkSync(zipPath);
      console.log("Temporary files cleaned up.");

      // Make binaries executable on Unix systems
      if (platform !== "win32") {
        const binaries = ["llama-server", "main", "quantize"];
        for (const binary of binaries) {
          const binaryPath = path.join(extractPath, binary);
          if (fs.existsSync(binaryPath)) {
            await execAsync(`chmod +x ${binaryPath}`);
          }
        }
      }

      console.log("Llama.cpp setup completed successfully!");
    } catch (error) {
      console.error("Download failed:", error);
      throw error;
    }
  }

  async downloadModel(modelId: string): Promise<void> {
    const modelConfig = this.config.models.find((m) => m.modelId === modelId);
    if (!modelConfig) {
      throw new Error(`Model ${modelId} not found in configuration`);
    }

    const modelPath = path.join(
      this.config.modelsPath,
      path.basename(modelConfig.modelPath),
    );

    if (fs.existsSync(modelPath)) {
      console.log(`Model ${modelId} already exists at ${modelPath}`);
      return;
    }

    console.log(`Downloading model: ${modelConfig.modelName}`);
    console.log(`URL: ${modelConfig.downloadUrl}`);
    console.log(
      `Size: ${(modelConfig.fileSize / 1024 / 1024 / 1024).toFixed(2)} GB`,
    );

    try {
      const response = await axios({
        method: "GET",
        url: modelConfig.downloadUrl,
        responseType: "stream",
        timeout: 3600000, // 1 hour timeout for large downloads
      });

      const totalSize = parseInt(response.headers["content-length"] || "0", 10);
      let downloaded = 0;
      let startTime = Date.now();

      const writer = fs.createWriteStream(modelPath);

      response.data.on("data", (chunk: Buffer) => {
        downloaded += chunk.length;
        const percentage = totalSize > 0 ? (downloaded / totalSize) * 100 : 0;
        const elapsed = (Date.now() - startTime) / 1000;
        const speed = elapsed > 0 ? downloaded / elapsed / 1024 / 1024 : 0;

        process.stdout.write(
          `\rDownload progress: ${percentage.toFixed(1)}% (${(downloaded / 1024 / 1024).toFixed(1)}MB/${(totalSize / 1024 / 1024).toFixed(1)}MB) - ${speed.toFixed(1)} MB/s`,
        );
      });

      response.data.pipe(writer);

      await new Promise((resolve, reject) => {
        writer.on("finish", resolve);
        writer.on("error", reject);
      });

      console.log("\nModel download completed!");
    } catch (error) {
      console.error("Model download failed:", error);
      // Clean up partially downloaded file
      if (fs.existsSync(modelPath)) {
        fs.unlinkSync(modelPath);
      }
      throw error;
    }
  }

  async startServer(modelId?: string): Promise<void> {
    if (this.isServerRunning) {
      console.log("Server is already running");
      return;
    }

    const targetModelId = modelId || this.config.defaultModel;
    const modelConfig = this.config.models.find(
      (m) => m.modelId === targetModelId,
    );
    if (!modelConfig) {
      throw new Error(`Model ${targetModelId} not found`);
    }

    const modelPath = path.join(
      this.config.modelsPath,
      path.basename(modelConfig.modelPath),
    );
    if (!fs.existsSync(modelPath)) {
      throw new Error(
        `Model file not found: ${modelPath}. Please download the model first.`,
      );
    }

    const binaryName =
      os.platform() === "win32" ? "llama-server.exe" : "llama-server";
    const serverBinary = path.join(this.config.binariesPath, binaryName);

    if (!fs.existsSync(serverBinary)) {
      throw new Error(
        `Server binary not found: ${serverBinary}. Please download llama.cpp first.`,
      );
    }

    console.log(
      `Starting llama.cpp server with model: ${modelConfig.modelName}`,
    );

    const args = [
      "--model",
      modelPath,
      "--port",
      this.config.server.serverPort.toString(),
      "--ctx-size",
      modelConfig.contextSize.toString(),
      "--n-gpu-layers",
      modelConfig.gpuLayers.toString(),
      "--threads",
      modelConfig.threadCount.toString(),
      "--batch-size",
      modelConfig.batchSize.toString(),
      "--log-disable",
    ];

    this.serverProcess = spawn(serverBinary, args);

    this.serverProcess.stdout.on("data", (data: Buffer) => {
      const message = data.toString().trim();
      if (message) {
        console.log(`[llama-server] ${message}`);
        if (message.includes("HTTP server listening")) {
          this.isServerRunning = true;
          console.log("Llama.cpp server started successfully!");
        }
      }
    });

    this.serverProcess.stderr.on("data", (data: Buffer) => {
      console.error(`[llama-server error] ${data.toString().trim()}`);
    });

    this.serverProcess.on("close", (code: number) => {
      console.log(`Llama.cpp server process exited with code ${code}`);
      this.isServerRunning = false;
    });

    // Wait for server to start
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }

  async stopServer(): Promise<void> {
    if (this.serverProcess) {
      this.serverProcess.kill();
      this.serverProcess = null;
      this.isServerRunning = false;
      console.log("Server stopped");
    }
  }

  async checkServerHealth(): Promise<boolean> {
    try {
      const response = await axios.get(
        `http://${this.config.server.host}:${this.config.server.serverPort}/health`,
        {
          timeout: 5000,
        },
      );
      return response.status === 200;
    } catch (error) {
      return false;
    }
  }

  async listModels(): Promise<void> {
    console.log("\nAvailable models:");
    console.log("================");

    for (const model of this.config.models) {
      const modelPath = path.join(
        this.config.modelsPath,
        path.basename(model.modelPath),
      );
      const exists = fs.existsSync(modelPath);
      const status = exists ? "✓ Downloaded" : "✗ Missing";

      console.log(`\n${model.modelName} (${model.modelId})`);
      console.log(
        `  Size: ${(model.fileSize / 1024 / 1024 / 1024).toFixed(2)} GB`,
      );
      console.log(`  Quantization: ${model.quantization}`);
      console.log(`  Context: ${model.contextSize} tokens`);
      console.log(`  Status: ${status}`);
      if (exists) {
        console.log(`  Path: ${modelPath}`);
      }
    }
  }
}

// Command line interface
async function main() {
  const manager = new LlamaCppManager();
  const args = process.argv.slice(2);
  const command = args[0];

  try {
    switch (command) {
      case "download":
        await manager.downloadLlamaCpp();
        break;

      case "download-model":
        const modelId = args[1] || defaultLlamaConfig.defaultModel;
        await manager.downloadModel(modelId);
        break;

      case "start":
        const startModelId = args[1];
        await manager.startServer(startModelId);
        break;

      case "stop":
        await manager.stopServer();
        break;

      case "status":
        const health = await manager.checkServerHealth();
        console.log(`Server health: ${health ? "Healthy" : "Unhealthy"}`);
        break;

      case "list-models":
        await manager.listModels();
        break;

      case "setup":
        console.log("Setting up llama.cpp...");
        await manager.downloadLlamaCpp();
        await manager.downloadModel(defaultLlamaConfig.defaultModel);
        console.log("Setup completed!");
        break;

      default:
        console.log(`
Llama.cpp Server Management Script

Usage:
  npm run llama:download          - Download llama.cpp binaries
  npm run llama:download-model [model] - Download a specific model
  npm run llama:start [model]     - Start the server with optional model
  npm run llama:stop              - Stop the server
  npm run llama:status            - Check server health
  npm run llama:list-models       - List available models
  npm run llama:setup             - Complete setup (download binaries + default model)

Available models: ${defaultLlamaConfig.models.map((m) => m.modelId).join(", ")}
Default model: ${defaultLlamaConfig.defaultModel}
        `);
        break;
    }
  } catch (error) {
    console.error(
      "Error:",
      error instanceof Error ? error.message : "Unknown error",
    );
    process.exit(1);
  }
}

// Run if this script is executed directly
if (require.main === module) {
  main();
}

export { LlamaCppManager };
