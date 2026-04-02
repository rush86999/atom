/**
 * Testing Agent Canvas Client
 *
 * Frontend client for AI Testing Agent canvas operations.
 * Integrates with existing TestingAgentService for test generation,
 * execution, coverage analysis, and failure analysis.
 */

import { useState, useCallback } from 'react'
import { testingAgentService, GeneratedTest, TestExecutionResponse, FailureAnalysisResponse } from './testing-agent'

export interface TestGenerationResult {
  success: boolean
  generatedTests: GeneratedTest[]
  testCount: number
  framework: string
  language: string
  complexityScore: number
  requiresApproval: boolean
  approvalReason?: string
  episodeId: string
  tokensUsed: number
  generationTime: number
  edgeCasesIdentified: string[]
  error?: string
}

export interface CoverageReport {
  totalCoverage: number
  files: Record<string, {
    lineCoverage: number
    branchCoverage?: number
    functionCoverage?: number
  }>
  gaps: Array<{
    file: string
    currentCoverage: number
    targetCoverage: number
    gap: number
    priority: 'P0' | 'P1' | 'P2'
    uncoveredLines: number[]
  }>
  timestamp: string
}

export interface TestingCanvasState {
  // Test generation state
  generatedTests: GeneratedTest[]
  currentGeneration: TestGenerationResult | null
  approvalStatus: {
    requiresApproval: boolean
    approvedBy: string | null
    approvedAt: string | null
    rejectionReason: string | null
  }

  // Test execution state
  executionResults: TestExecutionResponse | null
  isExecuting: boolean

  // Coverage state
  coverageReport: CoverageReport | null
  isAnalyzingCoverage: boolean

  // Failure analysis state
  failureAnalysis: FailureAnalysisResponse | null
  isAnalyzingFailures: boolean

  // UI state
  activeTab: 'generate' | 'execute' | 'coverage' | 'history'
  selectedTestIndex: number
  showHistory: boolean

  // Loading states
  isGenerating: boolean
  isApproving: boolean

  // Episode tracking
  episodeId: string | null
}

const initialState: TestingCanvasState = {
  generatedTests: [],
  currentGeneration: null,
  approvalStatus: {
    requiresApproval: false,
    approvedBy: null,
    approvedAt: null,
    rejectionReason: null
  },
  executionResults: null,
  isExecuting: false,
  coverageReport: null,
  isAnalyzingCoverage: false,
  failureAnalysis: null,
  isAnalyzingFailures: false,
  activeTab: 'generate',
  selectedTestIndex: 0,
  showHistory: false,
  isGenerating: false,
  isApproving: false,
  episodeId: null
}

/**
 * Testing Agent Canvas Hook
 *
 * Manages state for testing agent canvas operations including
 * test generation, execution, coverage analysis, and failure analysis.
 */
export function useTestingAgentCanvas(tenantId: string, agentId: string) {
  const [state, setState] = useState<TestingCanvasState>(initialState)

  /**
   * Generate tests from code
   */
  const generateTests = useCallback(async (
    codeFiles: Array<{ path: string, content: string }>,
    testType: 'unit' | 'integration' | 'e2e',
    framework?: string,
    language: 'typescript' | 'python' | 'rust' = 'typescript',
    options?: {
      context?: string
      dependencies?: string[]
      userWorkflow?: string
      pages?: string[]
    }
  ): Promise<TestGenerationResult> => {
    setState(prev => ({ ...prev, isGenerating: true }))

    try {
      const response = await testingAgentService.generateTests({
        tenantId,
        agentId,
        codeFiles,
        testType,
        framework,
        language,
        context: options?.context,
        dependencies: options?.dependencies,
        userWorkflow: options?.userWorkflow,
        pages: options?.pages
      })

      setState(prev => ({
        ...prev,
        generatedTests: response.generatedTests,
        currentGeneration: response,
        approvalStatus: {
          requiresApproval: response.requiresApproval,
          approvedBy: null,
          approvedAt: null,
          rejectionReason: null
        },
        episodeId: response.episodeId,
        isGenerating: false,
        selectedTestIndex: response.generatedTests.length > 0 ? 0 : -1
      }))

      return response
    } catch (error) {
      setState(prev => ({ ...prev, isGenerating: false }))
      throw error
    }
  }, [tenantId, agentId])

  /**
   * Execute tests and get results
   */
  const executeTests = useCallback(async (
    testFiles: string[],
    framework: 'vitest' | 'pytest' | 'playwright'
  ): Promise<TestExecutionResponse> => {
    setState(prev => ({ ...prev, isExecuting: true }))

    try {
      const response = await testingAgentService.executeTests({
        tenantId,
        agentId,
        testFiles,
        framework
      })

      setState(prev => ({
        ...prev,
        executionResults: response,
        isExecuting: false
      }))

      return response
    } catch (error) {
      setState(prev => ({ ...prev, isExecuting: false }))
      throw error
    }
  }, [tenantId, agentId])

  /**
   * Analyze test failures
   */
  const analyzeFailures = useCallback(async (
    testResults: any
  ): Promise<FailureAnalysisResponse> => {
    setState(prev => ({ ...prev, isAnalyzingFailures: true }))

    try {
      const response = await testingAgentService.analyzeFailures({
        tenantId,
        agentId,
        testResults
      })

      setState(prev => ({
        ...prev,
        failureAnalysis: response,
        isAnalyzingFailures: false
      }))

      return response
    } catch (error) {
      setState(prev => ({ ...prev, isAnalyzingFailures: false }))
      throw error
    }
  }, [tenantId, agentId])

  /**
   * Approve generated tests
   */
  const approveTests = useCallback(async (episodeId: string, approverId: string) => {
    setState(prev => ({ ...prev, isApproving: true }))

    try {
      const response = await testingAgentService.approveTests(episodeId, approverId)

      setState(prev => ({
        ...prev,
        approvalStatus: {
          requiresApproval: false,
          approvedBy: approverId,
          approvedAt: new Date().toISOString(),
          rejectionReason: null
        },
        isApproving: false
      }))

      return response
    } catch (error) {
      setState(prev => ({ ...prev, isApproving: false }))
      throw error
    }
  }, [])

  /**
   * Reject generated tests
   */
  const rejectTests = useCallback((reason: string) => {
    setState(prev => ({
      ...prev,
      approvalStatus: {
        ...prev.approvalStatus,
        requiresApproval: false,
        rejectionReason: reason
      }
    }))
  }, [])

  /**
   * Set active tab
   */
  const setActiveTab = useCallback((tab: 'generate' | 'execute' | 'coverage' | 'history') => {
    setState(prev => ({ ...prev, activeTab: tab }))
  }, [])

  /**
   * Set selected test index
   */
  const setSelectedTest = useCallback((index: number) => {
    setState(prev => ({ ...prev, selectedTestIndex: index }))
  }, [])

  /**
   * Toggle history view
   */
  const toggleShowHistory = useCallback(() => {
    setState(prev => ({ ...prev, showHistory: !prev.showHistory }))
  }, [])

  /**
   * Reset canvas state
   */
  const resetCanvas = useCallback(() => {
    setState(initialState)
  }, [])

  return {
    // State
    state,

    // Actions
    generateTests,
    executeTests,
    analyzeFailures,
    approveTests,
    rejectTests,
    setActiveTab,
    setSelectedTest,
    toggleShowHistory,
    resetCanvas
  }
}

