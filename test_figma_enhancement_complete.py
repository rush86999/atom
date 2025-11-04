import { Skill, SkillContext, SkillResult } from '../../../types/skillTypes';

/**
 * Test Figma Enhancement
 * Complete test of Figma enhancement including enhanced API and skills
 */

interface TestResult {
  testName: string;
  passed: boolean;
  error?: string;
  details?: any;
  duration: number;
}

export class FigmaEnhancementTest {
  private results: TestResult[] = [];
  private figmaApiUrl = 'http://localhost:8000';
  private figmaApiKey = process.env.FIGMA_ACCESS_TOKEN || 'test_token';

  async runCompleteTest(): Promise<{
    passed: number;
    failed: number;
    total: number;
    results: TestResult[];
    overallSuccess: boolean;
  }> {
    console.log('🧪 Starting Complete Figma Enhancement Test...');
    const startTime = Date.now();

    // Test 1: Enhanced API Health Check
    await this.testEnhancedApiHealth();

    // Test 2: Enhanced File Operations
    await this.testEnhancedFileOperations();

    // Test 3: Enhanced Component Operations
    await this.testEnhancedComponentOperations();

    // Test 4: Enhanced Comment Operations
    await this.testEnhancedCommentOperations();

    // Test 5: Enhanced Team Operations
    await this.testEnhancedTeamOperations();

    // Test 6: Enhanced Search Operations
    await this.testEnhancedSearchOperations();

    // Test 7: Skills Implementation
    await this.testSkillsImplementation();

    // Test 8: Frontend Integration
    await this.testFrontendIntegration();

    // Test 9: Performance Tests
    await this.testPerformance();

    // Test 10: Error Handling Tests
    await this.testErrorHandling();

    const endTime = Date.now();
    const totalDuration = endTime - startTime;

    const passed = this.results.filter(r => r.passed).length;
    const failed = this.results.filter(r => !r.passed).length;
    const total = this.results.length;

    console.log(`\n🎯 **FIGMA ENHANCEMENT TEST COMPLETE**`);
    console.log(`⏱️ Total Duration: ${totalDuration}ms`);
    console.log(`✅ Passed: ${passed}/${total}`);
    console.log(`❌ Failed: ${failed}/${total}`);
    console.log(`📊 Success Rate: ${Math.round((passed/total) * 100)}%`);

    // Log detailed results
    this.results.forEach(result => {
      const status = result.passed ? '✅' : '❌';
      const duration = `(${result.duration}ms)`;
      console.log(`${status} ${result.testName} ${duration}`);
      if (result.error) {
        console.log(`    Error: ${result.error}`);
      }
      if (result.details) {
        console.log(`    Details: ${JSON.stringify(result.details, null, 2)}`);
      }
    });

    return {
      passed,
      failed,
      total,
      results: this.results,
      overallSuccess: passed === total
    };
  }

