import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface ShellCommandResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  success: boolean;
  duration: number;
}

export interface ShellCommandOptions {
  cwd?: string;
  timeout?: number;
  env?: NodeJS.ProcessEnv;
  shell?: string;
}

/**
 * Execute a shell command and return the result
 */
export async function runShellCommand(
  command: string,
  options: ShellCommandOptions = {}
): Promise<ShellCommandResult> {
  const startTime = Date.now();

  try {
    const { stdout, stderr } = await execAsync(command, {
      cwd: options.cwd || process.cwd(),
      timeout: options.timeout || 30000, // 30 seconds default timeout
      env: { ...process.env, ...options.env },
      shell: options.shell || '/bin/bash',
    });

    const duration = Date.now() - startTime;

    return {
      stdout: stdout.trim(),
      stderr: stderr.trim(),
      exitCode: 0,
      success: true,
      duration,
    };
  } catch (error: any) {
    const duration = Date.now() - startTime;

    return {
      stdout: error.stdout?.trim() || '',
      stderr: error.stderr?.trim() || error.message,
      exitCode: error.code || 1,
      success: false,
      duration,
    };
  }
}

/**
 * Execute multiple shell commands in sequence
 */
export async function runShellCommands(
  commands: string[],
  options: ShellCommandOptions = {}
): Promise<ShellCommandResult[]> {
  const results: ShellCommandResult[] = [];

  for (const command of commands) {
    const result = await runShellCommand(command, options);
    results.push(result);

    // Stop execution if a command fails
    if (!result.success) {
      break;
    }
  }

  return results;
}

/**
 * Execute a shell command with real-time output
 */
export async function runShellCommandWithStream(
  command: string,
  options: ShellCommandOptions = {},
  onOutput?: (data: string) => void,
  onError?: (data: string) => void
): Promise<ShellCommandResult> {
  return new Promise((resolve) => {
    const startTime = Date.now();
    const childProcess = exec(command, {
      cwd: options.cwd || process.cwd(),
      timeout: options.timeout || 30000,
      env: { ...process.env, ...options.env },
      shell: options.shell || '/bin/bash',
    });

    let stdout = '';
    let stderr = '';

    childProcess.stdout?.on('data', (data: string) => {
      stdout += data;
      onOutput?.(data);
    });

    childProcess.stderr?.on('data', (data: string) => {
      stderr += data;
      onError?.(data);
    });

    childProcess.on('close', (code: number) => {
      const duration = Date.now() - startTime;

      resolve({
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        exitCode: code || 0,
        success: code === 0,
        duration,
      });
    });

    childProcess.on('error', (error: Error) => {
      const duration = Date.now() - startTime;

      resolve({
        stdout: stdout.trim(),
        stderr: error.message,
        exitCode: 1,
        success: false,
        duration,
      });
    });
  });
}

/**
 * Check if a command exists in the system PATH
 */
export async function commandExists(command: string): Promise<boolean> {
  try {
    const result = await runShellCommand(`command -v ${command}`);
    return result.success && result.stdout.includes(command);
  } catch {
    return false;
  }
}

/**
 * Execute a shell command with elevated privileges (sudo)
 */
export async function runShellCommandWithSudo(
  command: string,
  options: ShellCommandOptions = {}
): Promise<ShellCommandResult> {
  return runShellCommand(`sudo ${command}`, options);
}

/**
 * Execute a shell script from a file
 */
export async function runShellScript(
  scriptPath: string,
  options: ShellCommandOptions = {}
): Promise<ShellCommandResult> {
  return runShellCommand(`bash ${scriptPath}`, options);
}

/**
 * Execute a command and parse JSON output
 */
export async function runShellCommandJson<T>(
  command: string,
  options: ShellCommandOptions = {}
): Promise<{ data: T | null; result: ShellCommandResult }> {
  const result = await runShellCommand(command, options);

  if (!result.success || !result.stdout) {
    return { data: null, result };
  }

  try {
    const data = JSON.parse(result.stdout) as T;
    return { data, result };
  } catch (error) {
    return {
      data: null,
      result: {
        ...result,
        stderr: `Failed to parse JSON: ${error.message}\n${result.stderr}`,
        success: false,
      },
    };
  }
}

/**
 * Get system information using shell commands
 */
export async function getSystemInfo(): Promise<{
  platform: string;
  arch: string;
  nodeVersion: string;
  npmVersion: string;
  gitVersion: string;
}> {
  const [platform, arch, nodeVersion, npmVersion, gitVersion] = await Promise.all([
    runShellCommand('uname -s'),
    runShellCommand('uname -m'),
    runShellCommand('node --version'),
    runShellCommand('npm --version'),
    runShellCommand('git --version'),
  ]);

  return {
    platform: platform.success ? platform.stdout : 'unknown',
    arch: arch.success ? arch.stdout : 'unknown',
    nodeVersion: nodeVersion.success ? nodeVersion.stdout : 'unknown',
    npmVersion: npmVersion.success ? npmVersion.stdout : 'unknown',
    gitVersion: gitVersion.success ? gitVersion.stdout : 'unknown',
  };
}

export default {
  runShellCommand,
  runShellCommands,
  runShellCommandWithStream,
  runShellCommandWithSudo,
  runShellScript,
  runShellCommandJson,
  commandExists,
  getSystemInfo,
};
