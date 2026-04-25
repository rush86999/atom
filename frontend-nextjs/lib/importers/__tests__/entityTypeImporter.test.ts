/**
 * Tests for entityTypeImporter
 *
 * Tests entity type definition parsing, validation, and import functionality.
 */

import { parseEntityTypeDefinition, importEntityTypes, ImportError } from '@lib/importers/entityTypeImporter';
import { validateSchema } from '@lib/validators/jsonSchema';

// Mock axios
jest.mock('axios');
import axios from 'axios';

// Mock react-hot-toast
jest.mock('react-hot-toast');
import { toast } from 'react-hot-toast';

const mockedAxios = axios as jest.Mocked<typeof axios>;
const mockedToast = toast as jest.Mocked<typeof toast>;

describe('entityTypeImporter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('parseEntityTypeDefinition', () => {
    const validJsonSchema = {
      type: 'object',
      properties: {
        name: { type: 'string' },
        age: { type: 'number' }
      }
    };

    const validJsonDefinition = {
      slug: 'test-entity',
      display_name: 'Test Entity',
      json_schema: validJsonSchema
    };

    const validYamlDefinition = `
slug: test-entity
display_name: Test Entity
json_schema:
  type: object
  properties:
    name:
      type: string
    age:
      type: number
`;

    it('should parse valid JSON definition', () => {
      const content = JSON.stringify(validJsonDefinition);
      const result = parseEntityTypeDefinition(content, 'test.json');

      expect(result).toEqual(validJsonDefinition);
    });

    it('should parse valid YAML definition', () => {
      const result = parseEntityTypeDefinition(validYamlDefinition, 'test.yaml');

      expect(result).toHaveProperty('slug', 'test-entity');
      expect(result).toHaveProperty('display_name', 'Test Entity');
      expect(result).toHaveProperty('json_schema');
    });

    it('should parse .yml extension', () => {
      const result = parseEntityTypeDefinition(validYamlDefinition, 'test.yml');

      expect(result).toHaveProperty('slug', 'test-entity');
    });

    it('should throw error for invalid JSON', () => {
      expect(() => {
        parseEntityTypeDefinition('{invalid json}', 'test.json');
      }).toThrow('Parse error in test.json');
    });

    it('should throw error for invalid YAML', () => {
      expect(() => {
        parseEntityTypeDefinition('invalid: yaml: content:\n  - broken', 'test.yaml');
      }).toThrow('Parse error in test.yaml');
    });

    it('should throw error for missing slug', () => {
      const invalidDef = {
        display_name: 'Test',
        json_schema: validJsonSchema
      };

      expect(() => {
        parseEntityTypeDefinition(JSON.stringify(invalidDef), 'test.json');
      }).toThrow("Missing required field 'slug' in test.json");
    });

    it('should throw error for missing display_name', () => {
      const invalidDef = {
        slug: 'test',
        json_schema: validJsonSchema
      };

      expect(() => {
        parseEntityTypeDefinition(JSON.stringify(invalidDef), 'test.json');
      }).toThrow("Missing required field 'display_name' in test.json");
    });

    it('should throw error for missing json_schema', () => {
      const invalidDef = {
        slug: 'test',
        display_name: 'Test'
      };

      expect(() => {
        parseEntityTypeDefinition(JSON.stringify(invalidDef), 'test.json');
      }).toThrow("Missing required field 'json_schema' in test.json");
    });

    it('should throw error for invalid JSON schema', () => {
      const invalidDef = {
        slug: 'test',
        display_name: 'Test',
        json_schema: {
          type: 'invalid-type'
        }
      };

      expect(() => {
        parseEntityTypeDefinition(JSON.stringify(invalidDef), 'test.json');
      }).toThrow('Invalid JSON Schema in test.json');
    });

    it('should accept valid JSON schema', () => {
      const content = JSON.stringify(validJsonDefinition);
      const result = parseEntityTypeDefinition(content, 'test.json');

      expect(result.slug).toBe('test-entity');
    });

    it('should handle complex nested schemas', () => {
      const complexSchema = {
        slug: 'complex-entity',
        display_name: 'Complex Entity',
        json_schema: {
          type: 'object',
          properties: {
            user: {
              type: 'object',
              properties: {
                name: { type: 'string' },
                email: { type: 'string' }
              }
            },
            tags: {
              type: 'array',
              items: { type: 'string' }
            }
          },
          required: ['user']
        }
      };

      const content = JSON.stringify(complexSchema);
      const result = parseEntityTypeDefinition(content, 'complex.json');

      expect(result.slug).toBe('complex-entity');
      expect(result.json_schema.properties).toBeDefined();
    });

    it('should handle schema with required fields', () => {
      const schemaWithRequired = {
        slug: 'required-entity',
        display_name: 'Required Entity',
        json_schema: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            email: { type: 'string' }
          },
          required: ['name', 'email']
        }
      };

      const content = JSON.stringify(schemaWithRequired);
      const result = parseEntityTypeDefinition(content, 'required.json');

      expect(result.json_schema.required).toEqual(['name', 'email']);
    });
  });

  describe('importEntityTypes', () => {
    const workspaceId = 'test-workspace-123';

    const validDefinitions = [
      {
        slug: 'entity-1',
        display_name: 'Entity 1',
        json_schema: {
          type: 'object',
          properties: {
            name: { type: 'string' }
          }
        }
      },
      {
        slug: 'entity-2',
        display_name: 'Entity 2',
        json_schema: {
          type: 'object',
          properties: {
            title: { type: 'string' }
          }
        }
      }
    ];

    it('should import all valid entity types successfully', async () => {
      mockedAxios.post.mockResolvedValue({ data: { success: true } });

      const result = await importEntityTypes(validDefinitions, workspaceId);

      expect(result.success).toBe(2);
      expect(result.errors).toHaveLength(0);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
    });

    it('should handle partial failures', async () => {
      // First succeeds, second fails
      mockedAxios.post
        .mockResolvedValueOnce({ data: { success: true } })
        .mockRejectedValueOnce({
          response: {
            data: {
              detail: 'Validation error'
            }
          }
        });

      const result = await importEntityTypes(validDefinitions, workspaceId);

      expect(result.success).toBe(1);
      expect(result.errors).toHaveLength(1);
      expect(result.errors[0]).toEqual({
        file: 'entity-2',
        error: 'Validation error'
      });
    });

    it('should handle all failures', async () => {
      mockedAxios.post.mockRejectedValue({
        response: {
          data: {
            detail: 'Server error'
          }
        }
      });

      const result = await importEntityTypes(validDefinitions, workspaceId);

      expect(result.success).toBe(0);
      expect(result.errors).toHaveLength(2);
    });

    it('should include workspace ID in headers', async () => {
      mockedAxios.post.mockResolvedValue({ data: { success: true } });

      await importEntityTypes(validDefinitions, workspaceId);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        '/api/entity-types',
        validDefinitions[0],
        {
          headers: { 'X-Workspace-ID': workspaceId }
        }
      );
    });

    it('should handle missing slug in error reporting', async () => {
      const invalidDef = [
        {
          display_name: 'No Slug',
          json_schema: { type: 'object', properties: {} }
        }
      ];

      mockedAxios.post.mockRejectedValue(new Error('Network error'));

      const result = await importEntityTypes(invalidDef, workspaceId);

      expect(result.errors[0].file).toBe('unknown');
    });

    it('should handle network errors', async () => {
      mockedAxios.post.mockRejectedValue(new Error('Network error'));

      const result = await importEntityTypes(validDefinitions, workspaceId);

      expect(result.success).toBe(0);
      expect(result.errors).toHaveLength(2);
      expect(result.errors[0].error).toBe('Network error');
    });

    it('should handle API errors without detail', async () => {
      mockedAxios.post.mockRejectedValue({
        response: {
          data: {}
        }
      });

      const result = await importEntityTypes(validDefinitions, workspaceId);

      expect(result.errors[0].error).toBeDefined();
    });

    it('should handle API errors without response', async () => {
      const error = new Error('Unknown error') as any;
      delete error.response;
      mockedAxios.post.mockRejectedValue(error);

      const result = await importEntityTypes(validDefinitions, workspaceId);

      expect(result.errors[0].error).toBe('Unknown error');
    });

    it('should import empty definitions list', async () => {
      const result = await importEntityTypes([], workspaceId);

      expect(result.success).toBe(0);
      expect(result.errors).toHaveLength(0);
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });

    it('should handle single definition', async () => {
      mockedAxios.post.mockResolvedValue({ data: { success: true } });

      const result = await importEntityTypes([validDefinitions[0]], workspaceId);

      expect(result.success).toBe(1);
      expect(result.errors).toHaveLength(0);
    });

    it('should continue importing after failure', async () => {
      // First fails, second succeeds
      mockedAxios.post
        .mockRejectedValueOnce({
          response: {
            data: { detail: 'First failed' }
          }
        })
        .mockResolvedValueOnce({ data: { success: true } });

      const result = await importEntityTypes(validDefinitions, workspaceId);

      expect(result.success).toBe(1);
      expect(result.errors).toHaveLength(1);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
    });
  });

  describe('ImportError type', () => {
    it('should have correct structure', () => {
      const error: ImportError = {
        file: 'test-entity',
        error: 'Test error message'
      };

      expect(error.file).toBe('test-entity');
      expect(error.error).toBe('Test error message');
    });
  });

  describe('integration with validateSchema', () => {
    it('should use validateSchema for schema validation', () => {
      // Mock validateSchema to return invalid
      const validateSchemaMock = validateSchema as jest.MockedFunction<typeof validateSchema>;
      validateSchemaMock.mockReturnValue({
        valid: false,
        errors: ['Schema validation failed']
      });

      const invalidDef = {
        slug: 'test',
        display_name: 'Test',
        json_schema: { type: 'invalid' }
      };

      expect(() => {
        parseEntityTypeDefinition(JSON.stringify(invalidDef), 'test.json');
      }).toThrow('Invalid JSON Schema in test.json');

      validateSchemaMock.mockRestore();
    });
  });

  describe('file extension handling', () => {
    it('should handle .json extension', () => {
      const content = JSON.stringify({
        slug: 'test',
        display_name: 'Test',
        json_schema: { type: 'object', properties: {} }
      });

      expect(() => {
        parseEntityTypeDefinition(content, 'test.json');
      }).not.toThrow();
    });

    it('should handle .yaml extension', () => {
      const content = `
slug: test
display_name: Test
json_schema:
  type: object
  properties: {}
`;

      expect(() => {
        parseEntityTypeDefinition(content, 'test.yaml');
      }).not.toThrow();
    });

    it('should handle .yml extension', () => {
      const content = `
slug: test
display_name: Test
json_schema:
  type: object
  properties: {}
`;

      expect(() => {
        parseEntityTypeDefinition(content, 'test.yml');
      }).not.toThrow();
    });

    it('should default to JSON for unknown extensions', () => {
      const content = JSON.stringify({
        slug: 'test',
        display_name: 'Test',
        json_schema: { type: 'object', properties: {} }
      });

      expect(() => {
        parseEntityTypeDefinition(content, 'test.unknown');
      }).not.toThrow();
    });
  });
});