  private async testEnhancedApiHealth(): Promise<void> {
    const testName = 'Enhanced API Health Check';
    const startTime = Date.now();

    try {
      const response = await fetch(`${this.figmaApiUrl}/api/integrations/figma/health`);
      const data = await response.json();

      const isHealthy = data.status === 'healthy' || data.service_available;

      this.results.push({
        testName,
        passed: isHealthy,
        details: data,
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testEnhancedFileOperations(): Promise<void> {
    const testName = 'Enhanced File Operations';
    const startTime = Date.now();

    try {
      // Test file listing
      const listResponse = await fetch(`${this.figmaApiUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'test_user',
          operation: 'list',
          limit: 10
        })
      });

      const listData = await listResponse.json();
      const listWorking = listData.ok || (listData.data && Array.isArray(listData.data.files));

      // Test file creation
      const createResponse = await fetch(`${this.figmaApiUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'test_user',
          operation: 'create',
          data: {
            name: 'Test File Created via Enhanced API',
            description: 'Test file created by enhancement test'
          }
        })
      });

      const createData = await createResponse.json();
      const createWorking = createData.ok || createData.file;

      this.results.push({
        testName,
        passed: listWorking && createWorking,
        details: {
          listWorking,
          createWorking,
          listResponse: listData,
          createResponse: createData
        },
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testEnhancedComponentOperations(): Promise<void> {
    const testName = 'Enhanced Component Operations';
    const startTime = Date.now();

    try {
      // Test component listing
      const response = await fetch(`${this.figmaApiUrl}/api/integrations/figma/components`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'test_user',
          file_key: 'test_file_key',
          operation: 'list',
          limit: 10
        })
      });

      const data = await response.json();
      const working = data.ok || (data.data && Array.isArray(data.data.components));

      this.results.push({
        testName,
        passed: working,
        details: data,
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testEnhancedCommentOperations(): Promise<void> {
    const testName = 'Enhanced Comment Operations';
    const startTime = Date.now();

    try {
      // Test comment posting
      const response = await fetch(`${this.figmaApiUrl}/api/integrations/figma/files/test_file_key/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'test_user',
          message: 'Test comment from enhancement test',
          client_id: 'test_client'
        })
      });

      const data = await response.json();
      const working = data.ok || data.comment;

      this.results.push({
        testName,
        passed: working,
        details: data,
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testEnhancedTeamOperations(): Promise<void> {
    const testName = 'Enhanced Team Operations';
    const startTime = Date.now();

    try {
      // Test team listing
      const response = await fetch(`${this.figmaApiUrl}/api/integrations/figma/teams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'test_user',
          limit: 10
        })
      });

      const data = await response.json();
      const working = data.ok || (data.data && Array.isArray(data.data.teams));

      this.results.push({
        testName,
        passed: working,
        details: data,
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testEnhancedSearchOperations(): Promise<void> {
    const testName = 'Enhanced Search Operations';
    const startTime = Date.now();

    try {
      // Test global search
      const response = await fetch(`${this.figmaApiUrl}/api/integrations/figma/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'test_user',
          query: 'test button',
          type: 'global',
          limit: 10
        })
      });

      const data = await response.json();
      const working = data.ok || (data.data && Array.isArray(data.data.results));

      this.results.push({
        testName,
        passed: working,
        details: data,
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testSkillsImplementation(): Promise<void> {
    const testName = 'Skills Implementation';
    const startTime = Date.now();

    try {
      // Test if skills file exists and has expected structure
      const skillsResponse = await fetch(`${this.figmaApiUrl}/skills/figmaSkills.ts`, {
        method: 'GET'
      });

      let skillsWorking = false;
      if (skillsResponse.ok) {
        const skillsContent = await skillsResponse.text();
        skillsWorking = skillsContent.includes('FigmaCreateFileSkill') &&
                         skillsContent.includes('FigmaListFilesSkill') &&
                         skillsContent.includes('FigmaSearchComponentsSkill') &&
                         skillsContent.includes('FigmaAddFeedbackSkill');
      }

      // Test skills execution
      const skillResponse = await fetch(`${this.figmaApiUrl}/api/skills/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill_id: 'figma_create_file',
          context: {
            user: { id: 'test_user', name: 'Test User' },
            intent: 'Create a new Figma file called Test Design',
            entities: [{ type: 'file_name', value: 'Test Design' }]
          }
        })
      });

      const skillData = await skillResponse.json();
      const skillWorking = skillData.ok || skillData.success;

      this.results.push({
        testName,
        passed: skillsWorking && skillWorking,
        details: {
          skillsWorking,
          skillWorking,
          skillsResponse: skillsResponse.ok,
          skillResponse: skillData
        },
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testFrontendIntegration(): Promise<void> {
    const testName = 'Frontend Integration';
    const startTime = Date.now();

    try {
      // Test if frontend component exists
      const componentResponse = await fetch(`${this.figmaApiUrl}/src/ui-shared/integrations/figma/components/FigmaManager.tsx`, {
        method: 'GET'
      });

      let componentWorking = false;
      if (componentResponse.ok) {
        const componentContent = await componentResponse.text();
        componentWorking = componentContent.includes('FigmaIntegrationManager') &&
                            componentContent.includes('useToast') &&
                            componentContent.includes('Tabs') &&
                            componentContent.includes('files') &&
                            componentContent.includes('components') &&
                            componentContent.includes('teams');
      }

      this.results.push({
        testName,
        passed: componentWorking,
        details: {
          componentWorking,
          componentExists: componentResponse.ok
        },
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testPerformance(): Promise<void> {
    const testName = 'Performance Tests';
    const startTime = Date.now();

    try {
      // Test API response time
      const apiStartTime = Date.now();
      const response = await fetch(`${this.figmaApiUrl}/api/integrations/figma/health`);
      const apiEndTime = Date.now();
      const apiResponseTime = apiEndTime - apiStartTime;

      // Test file listing performance
      const filesStartTime = Date.now();
      const filesResponse = await fetch(`${this.figmaApiUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'test_user',
          operation: 'list',
          limit: 50
        })
      });
      const filesEndTime = Date.now();
      const filesResponseTime = filesEndTime - filesStartTime;

      const apiFast = apiResponseTime < 500; // Should be under 500ms
      const filesFast = filesResponseTime < 2000; // Should be under 2s

      this.results.push({
        testName,
        passed: apiFast && filesFast,
        details: {
          apiResponseTime,
          filesResponseTime,
          apiFast,
          filesFast
        },
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  private async testErrorHandling(): Promise<void> {
    const testName = 'Error Handling Tests';
    const startTime = Date.now();

    try {
      // Test 404 handling
      const response404 = await fetch(`${this.figmaApiUrl}/api/integrations/figma/nonexistent`);
      const handles404 = response404.status === 404;

      // Test invalid request handling
      const response400 = await fetch(`${this.figmaApiUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          // Missing user_id
          operation: 'list'
        })
      });
      const data400 = await response400.json();
      const handles400 = response400.status === 400 || !data400.ok;

      // Test malformed JSON handling
      const response500 = await fetch(`${this.figmaApiUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: 'invalid json'
      });
      const handles500 = response500.status === 500 || response500.status === 400;

      this.results.push({
        testName,
        passed: handles404 && handles400 && handles500,
        details: {
          handles404,
          handles400,
          handles500,
          response404: response404.status,
          response400: response400.status,
          response500: response500.status
        },
        duration: Date.now() - startTime
      });

    } catch (error) {
      this.results.push({
        testName,
        passed: false,
        error: error instanceof Error ? error.message : String(error),
        duration: Date.now() - startTime
      });
    }
  }

  /**
   * Test specific skill execution
   */
  async testSkill(skillId: string, context: SkillContext): Promise<SkillResult> {
    try {
      const response = await fetch(`${this.figmaApiUrl}/api/skills/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill_id: skillId,
          context
        })
      });

      const result = await response.json();

      return {
        success: result.ok || result.success,
        message: result.message || result.error?.message || 'Skill executed',
        data: result.data || result,
        actions: result.actions || []
      };

    } catch (error) {
      return {
        success: false,
        message: `Error executing skill ${skillId}: ${error}`,
        error: error as any
      };
    }
  }

  /**
   * Generate test report
   */
  generateTestReport(): string {
    const passed = this.results.filter(r => r.passed).length;
    const failed = this.results.filter(r => !r.passed).length;
    const total = this.results.length;
    const successRate = Math.round((passed/total) * 100);

    let report = `# Figma Enhancement Test Report\n\n`;
    report += `## Summary\n`;
    report += `- Total Tests: ${total}\n`;
    report += `- Passed: ${passed}\n`;
    report += `- Failed: ${failed}\n`;
    report += `- Success Rate: ${successRate}%\n\n`;

    report += `## Test Results\n\n`;
    this.results.forEach(result => {
      const status = result.passed ? '✅' : '❌';
      report += `${status} **${result.testName}** (${result.duration}ms)\n`;
      
      if (result.error) {
        report += `   Error: ${result.error}\n`;
      }
      
      if (result.details) {
        report += `   Details:\n   \`\`\`json\n   ${JSON.stringify(result.details, null, 2)}\n   \`\`\`\n`;
      }
      
      report += `\n`;
    });

    return report;
  }

  /**
   * Export results to JSON
   */
  exportResults(): string {
    return JSON.stringify({
      summary: {
        passed: this.results.filter(r => r.passed).length,
        failed: this.results.filter(r => !r.passed).length,
        total: this.results.length,
        successRate: Math.round((this.results.filter(r => r.passed).length / this.results.length) * 100)
      },
      results: this.results,
      timestamp: new Date().toISOString()
    }, null, 2);
  }
}

// Export test class and factory function
export const createFigmaEnhancementTest = () => new FigmaEnhancementTest();
export default FigmaEnhancementTest;