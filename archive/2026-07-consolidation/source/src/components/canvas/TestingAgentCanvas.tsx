'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  TestTube,
  Play,
  Square,
  CheckCircle2,
  XCircle,
  Clock,
  FileCode,
  Shield,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  History,
  Copy,
  BarChart3,
  Bug,
  RefreshCw,
  FileText,
  Settings
} from 'lucide-react';
import { toast } from 'sonner';
import { useMediaQuery } from '@/hooks/use-media-query';
import { useAccessibilityMirror } from '@/lib/canvas/accessibility';
import { useTestingAgentCanvas, getTestingCanvasContent } from '@/lib/ai/testing-agent-canvas';
import { GeneratedTest } from '@/lib/ai/testing-agent';

interface TestingAgentCanvasProps {
  canvasId: string;
  tenantId: string;
  agentId: string;
}

/**
 * TestingAgentCanvas Component
 *
 * Canvas for AI-powered test generation with real-time validation,
 * approval workflow, and history tracking.
 *
 * Features:
 * - Test generation panel with code input and framework selection
 * - Test execution panel with live results display
 * - Coverage report panel with visual breakdown
 * - Failure analysis panel with fix suggestions
 * - Approval workflow interface for high-risk operations
 * - History view with past executions
 * - Accessibility mirror for AI agent context
 * - EpisodeService integration for canvas metadata tracking
 */
