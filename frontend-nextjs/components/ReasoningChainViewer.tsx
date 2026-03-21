import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { ThumbsUp, ThumbsDown, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ReasoningStep {
    id: string;
    type: string;
    description: string;
    inputs: Record<string, any>;
    outputs: Record<string, any>;
    confidence: number;
    duration_ms: number;
    timestamp: string;
}

interface ReasoningChain {
    execution_id: string;
    started_at: string;
    completed_at: string | null;
    total_duration_ms: number;
    final_outcome: string | null;
    step_count: number;
    steps: ReasoningStep[];
    mermaid_diagram: string;
}

interface ReasoningChainViewerProps {
    chainId?: string;
    chainData?: ReasoningChain;
    onStepFeedback?: (stepId: string, score: number, comment?: string) => Promise<void>;
}

const ReasoningChainViewer: React.FC<ReasoningChainViewerProps> = ({ chainId, chainData, onStepFeedback }) => {
    const [chain, setChain] = useState<ReasoningChain | null>(chainData || null);
    const [loading, setLoading] = useState(!chainData);
    const [error, setError] = useState<string | null>(null);
    const [expandedStep, setExpandedStep] = useState<string | null>(null);
    const [activeFeedbackStep, setActiveFeedbackStep] = useState<string | null>(null);
    const [feedbackComment, setFeedbackComment] = useState("");
    const mermaidRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        mermaid.initialize({
            startOnLoad: false,
            theme: 'base',
            themeVariables: {
                primaryColor: '#667eea',
                primaryTextColor: '#fff',
                primaryBorderColor: '#5a6fd6',
                lineColor: '#94a3b8',
                secondaryColor: '#f1f5f9',
                tertiaryColor: '#e2e8f0'
            }
        });
    }, []);

    useEffect(() => {
        if (chainId && !chainData) {
            fetchChain();
        }
    }, [chainId]);

    useEffect(() => {
        if (chain?.mermaid_diagram && mermaidRef.current) {
            renderMermaid();
        }
    }, [chain]);

    const fetchChain = async () => {
        try {
            setLoading(true);
            const response = await fetch(`/api/v1/voice/reasoning/${chainId}`);
            if (!response.ok) throw new Error('Failed to fetch reasoning chain');
            const data = await response.json();
            setChain(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const renderMermaid = async () => {
        if (!mermaidRef.current || !chain?.mermaid_diagram) return;

        try {
            mermaidRef.current.innerHTML = '';
            const { svg } = await mermaid.render('reasoning-diagram', chain.mermaid_diagram);
            mermaidRef.current.innerHTML = svg;
        } catch (err) {
            console.error('Mermaid render error:', err);
        }
    };

    const getStepIcon = (type: string) => {
        const icons: Record<string, string> = {
            intent_analysis: '🎯',
            memory_query: '🧠',
            agent_selection: '🤖',
            agent_spawn: '✨',
            integration_call: '🔌',
            workflow_trigger: '⚡',
            decision: '🤔',
            action: '🎬',
            conclusion: '✅'
        };
        return icons[type] || '📍';
    };

    const getConfidenceColor = (confidence: number) => {
        if (confidence >= 0.8) return '#10b981';
        if (confidence >= 0.5) return '#f59e0b';
        return '#ef4444';
    };

    if (loading) {
        return (
            <div className="reasoning-loader">
                <div className="spinner" />
                Loading reasoning chain...
            </div>
        );
    }

    if (error) {
        return <div className="reasoning-error">{error}</div>;
    }

    if (!chain) {
        return <div className="reasoning-empty">No reasoning chain available</div>;
    }

    return (
        <div className="reasoning-chain-viewer">
            <div className="chain-header">
                <h3>AI Reasoning Chain</h3>
                <div className="header-meta">
                    <span className="step-count">{chain.step_count} steps</span>
                    <span className="duration">{chain.total_duration_ms.toFixed(0)}ms</span>
                </div>
            </div>

            <div className="diagram-section">
                <div ref={mermaidRef} className="mermaid-container" />
            </div>

            <div className="steps-list">
                {chain.steps.map((step, index) => (
                    <div
                        key={step.id}
                        className={`step-item ${expandedStep === step.id ? 'expanded' : ''}`}
                        onClick={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
                    >
                        <div className="step-header">
                            <span className="step-icon">{getStepIcon(step.type)}</span>
                            <span className="step-number">#{index + 1}</span>
                            <span className="step-type">{step.type.replace('_', ' ')}</span>
                            
                            {onStepFeedback && step.id && (
                                <div className="step-feedback-actions" onClick={(e) => e.stopPropagation()}>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-6 w-6 hover:text-emerald-500"
                                        onClick={() => onStepFeedback(step.id, 1)}
                                    >
                                        <ThumbsUp className="h-3.5 w-3.5" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-6 w-6 hover:text-rose-500"
                                        onClick={() => {
                                            setActiveFeedbackStep(step.id);
                                            onStepFeedback(step.id, -1);
                                        }}
                                    >
                                        <ThumbsDown className="h-3.5 w-3.5" />
                                    </Button>
                                </div>
                            )}

                            <div
                                className="confidence-bar"
                                style={{
                                    background: getConfidenceColor(step.confidence),
                                    width: `${step.confidence * 100}%`
                                }}
                            />
                        </div>
                        <div className="step-description">{step.description}</div>

                        {activeFeedbackStep === step.id && (
                            <div className="step-comment-input" onClick={(e) => e.stopPropagation()}>
                                <div className="flex gap-2 p-2 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-200 dark:border-slate-800">
                                    <input
                                        className="flex-1 bg-transparent text-xs border-none focus:ring-0 placeholder:text-muted-foreground/50 text-gray-800 dark:text-gray-200"
                                        placeholder="Provide a correction..."
                                        value={feedbackComment}
                                        onChange={(e) => setFeedbackComment(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && onStepFeedback) {
                                                onStepFeedback(step.id, 0, feedbackComment);
                                                setActiveFeedbackStep(null);
                                                setFeedbackComment("");
                                            }
                                        }}
                                        autoFocus
                                    />
                                    <Button size="icon" variant="ghost" className="h-4 w-4" onClick={() => setActiveFeedbackStep(null)}>
                                        <XCircle className="h-3.5 w-3.5" />
                                    </Button>
                                </div>
                            </div>
                        )}

                        {expandedStep === step.id && (
                            <div className="step-details">
                                <div className="detail-section">
                                    <strong>Inputs:</strong>
                                    <pre>{JSON.stringify(step.inputs, null, 2)}</pre>
                                </div>
                                <div className="detail-section">
                                    <strong>Outputs:</strong>
                                    <pre>{JSON.stringify(step.outputs, null, 2)}</pre>
                                </div>
                                <div className="detail-meta">
                                    <span>Duration: {step.duration_ms.toFixed(1)}ms</span>
                                    <span>Confidence: {(step.confidence * 100).toFixed(0)}%</span>
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {chain.final_outcome && (
                <div className="final-outcome">
                    <strong>Final Outcome:</strong>
                    <p>{chain.final_outcome}</p>
                </div>
            )}

            <style jsx>{`
        .reasoning-chain-viewer {
          background: #fff;
          border-radius: 16px;
          box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
          overflow: hidden;
        }

        .chain-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 24px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
        }

        .chain-header h3 {
          margin: 0;
          font-size: 18px;
        }

        .header-meta {
          display: flex;
          gap: 16px;
          font-size: 14px;
          opacity: 0.9;
        }

        .diagram-section {
          padding: 24px;
          background: #f8fafc;
          border-bottom: 1px solid #e2e8f0;
        }

        .mermaid-container {
          display: flex;
          justify-content: center;
          overflow-x: auto;
        }

        .steps-list {
          padding: 16px;
        }

        .step-item {
          padding: 16px;
          margin-bottom: 8px;
          background: #f8fafc;
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .step-item:hover {
          background: #f1f5f9;
        }

        .step-item.expanded {
          background: #e0e7ff;
        }

        .step-header {
          display: flex;
          align-items: center;
          gap: 12px;
          position: relative;
        }

        .step-feedback-actions {
          display: flex;
          gap: 4px;
          opacity: 0;
          transition: opacity 0.2s;
          margin-left: auto;
          margin-right: 120px;
        }

        .step-item:hover .step-feedback-actions {
          opacity: 1;
        }

        .step-comment-input {
          margin-top: 12px;
          animation: slideDown 0.2s ease-out;
        }

        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .step-icon {
          font-size: 20px;
        }

        .step-number {
          color: #64748b;
          font-size: 12px;
          font-weight: 600;
        }

        .step-type {
          font-weight: 600;
          color: #334155;
          text-transform: capitalize;
        }

        .confidence-bar {
          position: absolute;
          right: 0;
          height: 4px;
          border-radius: 2px;
          max-width: 100px;
        }

        .step-description {
          margin-top: 8px;
          color: #64748b;
          font-size: 14px;
        }

        .step-details {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid #cbd5e1;
        }

        .detail-section {
          margin-bottom: 12px;
        }

        .detail-section pre {
          margin: 8px 0 0;
          padding: 12px;
          background: #1e293b;
          color: #e2e8f0;
          border-radius: 8px;
          font-size: 12px;
          overflow-x: auto;
        }

        .detail-meta {
          display: flex;
          gap: 16px;
          font-size: 12px;
          color: #64748b;
        }

        .final-outcome {
          padding: 20px 24px;
          background: #ecfdf5;
          border-top: 1px solid #d1fae5;
        }

        .final-outcome strong {
          color: #059669;
        }

        .final-outcome p {
          margin: 8px 0 0;
          color: #047857;
        }

        .reasoning-loader,
        .reasoning-error,
        .reasoning-empty {
          padding: 40px;
          text-align: center;
          color: #64748b;
        }

        .spinner {
          width: 32px;
          height: 32px;
          border: 3px solid #e2e8f0;
          border-top-color: #667eea;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 16px;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .reasoning-error {
          color: #dc2626;
          background: #fef2f2;
        }
      `}</style>
        </div>
    );
};

export default ReasoningChainViewer;
