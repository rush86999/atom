"use strict";
var __createBinding =
  (this && this.__createBinding) ||
  (Object.create
    ? function (o, m, k, k2) {
        if (k2 === undefined) k2 = k;
        var desc = Object.getOwnPropertyDescriptor(m, k);
        if (
          !desc ||
          ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)
        ) {
          desc = {
            enumerable: true,
            get: function () {
              return m[k];
            },
          };
        }
        Object.defineProperty(o, k2, desc);
      }
    : function (o, m, k, k2) {
        if (k2 === undefined) k2 = k;
        o[k2] = m[k];
      });
var __setModuleDefault =
  (this && this.__setModuleDefault) ||
  (Object.create
    ? function (o, v) {
        Object.defineProperty(o, "default", { enumerable: true, value: v });
      }
    : function (o, v) {
        o["default"] = v;
      });
var __importStar =
  (this && this.__importStar) ||
  (function () {
    var ownKeys = function (o) {
      ownKeys =
        Object.getOwnPropertyNames ||
        function (o) {
          var ar = [];
          for (var k in o)
            if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
          return ar;
        };
      return ownKeys(o);
    };
    return function (mod) {
      if (mod && mod.__esModule) return mod;
      var result = {};
      if (mod != null)
        for (var k = ownKeys(mod), i = 0; i < k.length; i++)
          if (k[i] !== "default") __createBinding(result, mod, k[i]);
      __setModuleDefault(result, mod);
      return result;
    };
  })();
Object.defineProperty(exports, "__esModule", { value: true });
exports.getEnvironmentConfig = exports.TestConfig = void 0;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
class TestConfig {
  constructor() {
    this.baseUrl = process.env.TEST_BASE_URL || "http://localhost:3000";
    this.apiUrl = process.env.TEST_API_URL || "http://localhost:5000";
    this.timeout = parseInt(process.env.TEST_TIMEOUT || "30000", 10);
    this.retries = parseInt(process.env.TEST_RETRIES || "3", 10);
    this.headless =
      process.env.CI === "true" || process.env.HEADLESS === "true";
    this.persona = process.env.TEST_PERSONA || "all";
    // Ensure directories exist
    this.testDataDir = path.join(__dirname, "../../fixtures");
    this.resultsDir = path.join(__dirname, "../../results");
    this.ensureDirectories();
  }
  ensureDirectories() {
    const dirs = [
      this.testDataDir,
      this.resultsDir,
      path.join(this.resultsDir, "screenshots"),
      path.join(this.resultsDir, "allure-results"),
      path.join(this.resultsDir, "downloads"),
      path.join(this.resultsDir, "logs"),
    ];
    dirs.forEach((dir) => {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    });
  }
  get isAllPersonas() {
    return this.persona === "all";
  }
  get isSpecificPersona() {
    return !this.isAllPersonas;
  }
  shouldRunPersona(personaName) {
    return this.isAllPersonas || this.persona === personaName;
  }
  get apiHeaders() {
    return {
      "Content-Type": "application/json",
      "User-Agent": "Atom-E2E-Tests/1.0.0",
    };
  }
  authHeaders(token) {
    return {
      ...this.apiHeaders,
      Authorization: `Bearer ${token}`,
    };
  }
}
exports.TestConfig = TestConfig;
const getEnvironmentConfig = () => {
  const nodeEnv = process.env.NODE_ENV || "test";
  return {
    nodeEnv,
    isTest: nodeEnv === "test",
    isDev: nodeEnv === "development",
    isProd: nodeEnv === "production",
  };
};
exports.getEnvironmentConfig = getEnvironmentConfig;
//# sourceMappingURL=test-config.js.map
