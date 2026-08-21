import { NextApiRequest, NextApiResponse } from "next";
import fs from "fs";
import path from "path";
import os from "os";
import { execFile } from "child_process";

/**
 * Allowed base directory for file operations.
 * Restricts all file read/write/list operations to this directory tree.
 */
const ALLOWED_BASE_DIR = path.resolve(process.cwd());

/**
 * Validate that a resolved path is within the allowed base directory.
 * Prevents path traversal attacks (CWE-22).
 */
function validatePath(userPath: string): string {
  const resolved = path.resolve(userPath);
  if (!resolved.startsWith(ALLOWED_BASE_DIR + path.sep) && resolved !== ALLOWED_BASE_DIR) {
    throw new Error("Path is outside the allowed directory");
  }
  return resolved;
}

/**
 * Allowlist of commands that may be executed via the execute_command handler.
 * Each entry maps to a safe execFile invocation with controlled arguments.
 */
const ALLOWED_COMMANDS: Record<string, string> = {
  "node --version": "node",
  "npm --version": "npm",
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { command, args } = req.body;

  try {
    if (command === "get_system_info") {
      const cpuUsage = os.loadavg()[0];
      const totalMem = os.totalmem();
      const freeMem = os.freemem();
      const memUsage = ((totalMem - freeMem) / totalMem) * 100;
      
      return res.status(200).json({
        os: `${os.type()} ${os.release()} (${os.arch()})`,
        cpu_usage: parseFloat(cpuUsage.toFixed(1)) || 12.5,
        memory_usage: parseFloat(memUsage.toFixed(1)),
        disk_usage: 52.4,
        uptime: os.uptime(),
      });
    }

    if (command === "read_file_content") {
      const filePath = args?.path;
      if (!filePath) {
        return res.status(400).json({ success: false, error: "Path is required" });
      }
      const safePath = validatePath(filePath);
      if (!fs.existsSync(safePath)) {
        return res.status(400).json({ success: false, error: "File does not exist" });
      }
      const content = fs.readFileSync(safePath, "utf8");
      return res.status(200).json({ success: true, content });
    }

    if (command === "write_file_content") {
      const filePath = args?.path;
      const content = args?.content ?? "";
      if (!filePath) {
        return res.status(400).json({ success: false, error: "Path is required" });
      }
      const safePath = validatePath(filePath);
      fs.writeFileSync(safePath, content, "utf8");
      return res.status(200).json({ success: true });
    }

    if (command === "list_directory") {
      const dirPath = args?.path || ALLOWED_BASE_DIR;
      const safePath = validatePath(dirPath);
      if (!fs.existsSync(safePath)) {
        return res.status(400).json({ success: false, error: "Directory does not exist" });
      }
      const files = fs.readdirSync(safePath);
      const entries = files.map((file) => {
        const fullPath = path.join(safePath, file);
        let isDir = false;
        let size = 0;
        try {
          const stats = fs.statSync(fullPath);
          isDir = stats.isDirectory();
          size = stats.size;
        } catch (e) {
          // Ignore stats errors
        }
        return {
          name: file,
          path: fullPath,
          is_directory: isDir,
          size,
        };
      });
      return res.status(200).json({ success: true, entries });
    }

    if (command === "execute_command") {
      const { command: cmd, args: cmdArgs } = args;
      const fullCmd = `${cmd} ${cmdArgs ? cmdArgs.join(" ") : ""}`.trim();

      // Only allow commands from a strict allowlist
      const allowedBinary = ALLOWED_COMMANDS[fullCmd];
      if (!allowedBinary) {
        return res.status(403).json({
          success: false,
          error: "Command not in allowlist. Only safe read-only commands are permitted.",
        });
      }

      execFile(allowedBinary, ["--version"], { cwd: ALLOWED_BASE_DIR }, (error, stdout, stderr) => {
        return res.status(200).json({
          success: !error,
          output: stdout + (stderr ? `\nError: ${stderr}` : ""),
          exit_code: error ? error.code || 1 : 0,
          stdout,
          stderr,
        });
      });
      return;
    }

    return res.status(400).json({ error: `Command ${command} not supported` });
  } catch (error: any) {
    console.error(`[Desktop Bridge] Error running ${command}:`, error);
    return res.status(500).json({ success: false, error: error.message });
  }
}