/**
 * Format test generation result for accessibility mirror
 */
export function formatTestGenerationResult(result: TestGenerationResult | null): string[] {
  if (!result) return ['No tests generated yet']

  const lines: string[] = []

  lines.push(`Generated ${result.testCount} tests`)
  lines.push(`Framework: ${result.framework}`)
  lines.push(`Language: ${result.language}`)
  lines.push(`Complexity Score: ${result.complexityScore}/10`)
  lines.push(`Tokens Used: ${result.tokensUsed}`)
  lines.push(`Generation Time: ${result.generationTime.toFixed(2)}s`)

  if (result.edgeCasesIdentified.length > 0) {
    lines.push(`Edge Cases: ${result.edgeCasesIdentified.join(', ')}`)
  }

  return lines
}

/**
 * Format test execution results for accessibility mirror
 */
export function formatExecutionResults(results: TestExecutionResponse | null): string[] {
  if (!results) return ['No tests executed yet']

  const lines: string[] = []

  lines.push(`Framework: ${results.framework}`)
  lines.push(`Pass Rate: ${results.passRate.toFixed(1)}%`)

  if (results.failures && results.failures.length > 0) {
    lines.push(`Failures: ${results.failures.length}`)
    results.failures.forEach((f, i) => {
      lines.push(`  ${i + 1}. ${f.testName}: ${f.errorMessage || 'Unknown error'}`)
    })
  }

  return lines
}

/**
 * Format coverage report for accessibility mirror
 */
export function formatCoverageReport(coverage: CoverageReport | null): string[] {
  if (!coverage) return ['No coverage data available']

  const lines: string[] = []

  lines.push(`Total Coverage: ${coverage.totalCoverage.toFixed(1)}%`)

  if (coverage.gaps.length > 0) {
    lines.push(`Coverage Gaps: ${coverage.gaps.length}`)
    coverage.gaps.forEach(gap => {
      lines.push(`  ${gap.file}: ${gap.currentCoverage.toFixed(1)}% (target: ${gap.targetCoverage}%) [${gap.priority}]`)
    })
  }

  return lines
}

/**
 * Format approval status for accessibility mirror
 */
export function formatApprovalStatus(status: TestingCanvasState['approvalStatus']): string[] {
  const lines: string[] = []

  if (status.requiresApproval) {
    lines.push('Approval Required: Tests need approval before deployment')
  } else if (status.approvedBy) {
    lines.push(`Approved by: ${status.approvedBy} at ${status.approvedAt}`)
  } else if (status.rejectionReason) {
    lines.push(`Rejected: ${status.rejectionReason}`)
  } else {
    lines.push('Status: Pending review')
  }

  return lines
}

/**
 * Format test for accessibility mirror
 */
export function formatTest(test: GeneratedTest, index: number): string[] {
  return [
    `Test ${index + 1}: ${test.name}`,
    `Framework: ${test.framework}`,
    `Type: ${test.testType}`,
    `Lines: ${test.lineCount}`,
    `Description: ${test.description}`,
    test.edgeCases.length > 0 ? `Edge Cases: ${test.edgeCases.join(', ')}` : ''
  ].filter(Boolean)
}

/**
 * Combine all canvas content for accessibility mirror
 */
export function getTestingCanvasContent(
  generation: TestGenerationResult | null,
  execution: TestExecutionResponse | null,
  coverage: CoverageReport | null,
  approval: TestingCanvasState['approvalStatus']
): string[] {
  return [
    ...formatTestGenerationResult(generation),
    '',
    ...formatExecutionResults(execution),
    '',
    ...formatCoverageReport(coverage),
    '',
    ...formatApprovalStatus(approval)
  ].filter(line => line.trim().length > 0)
}
