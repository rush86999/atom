// Use the 2020-12 flavor of ajv: the plain Ajv class only ships the draft-07
// meta-schema, so any schema declaring $schema: draft/2019-09 or draft/2020-12
// (e.g. the entity modal's DEFAULT_SCHEMA) failed with "no schema with key or
// ref", which made entity-type creation impossible. Ajv2020 knows the
// 2020-12 meta-schema (and its meta/ refs) natively.
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);

export interface SchemaValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Validates a JSON Schema against meta-schema and custom constraints.
 */
export function validateSchema(schema: unknown): SchemaValidationResult {
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) {
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

  // getDepth counts the root object AND each properties container as levels,
  // so 10 nested property levels land at depth 22 — allow up to 10 levels
  // (max 10 nesting levels per the error message below)
  const depth = getDepth(schema);
  if (depth > 22) {
    errors.push(`Schema depth exceeds maximum (max 10 nesting levels)`);
  }

  return {
    valid: errors.length === 0,
    errors
  };
}
