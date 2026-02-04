import React, { memo, useState, useEffect } from "react";
import { Handle, Position } from "reactflow";

// Trigger configuration types
interface TriggerField {
  id: string;
  label: string;
  type: "text" | "number" | "select" | "textarea" | "checkbox";
  required?: boolean;
  placeholder?: string;
  options?: Array<{ value: string; label: string }>;
  min?: number;
  max?: number;
  defaultValue?: any;
}

interface TriggerType {
  id: string;
  name: string;
  service: string;
  icon: string;
  color: string;
  description: string;
  fields: TriggerField[];
  outputs: Array<{ id: string; label: string; type: string }>;
  handler_function?: string;
}

interface UniversalTriggerNodeProps {
  data: {
    triggerType?: string;
    triggerConfig?: any;
    onChange?: (data: any) => void;
    availableTriggers?: TriggerType[];
  };
}

const UniversalTriggerNode: React.FC<UniversalTriggerNodeProps> = memo(
  ({ data }) => {
    const [selectedTriggerType, setSelectedTriggerType] = useState<string>(
      data.triggerType || "",
    );
    const [fieldValues, setFieldValues] = useState<Record<string, any>>(
      data.triggerConfig || {},
    );
    const [availableTriggers, setAvailableTriggers] = useState<TriggerType[]>(
      [],
    );
    const [loading, setLoading] = useState(true);

    // Load trigger configurations from database/API
    useEffect(() => {
      const loadTriggerConfigurations = async () => {
        try {
          // Fetch trigger configurations from the API
          const response = await fetch("/api/triggers/");
          if (!response.ok) {
            throw new Error(`Failed to fetch triggers: ${response.statusText}`);
          }

          const apiTriggers = await response.json();

          // Transform API response to match our TriggerType interface
          const transformedTriggers: TriggerType[] = apiTriggers.map(
            (trigger: any) => ({
              id: trigger.id,
              name: trigger.name,
              service: trigger.service,
              icon: trigger.icon,
              color: trigger.color,
              description: trigger.description,
              fields: trigger.fields || [],
              outputs: trigger.outputs || [],
            }),
          );

          setAvailableTriggers(transformedTriggers);

          // If we have a pre-selected trigger type, ensure it's valid
          if (
            data.triggerType &&
            !transformedTriggers.find((t) => t.id === data.triggerType)
          ) {
            setSelectedTriggerType("");
          }
        } catch (error) {
          console.error(
            "Failed to load trigger configurations from API:",
            error,
          );
          // Fallback to empty array if API fails
          setAvailableTriggers([]);
        } finally {
          setLoading(false);
        }
      };

      loadTriggerConfigurations();
    }, [data.triggerType]);

    const onConfigChange = (key: string, value: any) => {
      const trigger = availableTriggers.find(
        (t) => t.id === selectedTriggerType,
      );
      const newData = {
        triggerType: selectedTriggerType,
        triggerConfig: { ...fieldValues, [key]: value },
        handlerFunction: trigger?.handler_function,
      };

      if (data.onChange) {
        data.onChange(newData);
      }
    };

    const handleTriggerTypeChange = (triggerId: string) => {
      setSelectedTriggerType(triggerId);
      setFieldValues({});

      const trigger = availableTriggers.find((t) => t.id === triggerId);
      if (trigger) {
        // Set default values for fields
        const defaults: Record<string, any> = {};
        trigger.fields.forEach((field) => {
          if (field.defaultValue !== undefined) {
            defaults[field.id] = field.defaultValue;
          }
        });
        setFieldValues(defaults);

        if (data.onChange) {
          data.onChange({
            triggerType: triggerId,
            triggerConfig: defaults,
            handlerFunction: trigger.handler_function,
          });
        }
      }
    };

    const handleFieldChange = (fieldId: string, value: any) => {
      const newFieldValues = { ...fieldValues, [fieldId]: value };
      setFieldValues(newFieldValues);
      onConfigChange(fieldId, value);
    };

    const renderField = (field: TriggerField) => {
      const value = fieldValues[field.id] ?? field.defaultValue ?? "";

      switch (field.type) {
        case "text":
        case "textarea":
          return (
            <input
              type="text"
              value={value}
              onChange={(e) => handleFieldChange(field.id, e.target.value)}
              style={{
                width: "100%",
                padding: "6px",
                border: "1px solid #ddd",
                borderRadius: "3px",
                resize: field.type === "textarea" ? "vertical" : "none",
                minHeight: field.type === "textarea" ? "60px" : "auto",
              }}
              placeholder={field.placeholder}
            />
          );

        case "number":
          return (
            <input
              type="number"
              value={value}
              onChange={(e) =>
                handleFieldChange(field.id, parseInt(e.target.value, 10) || 0)
              }
              style={{
                width: "100%",
                padding: "6px",
                border: "1px solid #ddd",
                borderRadius: "3px",
              }}
              min={field.min}
              max={field.max}
            />
          );

        case "select":
          return (
            <select
              value={value}
              onChange={(e) => handleFieldChange(field.id, e.target.value)}
              style={{
                width: "100%",
                padding: "6px",
                border: "1px solid #ddd",
                borderRadius: "3px",
              }}
            >
              {field.options?.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          );

        case "checkbox":
          return (
            <input
              type="checkbox"
              checked={!!value}
              onChange={(e) => handleFieldChange(field.id, e.target.checked)}
              style={{ marginRight: "8px" }}
            />
          );

        default:
          return null;
      }
    };

    const selectedTrigger = availableTriggers.find(
      (t) => t.id === selectedTriggerType,
    );

    if (loading) {
      return (
        <div
          style={{
            background: "#fff",
            border: "1px solid #ddd",
            padding: "10px 15px",
            borderRadius: "5px",
            width: 280,
            textAlign: "center",
          }}
        >
          <div>Loading triggers...</div>
        </div>
      );
    }

    return (
      <div
        style={{
          background: "#fff",
          border: "1px solid #ddd",
          padding: "10px 15px",
          borderRadius: "5px",
          width: 320,
          boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
        }}
      >
        <Handle
          type="target"
          position={Position.Top}
          style={{ background: "#555" }}
        />

        {/* Trigger Type Selection */}
        <div style={{ marginBottom: "15px" }}>
          <label
            style={{
              fontSize: "12px",
              display: "block",
              marginBottom: "5px",
              fontWeight: "500",
            }}
          >
            Trigger Type:
          </label>
          <select
            value={selectedTriggerType}
            onChange={(e) => handleTriggerTypeChange(e.target.value)}
            style={{
              width: "100%",
              padding: "6px",
              border: "1px solid #ddd",
              borderRadius: "3px",
            }}
          >
            <option value="">Select a trigger...</option>
            {availableTriggers.map((trigger) => (
              <option key={trigger.id} value={trigger.id}>
                {trigger.name}
              </option>
            ))}
          </select>
        </div>

        {/* Trigger Configuration */}
        {selectedTrigger && (
          <>
            {/* Trigger Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                marginBottom: "10px",
                paddingBottom: "10px",
                borderBottom: "1px solid #eee",
              }}
            >
              <div
                style={{
                  width: "24px",
                  height: "24px",
                  background: selectedTrigger.color,
                  borderRadius: "50%",
                  marginRight: "8px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "white",
                  fontSize: "12px",
                  fontWeight: "bold",
                }}
              >
                {selectedTrigger.icon}
              </div>
              <div>
                <strong>{selectedTrigger.name}</strong>
                <div
                  style={{ fontSize: "11px", color: "#666", marginTop: "2px" }}
                >
                  {selectedTrigger.description}
                </div>
              </div>
            </div>

            {/* Trigger Fields */}
            {selectedTrigger.fields.map((field) => (
              <div key={field.id} style={{ marginTop: "10px" }}>
                <label
                  style={{
                    fontSize: "12px",
                    display: "block",
                    marginBottom: "5px",
                    fontWeight: "500",
                  }}
                >
                  {field.label}
                  {field.required && (
                    <span style={{ color: "red", marginLeft: "2px" }}>*</span>
                  )}
                </label>
                {renderField(field)}
              </div>
            ))}
          </>
        )}

        <Handle
          type="source"
          position={Position.Bottom}
          style={{ background: "#555" }}
        />
      </div>
    );
  },
);

export default UniversalTriggerNode;

export const schema = {
  outputs: [
    // Outputs will be dynamically generated based on selected trigger
    { id: "dynamic_output", label: "Trigger Data", type: "object" },
  ],
};
