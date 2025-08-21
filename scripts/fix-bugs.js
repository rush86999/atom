#!/usr/bin/env node

/**
 * Atom Bug Fix and Test Runner
 * Identifies and automatically fixes common issues across web and desktop
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const axios = require('axios');

class AtomBugFixer {
  constructor() {
    this.results = {
      fixed: [],
      identified: [],
      failed: []
    };
  }

  log(level, message) {
    const icon = {
      'FIX': '🛠️',
      'ID': '🔍',
      'ERROR': '❌',
      'SUCCESS': '✅',
      'INFO': 'ℹ️'
    };
    console.log(`${icon[level] || ''} ${message}`);
  }

  async run() {
    console.log('🚀 ATOM BUG FIX & TEST RUNNER\n=============================\n');

    await this.testAndFixDependencies();
    await this.testDatabaseConnection();
    await this.testWebRoutes();
    await this.testBuildAndTypes();
    await this.validateEnvironment();
    await this.suggestFixes();

    this.printSummary();
  }

  async testAndFixDependencies() {
    this.log('INFO', 'Checking dependencies...');

    const packageTypes = [
      { path: 'atomic-docker/app_build_docker/package.json', name: 'Web App' },
      { path: 'desktop/tauri/package.json', name: 'Desktop App' }
    ];

    for (const pkg of packageTypes) {
      const pkgPath = path.join(process.cwd(), pkg.path);

      if (fs.existsSync(pkgPath)) {
        try {
          execSync(`npm install`, { cwd: path.dirname(pkgPath), stdio: 'inherit' });
          this.log('SUCCESS', `${pkg.name} dependencies installed`);
        } catch (error) {
          this.results.identified.push(`Dependencies install failed for ${pkg.name}`);
        }
      }
    }
  }

  async testDatabaseConnection() {
    this.log('INFO', 'Testing database connection...');

    const dbUrl = process.env.DATABASE_URL;
    if (!dbUrl) {
      this.results.identified.push('DATABASE_URL not set');
      this.log('ERROR', 'DATABASE_URL environment variable missing');
      this.log('FIX', 'Set DATABASE_URL="postgresql://user:pass@localhost:5432/atom"');
    } else {
      this.log('SUCCESS', 'DATABASE_URL configured');
    }
  }

  async testWebRoutes() {
    this.log('INFO', 'Testing web routes...');

    const endpoints = [
      { name: 'Health API', url: 'http://localhost:3000/api/health' },
      { name: 'NLP API', url: 'http://localhost:3000/api/agent/nlu', method: 'POST' }
    ];

    for (const endpoint of endpoints) {
      try {
        if (endpoint.method === 'POST') {
          await axios.post(endpoint.url, { message: 'test' }, { timeout: 5000 });
        } else {
          await axios.get(endpoint.url, { timeout: 5000 });
        }
        this.log('SUCCESS', `${endpoint.name} reachable`);
      } catch (error) {
        this.log('ERROR', `${endpoint.name} failed: ${error.message}`);
      }
    }
  }

  async testBuildAndTypes() {
    this.log('INFO', 'Testing build and type checking...');

    try {
      // Test web app build
      const webAppDir = path.join(process.cwd(), 'atomic-docker', 'app_build_docker');
      execSync('npm run build || npm run dev', {
        cwd: webAppDir,
        stdio: 'pipe',
        timeout: 60000
      });
      this.log('SUCCESS', 'Web app build successful');

    } catch (buildError) {
      // Fix common TypeScript issues
      const tsConfigPath = path.join(process.cwd(), 'tsconfig.json');
      if (fs.existsSync(tsConfigPath)) {
        let tsConfig = JSON.parse(fs.readFileSync(tsConfigPath, 'utf8'));

        // Remove vite/client from Next.js project
        if (tsConfig.compilerOptions?.types?.includes('vite/client')) {
          tsConfig.compilerOptions.types = tsConfig.compilerOptions.types.filter(t => t !== 'vite/client');
          fs.writeFileSync(tsConfigPath, JSON.stringify(tsConfig, null, 2));
          this.log('FIX', 'Removed invalid vite/client from tsconfig.json');
          this.results.fixed.push('Removed vite/client from tsconfig.json');
        }
      }
    }
  }

  async validateEnvironment() {
    this.log('INFO', 'Validating environment configuration...');

    const envFile = path.join(process.cwd(), '.env');
    const commonVars = {
      'DATABASE_URL': 'postgresql://user:pass@localhost:
