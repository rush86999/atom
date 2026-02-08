/**
 * Supervisor Identity
 *
 * Displays supervisor information (user or autonomous agent).
 * Shows LLM analysis for autonomous supervisors.
 */

import React, { useState, useEffect } from 'react';

interface Props {
  supervisorType: 'user' | 'autonomous_agent';
  supervisorId: string;
  supervisorName?: string;
}

interface AutonomousAnalysis {
  confidence_score: number;
  risk_level: 'safe' | 'medium' | 'high';
  suggested_modifications?: string[];
}

const SupervisorIdentity: React.FC<Props> = ({
  supervisorType,
  supervisorId,
  supervisorName
}) => {
  const [analysis, setAnalysis] = useState<AutonomousAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (supervisorType === 'autonomous_agent') {
      // Fetch autonomous supervisor analysis
      setLoading(true);
      // This would come from the proposal review
      setAnalysis({
        confidence_score: 0.92,
        risk_level: 'safe',
        suggested_modifications: []
      });
      setLoading(false);
    }
  }, [supervisorType, supervisorId]);

  const getRiskLevelColor = (level: string) => {
    switch (level) {
      case 'safe':
        return '#4caf50';
      case 'medium':
        return '#ff9800';
      case 'high':
        return '#f44336';
      default:
        return '#888';
    }
  };

  const getConfidenceWidth = (score: number) => {
    return `${score * 100}%`;
  };

  return (
    <div className="supervisor-identity">
      <div className="supervisor-header">
        <span className="supervisor-label">Supervisor:</span>
        <span className="supervisor-type">
          {supervisorType === 'user' ? '👤 User' : '🤖 Autonomous Agent'}
        </span>
      </div>

      <div className="supervisor-info">
        {supervisorName && (
          <div className="supervisor-name">{supervisorName}</div>
        )}
        <div className="supervisor-id">{supervisorId}</div>
      </div>

      {supervisorType === 'autonomous_agent' && analysis && (
        <div className="autonomous-analysis">
          <div className="analysis-section">
            <div className="analysis-label">Confidence Score</div>
            <div className="confidence-bar">
              <div
                className="confidence-fill"
                style={{ width: getConfidenceWidth(analysis.confidence_score) }}
              />
            </div>
            <div className="confidence-value">
              {Math.round(analysis.confidence_score * 100)}%
            </div>
          </div>

          <div className="analysis-section">
            <div className="analysis-label">Risk Level</div>
            <div
              className="risk-indicator"
              style={{ backgroundColor: getRiskLevelColor(analysis.risk_level) }}
            >
              {analysis.risk_level.toUpperCase()}
            </div>
          </div>

          {analysis.suggested_modifications && analysis.suggested_modifications.length > 0 && (
            <div className="analysis-section">
              <div className="analysis-label">Suggested Modifications</div>
              <ul className="modifications-list">
                {analysis.suggested_modifications.map((mod, index) => (
                  <li key={index}>{mod}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        .supervisor-identity {
          background: #f5f5f5;
          border-radius: 8px;
          padding: 12px;
          margin-bottom: 16px;
        }

        .supervisor-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }

        .supervisor-label {
          font-weight: 600;
          font-size: 14px;
        }

        .supervisor-type {
          font-size: 14px;
        }

        .supervisor-info {
          margin-bottom: 12px;
        }

        .supervisor-name {
          font-weight: 500;
        }

        .supervisor-id {
          font-size: 12px;
          color: #666;
        }

        .autonomous-analysis {
          border-top: 1px solid #e0e0e0;
          padding-top: 12px;
        }

        .analysis-section {
          margin-bottom: 12px;
        }

        .analysis-section:last-child {
          margin-bottom: 0;
        }

        .analysis-label {
          font-size: 12px;
          font-weight: 600;
          margin-bottom: 4px;
          color: #666;
        }

        .confidence-bar {
          position: relative;
          height: 8px;
          background: #e0e0e0;
          border-radius: 4px;
          overflow: hidden;
          margin-bottom: 4px;
        }

        .confidence-fill {
          height: 100%;
          background: linear-gradient(90deg, #4caf50, #8bc34a);
          transition: width 0.3s ease;
        }

        .confidence-value {
          font-size: 12px;
          text-align: right;
        }

        .risk-indicator {
          display: inline-block;
          padding: 4px 12px;
          border-radius: 12px;
          color: white;
          font-size: 12px;
          font-weight: 600;
        }

        .modifications-list {
          margin: 0;
          padding-left: 20px;
          font-size: 13px;
        }

        .modifications-list li {
          margin-bottom: 4px;
        }
      `}</style>
    </div>
  );
};

export default SupervisorIdentity;
