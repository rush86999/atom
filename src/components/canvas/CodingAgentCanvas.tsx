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
  Code,
  Play,
  Square,
  CheckCircle2,
  XCircle,
  Clock,
  FileCode,
  TestTube,
  Shield,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  History,
  Download,
  Copy,
  Settings,
  RefreshCw,
  FileText,
  Diff
} from 'lucide-react';
import { toast } from 'sonner';
import { useMediaQuery } from '@/hooks/use-media-query';
import { useAccessibilityMirror } from '@/lib/canvas/accessibility';
import { useCodingAgentCanvas, getCodingCanvasContent } from '@/lib/ai/coding-agent-canvas';
import { CodeGenerationResponse, GeneratedFile } from '@/lib/ai/coding-agent';

interface CodingAgentCanvasProps {
  canvasId: string;
  tenantId: string;
  agentId: string;
}

/**
 * CodingAgentCanvas Component
 *
 * Canvas for AI-powered code generation with real-time validation,
 * approval workflow, and history tracking.
 *
 * Features:
 * - Code editor with syntax highlighting (Monaco-style)
 * - Real-time validation feedback display
 * - Approval workflow interface for high-risk code
 * - History view with diff comparison
 * - Accessibility mirror for AI agent context
 * - EpisodeService integration for canvas metadata tracking
 */