export function TestingAgentCanvas({ canvasId, tenantId, agentId }: TestingAgentCanvasProps) {
  const {
    state,
    generateTests,
    executeTests,
    analyzeFailures,
    approveTests,
    rejectTests,
    setActiveTab,
    setSelectedTest,
    toggleShowHistory,
    resetCanvas
  } = useTestingAgentCanvas(tenantId, agentId);

  // Form state
  const [codeInput, setCodeInput] = useState('');
  const [filePath, setFilePath] = useState('');
  const [testType, setTestType] = useState<'unit' | 'integration' | 'e2e'>('unit');
  const [framework, setFramework] = useState<'vitest' | 'pytest' | 'playwright'>('vitest');
  const [language, setLanguage] = useState<'typescript' | 'python' | 'rust'>('typescript');
  const [context, setContext] = useState('');

  const isMobile = useMediaQuery('(max-width: 768px)');
  const editorRef = useRef<HTMLDivElement>(null);

  // Accessibility mirror for screen readers and AI agents
  const accessibilityMirror = useAccessibilityMirror({
    canvasId,
    canvasType: 'testing',
    getContent: () => getTestingCanvasContent(
      state.currentGeneration,
      state.executionResults,
      state.coverageReport,
      state.approvalStatus
    ),
  });

  const activeTest = state.generatedTests[state.selectedTestIndex] || null;

  /**
   * Handle test generation
   */
  const handleGenerate = async () => {
    if (!codeInput.trim()) {
      toast.error('Please provide code to test');
      return;
    }

    if (!filePath.trim()) {
      toast.error('Please specify file path');
      return;
    }

    try {
      const response = await generateTests(
        [{ path: filePath, content: codeInput }],
        testType,
        framework,
        language,
        { context }
      );

      if (response.success) {
        toast.success(`Generated ${response.testCount} tests in ${response.generationTime.toFixed(1)}s`);
      } else {
        toast.error(response.error || 'Test generation failed');
      }
    } catch (error) {
      console.error('Generation failed:', error);
      toast.error(error instanceof Error ? error.message : 'Test generation failed');
    }
  };

  /**
   * Handle test execution
   */
  const handleExecute = async () => {
    if (state.generatedTests.length === 0) {
      toast.error('No tests to execute');
      return;
    }

    try {
      const testFiles = state.generatedTests.map(t => t.name);
      const response = await executeTests(testFiles, framework);

      if (response.success) {
        toast.success(`Executed tests: ${response.passRate.toFixed(1)}% pass rate`);

        // Auto-analyze failures if any
        if (response.failures && response.failures.length > 0) {
          await analyzeFailures(response);
        }
      } else {
        toast.error(response.error || 'Test execution failed');
      }
    } catch (error) {
      console.error('Execution failed:', error);
      toast.error(error instanceof Error ? error.message : 'Test execution failed');
    }
  };

  /**
   * Handle approval
   */
  const handleApprove = async () => {
    if (!state.episodeId) {
      toast.error('No tests to approve');
      return;
    }

    try {
      await approveTests(state.episodeId, agentId);
      toast.success('Tests approved successfully');
    } catch (error) {
      console.error('Approval failed:', error);
      toast.error(error instanceof Error ? error.message : 'Approval failed');
    }
  };

  /**
   * Handle rejection
   */
  const handleReject = () => {
    const reason = prompt('Rejection reason (optional):');
    if (reason !== null) {
      rejectTests(reason);
      toast.success('Tests rejected');
    }
  };

  /**
   * Copy test to clipboard
   */
  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast.success('Test copied to clipboard');
    } catch (error) {
      toast.error('Failed to copy test');
    }
  };

  /**
   * Navigate tests
   */
  const navigateTest = (direction: 'prev' | 'next') => {
    if (direction === 'prev' && state.selectedTestIndex > 0) {
      setSelectedTest(state.selectedTestIndex - 1);
    } else if (direction === 'next' && state.selectedTestIndex < state.generatedTests.length - 1) {
      setSelectedTest(state.selectedTestIndex + 1);
    }
  };

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TestTube className="h-5 w-5" />
              <CardTitle>Testing Agent</CardTitle>
              <Badge variant="outline">{language}</Badge>
              {state.isGenerating && (
                <Badge variant="secondary" className="animate-pulse">
                  <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                  Generating
                </Badge>
              )}
              {state.isExecuting && (
                <Badge variant="secondary" className="animate-pulse">
                  <Play className="h-3 w-3 mr-1" />
                  Executing
                </Badge>
              )}
              {state.approvalStatus.requiresApproval && (
                <Badge variant="destructive">
                  <Shield className="h-3 w-3 mr-1" />
                  Approval Required
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              {state.generatedTests.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={resetCanvas}
                >
                  <Square className="h-4 w-4 mr-1" />
                  Reset
                </Button>
              )}
            </div>
          </div>
          <CardDescription>
            AI-powered test generation with execution, coverage analysis, and failure analysis
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Main Content */}
      <Tabs value={state.activeTab} onValueChange={(v) => setActiveTab(v as any)}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="generate">Generate</TabsTrigger>
          <TabsTrigger value="execute">Execute</TabsTrigger>
          <TabsTrigger value="coverage">Coverage</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        {/* Generate Tab */}
        <TabsContent value="generate" className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
          {/* Left Panel: Input */}
          <div className="flex flex-col gap-4 min-h-0">
            <Card className="flex-1 flex flex-col min-h-0">
              <CardHeader>
                <CardTitle className="text-lg">Test Generation Request</CardTitle>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col gap-4 min-h-0 overflow-hidden">
                {/* File Path */}
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium">File Path</label>
                  <Input
                    value={filePath}
                    onChange={(e) => setFilePath(e.target.value)}
                    placeholder="src/utils/math.ts"
                    disabled={state.isGenerating}
                  />
                </div>

                {/* Code Input */}
                <div className="flex-1 flex flex-col gap-2 min-h-0">
                  <label className="text-sm font-medium">Code</label>
                  <Textarea
                    value={codeInput}
                    onChange={(e) => setCodeInput(e.target.value)}
                    placeholder="Paste your code here..."
                    className="flex-1 resize-none font-mono text-sm min-h-[200px]"
                    disabled={state.isGenerating}
                  />
                </div>

                {/* Configuration */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Test Type</label>
                    <select
                      value={testType}
                      onChange={(e) => setTestType(e.target.value as any)}
                      className="px-3 py-2 rounded-md border bg-background"
                      disabled={state.isGenerating}
                    >
                      <option value="unit">Unit</option>
                      <option value="integration">Integration</option>
                      <option value="e2e">E2E</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Framework</label>
                    <select
                      value={framework}
                      onChange={(e) => setFramework(e.target.value as any)}
                      className="px-3 py-2 rounded-md border bg-background"
                      disabled={state.isGenerating}
                    >
                      <option value="vitest">Vitest</option>
                      <option value="pytest">pytest</option>
                      <option value="playwright">Playwright</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">Language</label>
                    <select
                      value={language}
                      onChange={(e) => setLanguage(e.target.value as any)}
                      className="px-3 py-2 rounded-md border bg-background"
                      disabled={state.isGenerating}
                    >
                      <option value="typescript">TypeScript</option>
                      <option value="python">Python</option>
                      <option value="rust">Rust</option>
                    </select>
                  </div>
                </div>

                {/* Context */}
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium">Context (optional)</label>
                  <Textarea
                    value={context}
                    onChange={(e) => setContext(e.target.value)}
                    placeholder="Additional context for test generation..."
                    className="h-20 resize-none text-sm"
                    disabled={state.isGenerating}
                  />
                </div>

                {/* Generate Button */}
                <Button
                  onClick={handleGenerate}
                  disabled={state.isGenerating || !codeInput.trim()}
                  className="w-full"
                >
                  {state.isGenerating ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <TestTube className="h-4 w-4 mr-2" />
                      Generate Tests
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Right Panel: Generated Tests */}
          <div className="flex flex-col gap-4 min-h-0">
            {state.generatedTests.length === 0 ? (
              <Card className="flex-1 flex items-center justify-center">
                <CardContent className="text-center text-muted-foreground py-12">
                  <TestTube className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No tests generated yet</p>
                  <p className="text-sm">Provide code and click Generate</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Test List */}
                <Card className="flex-1 flex flex-col min-h-0">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileCode className="h-4 w-4" />
                        <span className="font-medium">
                          {activeTest?.name || 'Select a test'}
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {activeTest?.lineCount} lines
                        </Badge>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigateTest('prev')}
                          disabled={state.selectedTestIndex === 0}
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <span className="text-sm text-muted-foreground">
                          {state.selectedTestIndex + 1} / {state.generatedTests.length}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigateTest('next')}
                          disabled={state.selectedTestIndex === state.generatedTests.length - 1}
                        >
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="flex-1 flex flex-col min-h-0 overflow-hidden">
                    {/* Test Code */}
                    <ScrollArea className="flex-1 rounded-md border bg-muted/50 p-4">
                      <pre className="font-mono text-sm whitespace-pre-wrap">
                        <code>{activeTest?.code || '// No test selected'}</code>
                      </pre>
                    </ScrollArea>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2 mt-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => activeTest && handleCopy(activeTest.code)}
                      >
                        <Copy className="h-4 w-4 mr-1" />
                        Copy
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Approval Workflow */}
                {state.approvalStatus.requiresApproval && (
                  <Card className="border-orange-500">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg text-orange-600">Approval Required</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-4">
                        These tests require approval before execution due to complexity or test type.
                      </p>
                      <div className="flex gap-2">
                        <Button
                          onClick={handleApprove}
                          disabled={state.isApproving}
                          className="flex-1"
                        >
                          <CheckCircle2 className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                        <Button
                          variant="outline"
                          onClick={handleReject}
                          disabled={state.isApproving}
                          className="flex-1"
                        >
                          <XCircle className="h-4 w-4 mr-1" />
                          Reject
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Execution Button */}
                <Button
                  onClick={handleExecute}
                  disabled={state.isExecuting || state.generatedTests.length === 0}
                  className="w-full"
                >
                  {state.isExecuting ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Executing...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Execute Tests
                    </>
                  )}
                </Button>
              </>
            )}
          </div>
        </TabsContent>

        {/* Execute Tab */}
        <TabsContent value="execute" className="min-h-[400px]">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Test Execution Results</CardTitle>
            </CardHeader>
            <CardContent>
              {state.executionResults ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span>Pass Rate: {state.executionResults.passRate.toFixed(1)}%</span>
                    </div>
                    {state.executionResults.failures && state.executionResults.failures.length > 0 && (
                      <div className="flex items-center gap-2">
                        <XCircle className="h-4 w-4 text-red-500" />
                        <span>Failures: {state.executionResults.failures.length}</span>
                      </div>
                    )}
                  </div>

                  {state.executionResults.failures && state.executionResults.failures.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium">Failed Tests</h4>
                      {state.executionResults.failures.map((failure, i) => (
                        <div key={i} className="p-2 border rounded-md bg-red-50 dark:bg-red-950">
                          <p className="font-mono text-sm">{failure.test_name}</p>
                          <p className="text-sm text-muted-foreground">{failure.error_message}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {state.failureAnalysis && state.failureAnalysis.suggestedFixes.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium">Suggested Fixes</h4>
                      {state.failureAnalysis.suggestedFixes.map((fix, i) => (
                        <div key={i} className="p-2 border rounded-md">
                          <p className="text-sm font-medium">{fix.suggestion_type}</p>
                          <p className="text-sm text-muted-foreground">{fix.explanation}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-12">
                  No test results yet. Generate and execute tests to see results.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Coverage Tab */}
        <TabsContent value="coverage" className="min-h-[400px]">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Coverage Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              {state.coverageReport ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4" />
                    <span className="text-sm">
                      Total Coverage: {state.coverageReport.totalCoverage.toFixed(1)}%
                    </span>
                  </div>

                  {state.coverageReport.gaps.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium">Coverage Gaps</h4>
                      {state.coverageReport.gaps.map((gap, i) => (
                        <div key={i} className="p-2 border rounded-md">
                          <div className="flex items-center justify-between">
                            <p className="font-mono text-sm">{gap.file}</p>
                            <Badge variant={gap.priority === 'P0' ? 'destructive' : gap.priority === 'P1' ? 'default' : 'secondary'}>
                              {gap.priority}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {gap.currentCoverage.toFixed(1)}% → {gap.targetCoverage}% (gap: {gap.gap.toFixed(1)}%)
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-12">
                  No coverage data available yet.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="min-h-[400px]">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Execution History</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-center py-12">
                History feature coming soon.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

/**
 * Export hook for external use
 */
export { useTestingAgentCanvas };
