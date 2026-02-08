/**
 * Log Stream Viewer
 *
 * Real-time log viewer using Server-Sent Events (SSE).
 * Displays log entries with level-based coloring and auto-scroll.
 */

import React, { useEffect, useRef } from 'react';

interface Props {
  executionId: string;
  logs?: Array<{
    timestamp: string;
    level: 'info' | 'warning' | 'error';
    message: string;
    data?: any;
  }>;
  autoScroll?: boolean;
}

const LogStreamViewer: React.FC<Props> = ({ executionId, logs: providedLogs, autoScroll = true }) => {
  const [logs, setLogs] = React.useState<Array<{
    timestamp: string;
    level: 'info' | 'warning' | 'error';
    message: string;
    data?: any;
  }>>(providedLogs || []);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Update logs when providedLogs prop changes
  useEffect(() => {
    if (providedLogs) {
      setLogs(providedLogs);
    }
  }, [providedLogs]);

  const getLevelClass = (level: string) => {
    return `log-entry log-${level}`;
  };

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'info':
        return 'ℹ';
      case 'warning':
        return '⚠';
      case 'error':
        return '✕';
      default:
        return '•';
    }
  };

  const copyLogs = () => {
    const logText = logs.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] ${l.message}`).join('\n');
    navigator.clipboard.writeText(logText);
  };

  const exportLogs = () => {
    const logText = logs.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] ${l.message}`).join('\n');
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `execution-${executionId}-logs.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="log-stream-viewer">
      <div className="log-header">
        <h4>Execution Logs</h4>
        <div className="log-actions">
          <button onClick={copyLogs} title="Copy logs">
            Copy
          </button>
          <button onClick={exportLogs} title="Export logs">
            Export
          </button>
        </div>
      </div>

      <div ref={containerRef} className="log-container">
        {logs.length === 0 ? (
          <div className="log-empty">Waiting for logs...</div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className={getLevelClass(log.level)}>
              <span className="log-icon">
                {getLevelIcon(log.level)}
              </span>
              <span className="log-timestamp">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className="log-message">
                {log.message}
              </span>
              {log.data && (
                <details className="log-data">
                  <summary>Data</summary>
                  <pre>{JSON.stringify(log.data, null, 2)}</pre>
                </details>
              )}
            </div>
          ))
        )}
      </div>

      <style jsx>{`
        .log-stream-viewer {
          background: #1e1e1e;
          border-radius: 8px;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          height: 300px;
        }

        .log-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 16px;
          background: #2d2d2d;
          border-bottom: 1px solid #404040;
        }

        .log-header h4 {
          margin: 0;
          color: #fff;
          font-size: 14px;
        }

        .log-actions {
          display: flex;
          gap: 8px;
        }

        .log-actions button {
          background: #404040;
          border: none;
          color: #fff;
          padding: 4px 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        }

        .log-actions button:hover {
          background: #505050;
        }

        .log-container {
          flex: 1;
          overflow-y: auto;
          padding: 12px;
          font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
          font-size: 12px;
        }

        .log-empty {
          color: #888;
          text-align: center;
          padding: 40px;
        }

        .log-entry {
          display: flex;
          gap: 8px;
          padding: 4px 0;
          line-height: 1.5;
        }

        .log-icon {
          flex-shrink: 0;
          width: 16px;
          text-align: center;
        }

        .log-timestamp {
          flex-shrink: 0;
          color: #888;
        }

        .log-message {
          flex: 1;
          word-break: break-word;
        }

        .log-info {
          color: #61afef;
        }

        .log-warning {
          color: #e5c07b;
        }

        .log-error {
          color: #e06c75;
        }

        .log-data {
          margin-top: 4px;
          padding-left: 24px;
        }

        .log-data summary {
          cursor: pointer;
          color: #888;
          font-size: 11px;
        }

        .log-data pre {
          margin: 8px 0 0 0;
          padding: 8px;
          background: #2d2d2d;
          border-radius: 4px;
          color: #abb2bf;
          font-size: 11px;
          overflow-x: auto;
        }
      `}</style>
    </div>
  );
};

export default LogStreamViewer;
