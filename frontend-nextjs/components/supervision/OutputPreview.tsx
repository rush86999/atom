/**
 * Output Preview
 *
 * Displays execution output with syntax highlighting for JSON.
 * Supports multiple output types: json, text, chart, table.
 */

import React, { useState } from 'react';
import ReactJson from 'react-json-view';

interface Props {
  executionId: string;
  output: any;
  outputType: 'json' | 'text' | 'chart' | 'table';
}

const OutputPreview: React.FC<Props> = ({ executionId, output, outputType }) => {
  const [view, setView] = useState<'formatted' | 'raw'>('formatted');

  const handleCopy = () => {
    const text = typeof output === 'string' ? output : JSON.stringify(output, null, 2);
    navigator.clipboard.writeText(text);
  };

  const handleExport = () => {
    const text = typeof output === 'string' ? output : JSON.stringify(output, null, 2);
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `execution-${executionId}-output.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderContent = () => {
    switch (outputType) {
      case 'json':
        return view === 'formatted' ? (
          <ReactJson
            src={output}
            theme="monokai"
            displayDataTypes={false}
            enableClipboard={false}
          />
        ) : (
          <pre className="raw-output">{JSON.stringify(output, null, 2)}</pre>
        );

      case 'text':
        return (
          <pre className="text-output">
            {typeof output === 'string' ? output : JSON.stringify(output, null, 2)}
          </pre>
        );

      case 'chart':
        // Would render chart visualization
        return (
          <div className="chart-output">
            <div className="chart-placeholder">
              Chart visualization would render here
            </div>
          </div>
        );

      case 'table':
        // Would render table
        if (Array.isArray(output) && output.length > 0) {
          const headers = Object.keys(output[0]);
          return (
            <table className="table-output">
              <thead>
                <tr>
                  {headers.map(header => (
                    <th key={header}>{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {output.map((row, index) => (
                  <tr key={index}>
                    {headers.map(header => (
                      <td key={header}>{String(row[header])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }
        return <div className="table-empty">No table data</div>;

      default:
        return <pre>{JSON.stringify(output, null, 2)}</pre>;
    }
  };

  return (
    <div className="output-preview">
      <div className="output-header">
        <h4>Output</h4>
        <div className="output-actions">
          {outputType === 'json' && (
            <button
              onClick={() => setView(view === 'formatted' ? 'raw' : 'formatted')}
            >
              {view === 'formatted' ? 'Raw' : 'Formatted'}
            </button>
          )}
          <button onClick={handleCopy} title="Copy output">
            Copy
          </button>
          <button onClick={handleExport} title="Export output">
            Export
          </button>
        </div>
      </div>

      <div className="output-content">
        {renderContent()}
      </div>

      <style jsx>{`
        .output-preview {
          background: #f5f5f5;
          border-radius: 8px;
          overflow: hidden;
          margin-top: 16px;
        }

        .output-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 16px;
          background: white;
          border-bottom: 1px solid #e0e0e0;
        }

        .output-header h4 {
          margin: 0;
          font-size: 14px;
        }

        .output-actions {
          display: flex;
          gap: 8px;
        }

        .output-actions button {
          background: white;
          border: 1px solid #e0e0e0;
          padding: 4px 12px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        }

        .output-actions button:hover {
          background: #f5f5f5;
        }

        .output-content {
          padding: 16px;
          max-height: 400px;
          overflow: auto;
        }

        .raw-output,
        .text-output {
          margin: 0;
          font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
          font-size: 12px;
          white-space: pre-wrap;
          word-break: break-word;
        }

        .table-output {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }

        .table-output th,
        .table-output td {
          padding: 8px;
          text-align: left;
          border-bottom: 1px solid #e0e0e0;
        }

        .table-output th {
          background: #f5f5f5;
          font-weight: 600;
        }

        .table-empty {
          padding: 40px;
          text-align: center;
          color: #888;
        }

        .chart-placeholder {
          padding: 40px;
          text-align: center;
          color: #888;
          background: white;
          border-radius: 4px;
        }
      `}</style>
    </div>
  );
};

export default OutputPreview;
