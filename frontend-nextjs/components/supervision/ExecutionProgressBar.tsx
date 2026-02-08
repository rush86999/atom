/**
 * Execution Progress Bar
 *
 * Visual progress bar showing execution steps with status indicators.
 */

import React from 'react';

interface Props {
  steps: Array<{
    id: string;
    name: string;
    status: 'pending' | 'in_progress' | 'completed' | 'failed';
    startedAt?: string;
    completedAt?: string;
  }>;
  currentStep: number;
}

const ExecutionProgressBar: React.FC<Props> = ({ steps, currentStep }) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return '✓';
      case 'in_progress':
        return '⟳';
      case 'failed':
        return '✗';
      default:
        return '○';
    }
  };

  const getStatusClass = (status: string) => {
    return `step step-${status}`;
  };

  const progressPercentage = ((currentStep + 1) / steps.length) * 100;

  return (
    <div className="execution-progress-bar">
      <div className="progress-header">
        <span>Execution Progress</span>
        <span>{Math.round(progressPercentage)}%</span>
      </div>

      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${progressPercentage}%` }}
        />
      </div>

      <div className="steps">
        {steps.map((step, index) => (
          <div
            key={step.id}
            className={getStatusClass(step.status)}
          >
            <div className="step-icon">
              {getStatusIcon(step.status)}
            </div>
            <div className="step-info">
              <div className="step-name">{step.name}</div>
              {step.startedAt && (
                <div className="step-time">
                  Started: {new Date(step.startedAt).toLocaleTimeString()}
                </div>
              )}
              {step.completedAt && (
                <div className="step-time">
                  Completed: {new Date(step.completedAt).toLocaleTimeString()}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <style jsx>{`
        .execution-progress-bar {
          background: #f5f5f5;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
        }

        .progress-header {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
          font-weight: 600;
        }

        .progress-track {
          position: relative;
          height: 8px;
          background: #e0e0e0;
          border-radius: 4px;
          overflow: hidden;
          margin-bottom: 16px;
        }

        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #4caf50, #8bc34a);
          transition: width 0.3s ease;
        }

        .steps {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .step {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 8px;
          border-radius: 4px;
          transition: background 0.2s;
        }

        .step-pending {
          opacity: 0.5;
        }

        .step-in_progress {
          background: #e3f2fd;
        }

        .step-completed {
          background: #e8f5e9;
        }

        .step-failed {
          background: #ffebee;
        }

        .step-icon {
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          background: white;
          font-weight: bold;
        }

        .step-in_progress .step-icon {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .step-info {
          flex: 1;
        }

        .step-name {
          font-weight: 500;
          margin-bottom: 4px;
        }

        .step-time {
          font-size: 12px;
          color: #666;
        }
      `}</style>
    </div>
  );
};

export default ExecutionProgressBar;
