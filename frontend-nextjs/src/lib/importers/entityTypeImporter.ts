import axios from 'axios';
import { toast } from 'react-hot-toast';
import yaml from 'js-yaml';
import { validateSchema } from '../validators/jsonSchema';

export interface ImportError {
  file: string;
  error: string;
}

/**
 * Parses and validates entity type definitions from a string (JSON or YAML).
 */
export function parseEntityTypeDefinition(content: string, filename: string): any {
  let data: any;
  
  try {
    if (filename.endsWith('.yaml') || filename.endsWith('.yml')) {
      data = yaml.load(content);
    } else {
      data = JSON.parse(content);
    }
  } catch (e: any) {
    throw new Error(`Parse error in ${filename}: ${e.message}`);
  }

  // Basic validation of the structure
  const required = ['slug', 'display_name', 'json_schema'];
  for (const field of required) {
    if (!data[field]) {
      throw new Error(`Missing required field '${field}' in ${filename}`);
    }
  }

  // Validate the nested JSON Schema
  const schemaValidation = validateSchema(data.json_schema);
  if (!schemaValidation.valid) {
    throw new Error(`Invalid JSON Schema in ${filename}: ${schemaValidation.errors[0]}`);
  }

  return data;
}

/**
 * Imports entity types to the backend.
 */
export async function importEntityTypes(
  definitions: any[],
  workspaceId: string
): Promise<{ success: number; errors: ImportError[] }> {
  let successCount = 0;
  const errors: ImportError[] = [];

  for (const def of definitions) {
    try {
      await axios.post('/api/entity-types', def, {
        headers: { 'X-Workspace-ID': workspaceId }
      });
      successCount++;
    } catch (err: any) {
      errors.push({
        file: def.slug || 'unknown',
        error: err.response?.data?.detail || err.message
      });
    }
  }

  return { success: successCount, errors };
}