export function CodingAgentCanvas({ canvasId, tenantId, agentId }: CodingAgentCanvasProps) {
  const {
    state,
    generateCode,
    validateCode,
    approveCode,
    rejectCode,
    setActiveFile,
    toggleShowTests,
    toggleShowDiff,
    resetCanvas
  } = useCodingAgentCanvas(tenantId, agentId);

  // Form state
  const [requirements, setRequirements] = useState('');
  const [filesToCreate, setFilesToCreate] = useState<string>('');
  const [language, setLanguage] = useState<'typescript' | 'python' | 'rust'>('typescript');
  const [complexity, setComplexity] = useState<'low' | 'medium' | 'high' | 'critical'>('medium');
  const [includeTests, setIncludeTests] = useState(true);

  const isMobile = useMediaQuery('(max-width: 768px)');
  const editorRef = useRef<HTMLDivElement>(null);

  // Accessibility mirror for screen readers and AI agents
  const accessibilityMirror = useAccessibilityMirror({
    canvasId,
    canvasType: 'coding',
    getContent: () => getCodingCanvasContent(
      state.generatedFiles,
      state.currentValidation,
      state.approvalStatus
    ),
  });

  const activeFile = state.generatedFiles[state.activeFileIndex] || null;

  /**
   * Handle code generation
   */
  const handleGenerate = async () => {
    if (!requirements.trim()) {
      toast.error('Please provide requirements');
      return;
    }

    const filesList = filesToCreate
      .split('\n')
      .map(f => f.trim())
      .filter(f => f.length > 0);

    if (filesList.length === 0) {
      toast.error('Please specify at least one file to create');
      return;
    }

    try {
      const response = await generateCode(requirements, filesList, language, {
        complexity,
        includeTests
      });

      if (response.success) {
        toast.success(`Generated ${response.files.length} files in ${response.generationTime.toFixed(1)}s`);

        // Auto-validate if generation succeeded
        if (response.files.length > 0) {
          await validateCode(response.files);
        }
      } else {
        toast.error(response.error || 'Code generation failed');
      }
    } catch (error) {
      console.error('Generation failed:', error);
      toast.error(error instanceof Error ? error.message : 'Code generation failed');
    }
  };

  /**
   * Handle approval
   */
  const handleApprove = async () => {
    if (!state.episodeId) {
      toast.error('No code to approve');
      return;
    }

    try {
      await approveCode(state.episodeId, agentId);
      toast.success('Code approved successfully');
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
      rejectCode(reason);
      toast.success('Code rejected');
    }
  };

  /**
   * Copy code to clipboard
   */
  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast.success('Code copied to clipboard');
    } catch (error) {
      toast.error('Failed to copy code');
    }
  };

  /**
   * Download file
   */
  const handleDownload = (file: GeneratedFile) => {
    const blob = new Blob([file.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.path;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`Downloaded ${file.path}`);
  };

  /**
   * Navigate files
   */
  const navigateFile = (direction: 'prev' | 'next') => {
    if (direction === 'prev' && state.activeFileIndex > 0) {
      setActiveFile(state.activeFileIndex - 1);
    } else if (direction === 'next' && state.activeFileIndex < state.generatedFiles.length - 1) {
      setActiveFile(state.activeFileIndex + 1);
    }
  };

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Code className="h-5 w-5" />
              <CardTitle>Coding Agent</CardTitle>
              <Badge variant="outline">{language}</Badge>
              {state.isGenerating && (
                <Badge variant="secondary" className="animate-pulse">
                  <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                  Generating
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
              {state.generatedFiles.length > 0 && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={toggleShowDiff}
                  >
                    <Diff className="h-4 w-4 mr-1" />
                    {state.showDiff ? 'Hide' : 'Show'} Diff
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={resetCanvas}
                  >
                    <Square className="h-4 w-4 mr-1" />
                    Reset
                  </Button>
                </>
              )}
            </div>
          </div>
          <CardDescription>
            AI-powered code generation with real-time validation and approval workflow
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
        {/* Left Panel: Input */}
        <div className="flex flex-col gap-4 min-h-0">
          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader>
              <CardTitle className="text-lg">Code Generation Request</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col gap-4 min-h-0 overflow-hidden">
              {/* Requirements */}
              <div className="flex-1 flex flex-col gap-2 min-h-0">
                <label className="text-sm font-medium">Requirements</label>
                <Textarea
                  value={requirements}
                  onChange={(e) => setRequirements(e.target.value)}
                  placeholder="Describe the code you want to generate..."
                  className="flex-1 resize-none font-mono text-sm"
                  disabled={state.isGenerating}
                />
              </div>

              {/* Files to Create */}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Files to Create (one per line)</label>
                <Textarea
                  value={filesToCreate}
                  onChange={(e) => setFilesToCreate(e.target.value)}
                  placeholder="src/components/MyComponent.tsx&#10;src/lib/my-service.ts&#10;tests/MyComponent.test.tsx"
                  className="h-24 resize-none font-mono text-sm"
                  disabled={state.isGenerating}
                />
              </div>

              {/* Configuration */}
              <div className="grid grid-cols-2 gap-4">
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
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium">Complexity</label>
                  <select
                    value={complexity}
                    onChange={(e) => setComplexity(e.target.value as any)}
                    className="px-3 py-2 rounded-md border bg-background"
                    disabled={state.isGenerating}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>

              {/* Options */}
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeTests}
                    onChange={(e) => setIncludeTests(e.target.checked)}
                    disabled={state.isGenerating}
                    className="rounded"
                  />
                  Include Tests
                </label>
              </div>

              {/* Generate Button */}
              <Button
                onClick={handleGenerate}
                disabled={state.isGenerating || !requirements.trim()}
                className="w-full"
              >
                {state.isGenerating ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Generate Code
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Right Panel: Output */}
        <div className="flex flex-col gap-4 min-h-0">
          {state.generatedFiles.length === 0 ? (
            <Card className="flex-1 flex items-center justify-center">
              <CardContent className="text-center text-muted-foreground py-12">
                <Code className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No code generated yet</p>
                <p className="text-sm">Fill in the requirements and click Generate</p>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* File Tabs */}
              <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileCode className="h-4 w-4" />
                      <span className="font-medium">
                        {activeFile?.path || 'Select a file'}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {activeFile?.lines} lines
                      </Badge>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigateFile('prev')}
                        disabled={state.activeFileIndex === 0}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <span className="text-sm text-muted-foreground">
                        {state.activeFileIndex + 1} / {state.generatedFiles.length}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigateFile('next')}
                        disabled={state.activeFileIndex === state.generatedFiles.length - 1}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col min-h-0 overflow-hidden">
                  {/* Code Editor */}
                  <ScrollArea className="flex-1 rounded-md border bg-muted/50 p-4">
                    <pre className="font-mono text-sm whitespace-pre-wrap">
                      <code>{activeFile?.content || '// No file selected'}</code>
                    </pre>
                  </ScrollArea>

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2 mt-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => activeFile && handleCopy(activeFile.content)}
                    >
                      <Copy className="h-4 w-4 mr-1" />
                      Copy
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => activeFile && handleDownload(activeFile)}
                    >
                      <Download className="h-4 w-4 mr-1" />
                      Download
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Validation Results */}
              {state.currentValidation && (
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">Validation Results</CardTitle>
                      <Badge
                        variant={state.currentValidation.success ? 'default' : 'destructive'}
                      >
                        {state.currentValidation.qualityScore}/100
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span>Lint: {state.currentValidation.lintErrors.length} errors</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-yellow-500" />
                        <span>Type: {state.currentValidation.typeErrors.length} errors</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-blue-500" />
                        <span>Security: {state.currentValidation.securityIssues.length} issues</span>
                      </div>
                      {state.currentValidation.testResults && (
                        <div className="flex items-center gap-2">
                          <TestTube className="h-4 w-4 text-purple-500" />
                          <span>
                            Tests: {state.currentValidation.testResults.passed} passed
                            {state.currentValidation.testResults.coverage && ` (${state.currentValidation.testResults.coverage}% coverage)`}
                          </span>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Approval Workflow */}
              {state.approvalStatus.requiresApproval && (
                <Card className="border-orange-500">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg text-orange-600">Approval Required</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground mb-4">
                      This code requires approval before deployment due to complexity level or security concerns.
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

              {/* Tests Tab */}
              {state.generatedTests.length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">Generated Tests</CardTitle>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={toggleShowTests}
                      >
                        {state.showTests ? 'Hide' : 'Show'} Tests ({state.generatedTests.length})
                      </Button>
                    </div>
                  </CardHeader>
                  {state.showTests && (
                    <CardContent>
                      <ScrollArea className="h-48 rounded-md border bg-muted/50 p-4">
                        {state.generatedTests.map((test, index) => (
                          <div key={index} className="mb-4">
                            <div className="flex items-center gap-2 mb-2">
                              <TestTube className="h-4 w-4" />
                              <span className="font-medium">{test.path}</span>
                              <Badge variant="outline" className="text-xs">
                                {test.lines} lines
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </ScrollArea>
                    </CardContent>
                  )}
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Export hook for external use
 */
export { useCodingAgentCanvas };
