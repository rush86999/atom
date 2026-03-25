import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);

export interface SchemaValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Validates a JSON Schema against meta-schema and custom constraints.
 */
export function validateSchema(schema: unknown): SchemaValidationResult {
  if (!schema || typeof schema !== 'object') {
    return { valid: false, errors: ['Schema must be a valid JSON object'] };
  }

  const errors: string[] = [];

  // 1. Basic JSON Schema validation using AJV
  try {
    const isValid = ajv.validateSchema(schema as any);
    if (!isValid && ajv.errors) {
      ajv.errors.forEach(err => {
        errors.push(`${err.instancePath || 'root'} ${err.message}`);
      });
    }
  } catch (e: any) {
    errors.push(`Invalid schema structure: ${e.message}`);
  }

  // 2. Custom constraints for Entity Management
  const s = schema as any;

  // Root must be type: object
  if (s.type !== 'object') {
    errors.push("Root type must be 'object'");
  }

  // Must have properties
  if (!s.properties || typeof s.properties !== 'object') {
    errors.push("Schema must define 'properties'");
  } else {
    // Max properties constraint
    const propCount = Object.keys(s.properties).length;
    if (propCount > 100) {
      errors.push(`Too many properties (max 100, found ${propCount})`);
    }
  }

  // Max depth constraint (simple recursive check)
  const getDepth = (obj: any): number => {
    if (!obj || typeof obj !== 'object') return 0;
    const depths = Object.values(obj).map(v => getDepth(v));
    return 1 + (depths.length > 0 ? Math.max(...depths) : 0);
  };

  const depth = getDepth(schema);
  if (depth > 12) { // 10 + some buffer for root/properties level
    errors.push(`Schema depth exceeds maximum (max 10 nesting levels)`);
  }

  return {
    valid: errors.length === 0,
    errors
  };
}
