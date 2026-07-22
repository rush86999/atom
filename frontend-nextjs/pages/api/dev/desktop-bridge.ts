import { NextApiRequest, NextApiResponse } from "next";
import fs from "fs";
import path from "path";
import os from "os";
import { exec } from "child_process";

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
      const filePath = args.path;
      if (!filePath) {
        return res.status(400).json({ success: false, error: "Path is required" });
      }
      if (!fs.existsSync(filePath)) {
        return res.status(400).json({ success: false, error: "File does not exist" });
      }
      const content = fs.readFileSync(filePath, "utf8");
      return res.status(200).json({ success: true, content });
    }

    if (command === "write_file_content") {
      const filePath = args.path;
      const content = args.content ?? "";
      if (!filePath) {
        return res.status(400).json({ success: false, error: "Path is required" });
      }
      fs.writeFileSync(filePath, content, "utf8");
      return res.status(200).json({ success: true });
    }

    if (command === "list_directory") {
      const dirPath = args.path || process.cwd();
      if (!fs.existsSync(dirPath)) {
        return res.status(400).json({ success: false, error: "Directory does not exist" });
      }
      const files = fs.readdirSync(dirPath);
      const entries = files.map((file) => {
        const fullPath = path.join(dirPath, file);
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
      const { command: cmd, args: cmdArgs, workingDir } = args;
      const fullCmd = `${cmd} ${cmdArgs ? cmdArgs.join(" ") : ""}`.trim();
      
      exec(fullCmd, { cwd: workingDir || process.cwd() }, (error, stdout, stderr) => {
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
