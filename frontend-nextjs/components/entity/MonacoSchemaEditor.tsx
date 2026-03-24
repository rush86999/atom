import React, { useState, useEffect, useCallback } from 'react';
import Editor, { OnChange } from '@monaco-editor/react';
import { validateSchema, SchemaValidationResult } from '@/src/lib/validators/jsonSchema';

interface MonacoSchemaEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string;
  readOnly?: boolean;
}

const MonacoSchemaEditor: React.FC<MonacoSchemaEditorProps> = ({
  value,
  onChange,
  height = '400px',
  readOnly = false
}) => {
  const [validation, setValidation] = useState<SchemaValidationResult>({ valid: true, errors: [] });

  // Debounced validation
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        const parsed = JSON.parse(value);
        const result = validateSchema(parsed);
        setValidation(result);
      } catch (e: any) {
        setValidation({ valid: false, errors: [`JSON Parse Error: ${e.message}`] });
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [value]);

  const handleEditorChange: OnChange = (val) => {
    if (val !== undefined) {
      onChange(val);
    }
  };

  return (
    <div className="flex flex-col w-full rounded-lg border border-white/10 overflow-hidden bg-zinc-900">
      <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/10">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">JSON Schema Editor</span>
        {!validation.valid && (
          <span className="text-[10px] font-bold text-red-500 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">
            {validation.errors.length} ERRORS
          </span>
        )}
      </div>
      
      <div style={{ height }}>
        <Editor
          height="100%"
          defaultLanguage="json"
          theme="vs-dark"
          value={value}
          onChange={handleEditorChange}
          options={{
            readOnly,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 14,
            automaticLayout: true,
            tabSize: 2,
            formatOnPaste: true,
            formatOnType: true,
            fixedOverflowWidgets: true
          }}
        />
      </div>

      {!validation.valid && (
        <div className="bg-red-500/10 border-t border-red-500/20 max-h-32 overflow-y-auto p-2">
          {validation.errors.map((error, idx) => (
            <div key={idx} className="flex gap-2 items-start py-1">
              <span className="text-red-500 mt-0.5">•</span>
              <span className="text-red-400 text-[11px] leading-relaxed">{error}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default MonacoSchemaEditor;
