export declare class TestConfig {
  readonly baseUrl: string;
  readonly apiUrl: string;
  readonly timeout: number;
  readonly retries: number;
  readonly headless: boolean;
  readonly testDataDir: string;
  readonly resultsDir: string;
  readonly persona: string;
  constructor();
  private ensureDirectories;
  get isAllPersonas(): boolean;
  get isSpecificPersona(): boolean;
  get shouldRunPersona(): boolean;
  get apiHeaders(): {
    "Content-Type": string;
    "User-Agent": string;
  };
  get authHeaders(): {
    Authorization: string;
    "Content-Type": string;
    "User-Agent": string;
  };
}
export interface EnvironmentConfig {
  nodeEnv: string;
  isTest: boolean;
  isDev: boolean;
  isProd: boolean;
}
export declare const getEnvironmentConfig: () => EnvironmentConfig;
//# sourceMappingURL=test-config.d.ts.map
