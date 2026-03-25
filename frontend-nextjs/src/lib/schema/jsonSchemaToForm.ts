import { JSONSchema7 } from "json-schema";

export interface FieldConfig {
  name: string;
  type: string;
  required: boolean;
  title?: string;
  description?: string;
  items?: any; // For arrays
  properties?: FieldConfig[]; // For nested objects
}

/**
 * Converts a JSON Schema to an array of simplified field configurations recursively.
 */
export function schemaToFields(schema: JSONSchema7): FieldConfig[] {
  if (!schema || !schema.properties) return [];

  const requiredFields = new Set(schema.required || []);

  return Object.entries(schema.properties).map(([name, def]: [string, any]) => {
    const field: FieldConfig = {
      name,
      type: Array.isArray(def.type) ? def.type[0] : def.type || "string",
      required: requiredFields.has(name),
      title: def.title,
      description: def.description,
    };

    if (field.type === "array" && def.items) {
      field.items = def.items;
    }

    if (field.type === "object" && def.properties) {
      field.properties = schemaToFields(def as JSONSchema7);
    }

    return field;
  });
}

/**
 * Converts an array of field configurations back to a JSON Schema recursively.
 */
export function fieldsToSchema(fields: FieldConfig[]): JSONSchema7 {
  const properties: { [key: string]: any } = {};
  const required: string[] = [];

  fields.forEach((field) => {
    const propDef: any = {
      type: field.type,
      title: field.title || field.name,
      description: field.description,
    };

    if (field.type === "array" && field.items) {
      propDef.items = field.items;
    }

    if (field.type === "object") {
      const nestedSchema = fieldsToSchema(field.properties || []);
      propDef.properties = nestedSchema.properties;
      if (nestedSchema.required) propDef.required = nestedSchema.required;
    }

    properties[field.name] = propDef;

    if (field.required) {
      required.push(field.name);
    }
  });

  return {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    type: "object",
    properties,
    required: required.length > 0 ? required : undefined,
  };
}
