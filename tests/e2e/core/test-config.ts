import * as fs from 'fs';
import * as path from 'path';

export class TestConfig {
  readonly baseUrl: string;
  readonly apiUrl: string;
  readonly timeout: number;
  readonly retries: number;
  readonly headless: boolean;
  readonly testDataDir: string;
  readonly resultsDir: string;
  readonly persona: string;

  constructor() {
    this.baseUrl = process.env.TEST_BASE_URL || 'http://localhost:3000';
    this.apiUrl = process.env.TEST_API_URL || 'http://localhost:5000';
    this.timeout = parseInt(process.env.TEST_TIMEOUT || '30000', 10);
    this.retries = parseInt(process.env.TEST_RETRIES || '3', 10);
    this.headless = process.env.CI === 'true' || process.env.HEADLESS === 'true';
    this.persona = process.env.TEST_PERSONA || 'all';

    // Ensure directories exist
    this.testDataDir = path.join(__dirname, '../../fixtures');
    this.resultsDir = path.join(__dirname, '../../results');

    this.ensureDirectories();
  }

  private ensureDirectories() {
    const dirs = [
      this.testDataDir,
      this.resultsDir,
      path.join(this.resultsDir, 'screenshots'),
      path.join(this.resultsDir, 'allure-results'),
      path.join(this.resultsDir, 'downloads'),
      path.join(this.resultsDir, 'logs')
    ];

    dirs.forEach(dir => {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    });
  }

  get isAllPersonas() {
    return this.persona === 'all';
  }

  get isSpecificPersona() {
    return !this.isAllPersonas;
  }

  get shouldRunPersona(personaName: string) {
    return this.isAllPersonas || this.persona === personaName;
  }

  get apiHeaders() {
    return {
      'Content-Type': 'application/json',
      'User-Agent': 'Atom-E2E-Tests/1.0.0',
    };
  }

  get authHeaders(token: string) {
    return {
      ...this.apiHeaders,
      'Authorization': `Bearer ${token}`,
    };
  }
}

export interface EnvironmentConfig {
  nodeEnv: string;
  isTest: boolean;
  isDev: boolean;
  isProd: boolean;
}

export const getEnvironmentConfig = (): EnvironmentConfig => {
  const nodeEnv = process.env.NODE_ENV || 'test';
  return {
    nodeEnv,
    isTest: nodeEnv === 'test',
    isDev: nodeEnv === 'development',
    isProd: nodeEnv === 'production',
  };
};
