#!/usr/bin/env node

/**
 * Enhanced Workflow System - Master Integration Script
 * 
 * This script orchestrates the complete integration of all enhanced workflow components
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

class MasterIntegration {
  constructor() {
    this.setupDirectories();
  }

  async runFullIntegration(): Promise<void> {
    console.log('🚀 Starting Enhanced Workflow System Integration');
    console.log('=' .repeat(60));

    try {
      // Step 1: Build all components
      await this.buildComponents();
      
      // Step 2: Run comprehensive tests
      await this.runComprehensiveTests();
      
      // Step 3: Generate documentation
      await this.generateAllDocumentation();
      
      // Step 4: Create deployment packages
      await this.createDeploymentPackages();
      
      // Step 5: Run performance benchmarks
      await this.runPerformanceBenchmarks();
      
      console.log('\n🎉 Enhanced Workflow System Integration Complete!');
      console.log('\n📋 Next Steps:');
      console.log('1. Review test results');
      console.log('2. Validate documentation');
      console.log('3. Deploy to staging environment');
      console.log('4. Run end-to-end tests');
      console.log('5. Deploy to production');
      
    } catch (error) {
      console.error(`❌ Integration failed: ${error.message}`);
      process.exit(1);
    }
  }

  private setupDirectories(): void {
    const dirs = [
      'dist',
      'logs',
      'temp',
      'deployments/staging',
      'deployments/production'
    ];

    dirs.forEach(dir => {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
        console.log(`📁 Created directory: ${dir}`);
      }
    });
  }

  private async buildComponents(): Promise<void> {
    console.log('\n🔨 Building Components...');
    
    try {
      // Build TypeScript
      console.log('  🔨 Building TypeScript...');
      execSync('npx tsc --build', { stdio: 'inherit' });
      
      // Run type checking
      console.log('  🔍 Type checking...');
      execSync('npx tsc --noEmit', { stdio: 'inherit' });
      
      // Run linting
      console.log('  🧹 Linting...');
      execSync('npx eslint src --ext .ts,.tsx', { stdio: 'inherit' });
      
      console.log('✅ Components built successfully');
    } catch (error) {
      throw new Error('Component build failed');
    }
  }

  private async runComprehensiveTests(): Promise<void> {
    console.log('\n🧪 Running Comprehensive Tests...');
    
    try {
      // Unit tests
      console.log('  🧪 Running unit tests...');
      execSync('npm run test:unit', { stdio: 'inherit' });
      
      // Integration tests
      console.log('  🔗 Running integration tests...');
      execSync('npm run test:integration', { stdio: 'inherit' });
      
      // E2E tests
      console.log('  🌐 Running E2E tests...');
      execSync('npm run test:e2e', { stdio: 'inherit' });
      
      // Performance tests
      console.log('  ⚡ Running performance tests...');
      execSync('npm run test:performance', { stdio: 'inherit' });
      
      console.log('✅ All tests passed');
    } catch (error) {
      throw new Error('Comprehensive tests failed');
    }
  }

  private async generateAllDocumentation(): Promise<void> {
    console.log('\n📚 Generating Documentation...');
    
    try {
      // API documentation
      console.log('  📖 Generating API documentation...');
      execSync('node scripts/generate-api-docs.js', { stdio: 'inherit' });
      
      // Component documentation
      console.log('  🧩 Generating component documentation...');
      execSync('node scripts/generate-component-docs.js', { stdio: 'inherit' });
      
      // User guides
      console.log('  📚 Generating user guides...');
      execSync('node scripts/generate-user-guides.js', { stdio: 'inherit' });
      
      console.log('✅ Documentation generated successfully');
    } catch (error) {
      throw new Error('Documentation generation failed');
    }
  }

  private async createDeploymentPackages(): Promise<void> {
    console.log('\n📦 Creating Deployment Packages...');
    
    try {
      // Create staging package
      console.log('  📦 Creating staging package...');
      execSync('npm run build:staging', { stdio: 'inherit' });
      
      // Create production package
      console.log('  📦 Creating production package...');
      execSync('npm run build:production', { stdio: 'inherit' });
      
      console.log('✅ Deployment packages created successfully');
    } catch (error) {
      throw new Error('Deployment package creation failed');
    }
  }

  private async runPerformanceBenchmarks(): Promise<void> {
    console.log('\n⚡ Running Performance Benchmarks...');
    
    try {
      console.log('  🏃 Running workflow execution benchmarks...');
      execSync('node scripts/benchmark-workflows.js', { stdio: 'inherit' });
      
      console.log('  🤖 Running AI performance benchmarks...');
      execSync('node scripts/benchmark-ai.js', { stdio: 'inherit' });
      
      console.log('  🔀 Running branch evaluation benchmarks...');
      execSync('node scripts/benchmark-branches.js', { stdio: 'inherit' });
      
      console.log('✅ Performance benchmarks completed');
    } catch (error) {
      throw new Error('Performance benchmarks failed');
    }
  }
}

// Run integration
if (require.main === module) {
  const integration = new MasterIntegration();
  integration.runFullIntegration().catch(console.error);
}

module.exports = MasterIntegration;
