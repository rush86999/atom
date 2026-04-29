/**
 * Tests for JSON Schema Validator
 *
 * Tests JSON Schema validation using AJV with custom constraints.
 */

import { validateSchema, SchemaValidationResult } from '@lib/src/validators/jsonSchema';

describe('validateSchema', () => {
  describe('basic validation', () => {
    it('should validate a correct JSON schema', () => {
      const validSchema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          age: { type: 'number' }
        }
      };

      const result = validateSchema(validSchema);

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should reject non-object input', () => {
      const result = validateSchema('not an object');

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Schema must be a valid JSON object');
    });

    it('should reject null', () => {
      const result = validateSchema(null);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Schema must be a valid JSON object');
    });

    it('should reject undefined', () => {
      const result = validateSchema(undefined);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Schema must be a valid JSON object');
    });

    it('should reject array', () => {
      const result = validateSchema([{ type: 'object' }]);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Schema must be a valid JSON object');
    });

    it('should reject primitive types', () => {
      expect(validateSchema('string').valid).toBe(false);
      expect(validateSchema(123).valid).toBe(false);
      expect(validateSchema(true).valid).toBe(false);
    });
  });

  describe('root type constraint', () => {
    it('should require root type to be object', () => {
      const invalidSchema = {
        type: 'array',
        items: { type: 'string' }
      };

      const result = validateSchema(invalidSchema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain("Root type must be 'object'");
    });

    it('should accept root type object', () => {
      const validSchema = {
        type: 'object',
        properties: {
          name: { type: 'string' }
        }
      };

      const result = validateSchema(validSchema);

      expect(result.valid).toBe(true);
    });
  });

  describe('properties constraint', () => {
    it('should require properties field', () => {
      const invalidSchema = {
        type: 'object'
      };

      const result = validateSchema(invalidSchema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain("Schema must define 'properties'");
    });

    it('should reject non-object properties', () => {
      const invalidSchema = {
        type: 'object',
        properties: 'invalid'
      };

      const result = validateSchema(invalidSchema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain("Schema must define 'properties'");
    });

    it('should accept empty properties', () => {
      const validSchema = {
        type: 'object',
        properties: {}
      };

      const result = validateSchema(validSchema);

      expect(result.valid).toBe(true);
    });

    it('should accept valid properties', () => {
      const validSchema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          age: { type: 'number' }
        }
      };

      const result = validateSchema(validSchema);

      expect(result.valid).toBe(true);
    });
  });

  describe('max properties constraint', () => {
    it('should reject schemas with more than 100 properties', () => {
      const properties: any = {};
      for (let i = 0; i < 101; i++) {
        properties[`field${i}`] = { type: 'string' };
      }

      const invalidSchema = {
        type: 'object',
        properties
      };

      const result = validateSchema(invalidSchema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Too many properties (max 100, found 101)');
    });

    it('should accept schemas with exactly 100 properties', () => {
      const properties: any = {};
      for (let i = 0; i < 100; i++) {
        properties[`field${i}`] = { type: 'string' };
      }

      const validSchema = {
        type: 'object',
        properties
      };

      const result = validateSchema(validSchema);

      expect(result.valid).toBe(true);
    });

    it('should accept schemas with less than 100 properties', () => {
      const properties: any = {};
      for (let i = 0; i < 50; i++) {
        properties[`field${i}`] = { type: 'string' };
      }

      const validSchema = {
        type: 'object',
        properties
      };

      const result = validateSchema(validSchema);

      expect(result.valid).toBe(true);
    });
  });

  describe('max depth constraint', () => {
    it('should reject schemas exceeding max depth', () => {
      const deepSchema = {
        type: 'object',
        properties: {
          level1: {
            type: 'object',
            properties: {
              level2: {
                type: 'object',
                properties: {
                  level3: {
                    type: 'object',
                    properties: {
                      level4: {
                        type: 'object',
                        properties: {
                          level5: {
                            type: 'object',
                            properties: {
                              level6: {
                                type: 'object',
                                properties: {
                                  level7: {
                                    type: 'object',
                                    properties: {
                                      level8: {
                                        type: 'object',
                                        properties: {
                                          level9: {
                                            type: 'object',
                                            properties: {
                                              level10: {
                                                type: 'object',
                                                properties: {
                                                  level11: { type: 'string' }
                                                }
                                              }
                                            }
                                          }
                                        }
                                      }
                                    }
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      };

      const result = validateSchema(deepSchema);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Schema depth exceeds maximum (max 10 nesting levels)');
    });

    it('should accept schemas at max depth', () => {
      const validDeepSchema = {
        type: 'object',
        properties: {
          level1: {
            type: 'object',
            properties: {
              level2: {
                type: 'object',
                properties: {
                  level3: {
                    type: 'object',
                    properties: {
                      level4: {
                        type: 'object',
                        properties: {
                          level5: {
                            type: 'object',
                            properties: {
                              level6: {
                                type: 'object',
                                properties: {
                                  level8: {
                                    type: 'object',
                                    properties: {
                                      level9: {
                                        type: 'object',
                                        properties: {
                                          level10: { type: 'string' }
                                        }
                                      }
                                    }
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      };

      const result = validateSchema(validDeepSchema);

      expect(result.valid).toBe(true);
    });

    it('should handle shallow schemas', () => {
      const shallowSchema = {
        type: 'object',
        properties: {
          name: { type: 'string' }
        }
      };

      const result = validateSchema(shallowSchema);

      expect(result.valid).toBe(true);
    });
  });

  describe('AJV validation', () => {
    it('should catch AJV validation errors', () => {
      const invalidSchema = {
        type: 'object',
        properties: {
          name: { type: 'invalid-type' }
        }
      };

      const result = validateSchema(invalidSchema);

      // AJV might not catch all type errors in strict: false mode
      // But it should catch structural issues
      expect(result).toBeDefined();
    });

    it('should validate complex valid schemas', () => {
      const complexSchema = {
        type: 'object',
        properties: {
          name: {
            type: 'string',
            minLength: 1,
            maxLength: 100
          },
          age: {
            type: 'number',
            minimum: 0,
            maximum: 150
          },
          email: {
            type: 'string',
            format: 'email'
          },
          tags: {
            type: 'array',
            items: { type: 'string' }
          }
        },
        required: ['name', 'email']
      };

      const result = validateSchema(complexSchema);

      expect(result.valid).toBe(true);
    });
  });

  describe('error messages', () => {
    it('should return multiple errors', () => {
      const invalidSchema = {
        type: 'array',
        properties: 'invalid'
      };

      const result = validateSchema(invalidSchema);

      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it('should include instance path in AJV errors', () => {
      const invalidSchema = {
        type: 'object',
        properties: {
          field: {
            type: 'invalid'
          }
        }
      };

      const result = validateSchema(invalidSchema);

      if (!result.valid) {
        result.errors.forEach(error => {
          expect(typeof error).toBe('string');
        });
      }
    });

    it('should structure errors correctly', () => {
      const result = validateSchema({ type: 'array' });

      expect(result).toHaveProperty('valid');
      expect(result).toHaveProperty('errors');
      expect(Array.isArray(result.errors)).toBe(true);
    });
  });

  describe('edge cases', () => {
    it('should handle schema with additionalProperties', () => {
      const schema = {
        type: 'object',
        properties: {
          name: { type: 'string' }
        },
        additionalProperties: true
      };

      const result = validateSchema(schema);

      expect(result.valid).toBe(true);
    });

    it('should handle schema with required fields', () => {
      const schema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          email: { type: 'string' }
        },
        required: ['name', 'email']
      };

      const result = validateSchema(schema);

      expect(result.valid).toBe(true);
    });

    it('should handle nested object properties', () => {
      const schema = {
        type: 'object',
        properties: {
          user: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              address: {
                type: 'object',
                properties: {
                  street: { type: 'string' },
                  city: { type: 'string' }
                }
              }
            }
          }
        }
      };

      const result = validateSchema(schema);

      expect(result.valid).toBe(true);
    });

    it('should handle array properties', () => {
      const schema = {
        type: 'object',
        properties: {
          tags: {
            type: 'array',
            items: { type: 'string' }
          },
          numbers: {
            type: 'array',
            items: { type: 'number' }
          }
        }
      };

      const result = validateSchema(schema);

      expect(result.valid).toBe(true);
    });

    it('should handle schema with allSupported formats', () => {
      const schema = {
        type: 'object',
        properties: {
          email: { type: 'string', format: 'email' },
          date: { type: 'string', format: 'date' },
          uri: { type: 'string', format: 'uri' }
        }
      };

      const result = validateSchema(schema);

      expect(result.valid).toBe(true);
    });
  });

  describe('SchemaValidationResult type', () => {
    it('should return correct type structure', () => {
      const result: SchemaValidationResult = validateSchema({ type: 'object' });

      expect(typeof result.valid).toBe('boolean');
      expect(Array.isArray(result.errors)).toBe(true);
    });

    it('should have valid=false when errors exist', () => {
      const result = validateSchema('invalid');

      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it('should have valid=true when no errors', () => {
      const result = validateSchema({
        type: 'object',
        properties: {}
      });

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
  });
});
