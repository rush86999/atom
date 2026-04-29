/**
 * Tests for JSON Schema to Form Converter
 *
 * Tests conversion between JSON Schema and field configurations.
 */

import { schemaToFields, fieldsToSchema, FieldConfig } from '@lib/src/schema/jsonSchemaToForm';
import { JSONSchema7 } from 'json-schema';

describe('jsonSchemaToForm', () => {
  describe('schemaToFields', () => {
    it('should convert empty schema to empty array', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {}
      };

      const fields = schemaToFields(schema);

      expect(fields).toEqual([]);
    });

    it('should convert null schema to empty array', () => {
      const fields = schemaToFields(null as any);

      expect(fields).toEqual([]);
    });

    it('should convert undefined schema to empty array', () => {
      const fields = schemaToFields(undefined as any);

      expect(fields).toEqual([]);
    });

    it('should convert schema without properties to empty array', () => {
      const schema: JSONSchema7 = {
        type: 'object'
      };

      const fields = schemaToFields(schema);

      expect(fields).toEqual([]);
    });

    it('should convert simple string fields', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          email: { type: 'string' }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields).toHaveLength(2);
      expect(fields[0]).toEqual({
        name: 'name',
        type: 'string',
        required: false,
        title: undefined,
        description: undefined
      });
      expect(fields[1]).toEqual({
        name: 'email',
        type: 'string',
        required: false,
        title: undefined,
        description: undefined
      });
    });

    it('should handle required fields', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          email: { type: 'string' }
        },
        required: ['name']
      };

      const fields = schemaToFields(schema);

      expect(fields[0].required).toBe(true);
      expect(fields[1].required).toBe(false);
    });

    it('should include title and description', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          name: {
            type: 'string',
            title: 'Full Name',
            description: 'Enter your full name'
          }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].title).toBe('Full Name');
      expect(fields[0].description).toBe('Enter your full name');
    });

    it('should convert number fields', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          age: { type: 'number' },
          price: { type: 'number' }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].type).toBe('number');
      expect(fields[1].type).toBe('number');
    });

    it('should convert boolean fields', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          active: { type: 'boolean' }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].type).toBe('boolean');
    });

    it('should convert array fields with items', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          tags: {
            type: 'array',
            items: { type: 'string' }
          }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].type).toBe('array');
      expect(fields[0].items).toEqual({ type: 'string' });
    });

    it('should convert nested object fields', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          user: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              email: { type: 'string' }
            }
          }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].type).toBe('object');
      expect(fields[0].properties).toBeDefined();
      expect(fields[0].properties).toHaveLength(2);
      expect(fields[0].properties![0].name).toBe('name');
      expect(fields[0].properties![1].name).toBe('email');
    });

    it('should handle deeply nested objects', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          level1: {
            type: 'object',
            properties: {
              level2: {
                type: 'object',
                properties: {
                  level3: { type: 'string' }
                }
              }
            }
          }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].type).toBe('object');
      expect(fields[0].properties![0].type).toBe('object');
      expect(fields[0].properties![0].properties![0].name).toBe('level3');
    });

    it('should handle mixed field types', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          age: { type: 'number' },
          active: { type: 'boolean' },
          tags: {
            type: 'array',
            items: { type: 'string' }
          },
          address: {
            type: 'object',
            properties: {
              street: { type: 'string' }
            }
          }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields).toHaveLength(5);
      expect(fields[0].type).toBe('string');
      expect(fields[1].type).toBe('number');
      expect(fields[2].type).toBe('boolean');
      expect(fields[3].type).toBe('array');
      expect(fields[4].type).toBe('object');
    });

    it('should handle array type in union types', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          field: { type: ['string', 'null'] }
        }
      };

      const fields = schemaToFields(schema);

      // Should take first type in array
      expect(fields[0].type).toBe('string');
    });

    it('should default to string type when type is missing', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          field: {} as any
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].type).toBe('string');
    });

    it('should handle required array with nested objects', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          user: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              email: { type: 'string' }
            }
          }
        },
        required: ['user']
      };

      const fields = schemaToFields(schema);

      expect(fields[0].required).toBe(true);
    });
  });

  describe('fieldsToSchema', () => {
    it('should convert empty array to basic schema', () => {
      const fields: FieldConfig[] = [];

      const schema = fieldsToSchema(fields);

      expect(schema).toMatchObject({
        $schema: 'https://json-schema.org/draft/2020-12/schema',
        type: 'object',
        properties: {}
      });
    });

    it('should convert simple string fields', () => {
      const fields: FieldConfig[] = [
        { name: 'name', type: 'string', required: false },
        { name: 'email', type: 'string', required: false }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.name).toEqual({
        type: 'string',
        title: 'name',
        description: undefined
      });
      expect(schema.properties.email).toEqual({
        type: 'string',
        title: 'email',
        description: undefined
      });
    });

    it('should include required fields', () => {
      const fields: FieldConfig[] = [
        { name: 'name', type: 'string', required: true },
        { name: 'email', type: 'string', required: false }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.required).toEqual(['name']);
    });

    it('should omit required when no fields are required', () => {
      const fields: FieldConfig[] = [
        { name: 'name', type: 'string', required: false },
        { name: 'email', type: 'string', required: false }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.required).toBeUndefined();
    });

    it('should include title and description', () => {
      const fields: FieldConfig[] = [
        {
          name: 'name',
          type: 'string',
          required: false,
          title: 'Full Name',
          description: 'Enter your name'
        }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.name).toEqual({
        type: 'string',
        title: 'Full Name',
        description: 'Enter your name'
      });
    });

    it('should convert number fields', () => {
      const fields: FieldConfig[] = [
        { name: 'age', type: 'number', required: false }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.age.type).toBe('number');
    });

    it('should convert boolean fields', () => {
      const fields: FieldConfig[] = [
        { name: 'active', type: 'boolean', required: false }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.active.type).toBe('boolean');
    });

    it('should convert array fields with items', () => {
      const fields: FieldConfig[] = [
        {
          name: 'tags',
          type: 'array',
          required: false,
          items: { type: 'string' }
        }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.tags).toEqual({
        type: 'array',
        title: 'tags',
        description: undefined,
        items: { type: 'string' }
      });
    });

    it('should convert nested object fields', () => {
      const fields: FieldConfig[] = [
        {
          name: 'user',
          type: 'object',
          required: false,
          properties: [
            { name: 'name', type: 'string', required: false },
            { name: 'email', type: 'string', required: true }
          ]
        }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.user).toMatchObject({
        type: 'object',
        title: 'user',
        properties: {
          name: { type: 'string', title: 'name' },
          email: { type: 'string', title: 'email' }
        },
        required: ['email']
      });
    });

    it('should handle deeply nested objects', () => {
      const fields: FieldConfig[] = [
        {
          name: 'level1',
          type: 'object',
          required: false,
          properties: [
            {
              name: 'level2',
              type: 'object',
              required: false,
              properties: [
                { name: 'level3', type: 'string', required: false }
              ]
            }
          ]
        }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.level1.properties.level2.properties.level3).toBeDefined();
    });

    it('should handle mixed field types', () => {
      const fields: FieldConfig[] = [
        { name: 'name', type: 'string', required: true },
        { name: 'age', type: 'number', required: false },
        { name: 'active', type: 'boolean', required: false },
        {
          name: 'tags',
          type: 'array',
          required: false,
          items: { type: 'string' }
        }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.name.type).toBe('string');
      expect(schema.properties.age.type).toBe('number');
      expect(schema.properties.active.type).toBe('boolean');
      expect(schema.properties.tags.type).toBe('array');
      expect(schema.required).toEqual(['name']);
    });

    it('should use name as default title', () => {
      const fields: FieldConfig[] = [
        { name: 'field_name', type: 'string', required: false }
      ];

      const schema = fieldsToSchema(fields);

      expect(schema.properties.field_name.title).toBe('field_name');
    });
  });

  describe('round-trip conversion', () => {
    it('should maintain schema structure through conversion', () => {
      const originalSchema: JSONSchema7 = {
        type: 'object',
        properties: {
          name: {
            type: 'string',
            title: 'Name',
            description: 'Full name'
          },
          age: {
            type: 'number',
            title: 'Age'
          },
          tags: {
            type: 'array',
            items: { type: 'string' }
          }
        },
        required: ['name']
      };

      const fields = schemaToFields(originalSchema);
      const convertedSchema = fieldsToSchema(fields);

      expect(convertedSchema.properties.name).toMatchObject({
        type: 'string',
        title: 'Name',
        description: 'Full name'
      });
      expect(convertedSchema.properties.age).toMatchObject({
        type: 'number',
        title: 'Age'
      });
      expect(convertedSchema.properties.tags).toMatchObject({
        type: 'array',
        items: { type: 'string' }
      });
      expect(convertedSchema.required).toEqual(['name']);
    });

    it('should handle nested objects in round-trip', () => {
      const originalSchema: JSONSchema7 = {
        type: 'object',
        properties: {
          user: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              email: { type: 'string' }
            }
          }
        }
      };

      const fields = schemaToFields(originalSchema);
      const convertedSchema = fieldsToSchema(fields);

      expect(convertedSchema.properties.user.properties.name).toBeDefined();
      expect(convertedSchema.properties.user.properties.email).toBeDefined();
    });
  });

  describe('FieldConfig type', () => {
    it('should accept valid field config', () => {
      const config: FieldConfig = {
        name: 'test',
        type: 'string',
        required: false,
        title: 'Test Field',
        description: 'Test description'
      };

      expect(config.name).toBe('test');
      expect(config.type).toBe('string');
      expect(config.required).toBe(false);
      expect(config.title).toBe('Test Field');
      expect(config.description).toBe('Test description');
    });

    it('should accept field config with optional properties', () => {
      const config: FieldConfig = {
        name: 'test',
        type: 'string',
        required: false
      };

      expect(config.name).toBe('test');
      expect(config.title).toBeUndefined();
      expect(config.description).toBeUndefined();
    });
  });

  describe('edge cases', () => {
    it('should handle fields with no type (defaults to string)', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          field: {} as any
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].type).toBe('string');
    });

    it('should handle null properties in schema', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          field: null as any
        }
      };

      const fields = schemaToFields(schema);

      expect(fields).toHaveLength(1);
    });

    it('should handle empty nested properties', () => {
      const schema: JSONSchema7 = {
        type: 'object',
        properties: {
          nested: {
            type: 'object',
            properties: {}
          }
        }
      };

      const fields = schemaToFields(schema);

      expect(fields[0].type).toBe('object');
      expect(fields[0].properties).toEqual([]);
    });
  });
});
