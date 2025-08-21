#!/usr/bin/env node

/**
 * Comprehensive Bug Fixing Test Suite for Atom AI
 * Identifies and automatically fixes integration bugs across Web + Desktop apps
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const axios = require('axios');

class AtomicBugFixer {
  constructor() {
    this.startTime = Date.now();
    this.bugs = [];
    this.fixes = [];
    this.logs = [];
  }

  log(level, message, data = {}) {
    const timestamp = new Date().toISOString();
    const prefix = {
      FIX: '🛠️',
      BUG: '🐛',
      SUCCESS: '✅',
      WARN: '⚠️',
      INFO: 'ℹ️'
    }[level];

    console.log(`${prefix} ${message}`);
    this.logs.push({ timestamp, level, message, data });
  }

  async scanAndFix() {
    console.log('🚀 ATOM COMPREHENSIVE BUG FIXER\n===============================\n');

    await this.verifyEnvironment();
    await this.fixTypeScriptIssues();
    await this.validatePackageVersions();
    await this.checkMissingImports();
    await this.fixImportIssues();
    await this.validateDatabaseConnections();
    await this.testAndFixBuildProcess();
    await this.runE2EEssentialTests();

    this.reportResults();
  }

  async verifyEnvironment() {
    this.log('INFO', 'Checking environment configuration...');

    // Check critical environment variables
    const requiredEnv = ['DATABASE_URL', 'OPENAI_API_KEY', 'NODE_ENV'];
    const missing = requiredEnv.filter(env => !process.env[env]);

    if (missing.length > 0) {
      const fix = `
# Environment fix - add to .env file:
DATABASE_URL="postgresql://username:password@localhost:5432/atom_dev"
OPENAI_API_KEY="your_openai_api_key_here"
NODE_ENV="development"
`;
      fs.writeFileSync(path.join(process.cwd(), '.env.example'), fix.trim());
      this.log('FIX', 'Created .env.example with required configuration');
    }
  }

  fixTypeScriptIssues() {
    this.log('INFO', 'Fixing TypeScript configuration issues...');

    const rootTsConfig = path.join(process.cwd(), 'tsconfig.json');
    if (fs.existsSync(rootTsConfig)) {
      const config = JSON.parse(fs.readFileSync(rootTsConfig, 'utf8'));

      // Fix vite/client in Next.js project
      if (config.compilerOptions?.types?.includes('vite/client')) {
        config.compilerOptions.types = config.compilerOptions.types.filter(t => t !== 'vite/client');
        fs.writeFileSync(rootTsConfig, JSON.stringify(config, null, 2));
        this.log('FIX', 'Removed invalid vite/client from root tsconfig.json');
        this.fixes.push('Fixed TypeScript configuration');
      }
    }
  }

  validatePackageVersions() {
    this.log('INFO', 'Checking package versions and dependencies...');

    // Check web app dependencies
    try {
      const webPackage = JSON.parse(fs.readFileSync(
        path.join(process.cwd(), 'atomic-docker/app_build_docker/package.json'),
        'utf8'
      ));

      // Ensure critical dependencies are present
      const required = ['next', 'react', 'react-dom', 'axios'];
      const missing = required.filter(dep => !webPackage.dependencies[dep]);

      if (missing.length > 0) {
        this.log('BUG', `Missing web dependencies: ${missing.join(', ')}`);
        this.bugs.push(`Web app missing: ${missing.join(', ')}`);

        // Create install script
        const installScript = `npm install ${missing.join(' ')}`;
        fs.writeFileSync(path.join(process.cwd(), 'scripts/fix-web-deps.sh'),
          `cd atomic-docker/app_build_docker && ${installScript}`);
        this.log('FIX', `Created install script for missing dependencies`);
      }
    } catch (error) {
      this.log('WARN', 'Could not check web package.json');
    }
  }

  checkMissingImports() {
    this.log('INFO', 'Checking for missing imports and modules...');

    const checks = [
      {
        path: path.join(process.cwd(), 'desktop/tauri/src-tauri/main.rs'),
        check: (content) => {
          const missing = [];
          if (!content.includes('use rand::rngs::OsRng')) missing.push('rand');
          if (!content.includes('use aes_gcm::aead')) missing.push('aes_gcm-aead');
          return missing;
        }
      },
      {
        path: path.join(process.cwd(), 'atomic-docker/project/functions/python_api_service/test_search_routes.py'),
        check: (content) => {
          const unused = [];
          if
