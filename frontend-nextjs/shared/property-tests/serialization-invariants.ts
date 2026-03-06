/**
 * Serialization Roundtrip Property Tests
 *
 * Property-based tests for serialization invariants.
 * Tests verify that data survives JSON serialization/deserialization:
 * - JSON roundtrip preserves data structure
 * - Agent data survives serialization
 * - Canvas data survives serialization
 * - Array order is preserved
 * - Special values (null, undefined) are handled correctly
 *
 * @module property-tests/serialization-invariants
 */

import fc from 'fast-check';

/**
 * Deep equality comparison helper.
 *
 * Handles nested objects, arrays, and special values (null, undefined).
 * Used for verifying data after serialization roundtrip.
 *
 * @param a - First value to compare
 * @param b - Second value to compare
 * @returns true if values are deeply equal, false otherwise
 *
 * @example
 * ```ts
 * const original = { a: 1, b: { c: 2 } };
 * const serialized = JSON.stringify(original);
 * const deserialized = JSON.parse(serialized);
 * deepEquals(original, deserialized); // true
 * ```
 */
export function deepEquals(a: unknown, b: unknown): boolean {
  // Handle null/undefined
  if (a === null || a === undefined) {
    return a === b;
  }

  if (b === null || b === undefined) {
    return a === b;
  }

  // Handle primitives
  if (typeof a !== 'object' || typeof b !== 'object') {
    return a === b;
  }

  // Handle arrays
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) {
      return false;
    }

    for (let i = 0; i < a.length; i++) {
      if (!deepEquals(a[i], b[i])) {
        return false;
      }
    }

    return true;
  }

  // Handle array vs object mismatch
  if (Array.isArray(a) !== Array.isArray(b)) {
    return false;
  }

  // Handle objects
  if (a instanceof Object && b instanceof Object) {
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);

    if (keysA.length !== keysB.length) {
      return false;
    }

    for (const key of keysA) {
      if (!keysB.includes(key)) {
        return false;
      }

      const valA = (a as Record<string, unknown>)[key];
      const valB = (b as Record<string, unknown>)[key];

      if (!deepEquals(valA, valB)) {
        return false;
      }
    }

    return true;
  }

  return false;
}

/**
 * JSON roundtrip preserves data property.
 *
 * Tests that JSON.stringify → JSON.parse preserves arbitrary JSON data.
 * Uses fc.jsonObject() for arbitrary JSON generation.
 *
 * @example
 * ```ts
 * fc.assert(jsonRoundtripPreservesData);
 * ```
 *
 * Invariant: For all JSON values, stringify → parse preserves structure
 */
export const jsonRoundtripPreservesData = fc.property(
  fc.jsonObject(),
  (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);

    return deepEquals(data, deserialized);
  }
);

/**
 * Agent data roundtrip property.
 *
 * Tests that agent data structure survives JSON roundtrip.
 * Uses fc.record() with specific agent fields.
 *
 * @example
 * ```ts
 * fc.assert(agentDataRoundtrip);
 * ```
 *
 * Invariant: Agent data fields preserved after serialization
 */
export const agentDataRoundtrip = fc.property(
  fc.record({
    id: fc.uuid(),
    name: fc.string(),
    maturity_level: fc.constantFrom('STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS' as const),
    created_at: fc.date(),
    is_active: fc.boolean(),
    metadata: fc.option(fc.record({
      version: fc.integer({ min: 1, max: 10 }),
      tags: fc.array(fc.string()),
    }), { nil: undefined }),
  }),
  (agentData) => {
    const serialized = JSON.stringify(agentData);
    const deserialized = JSON.parse(serialized);

    // Verify all fields preserved
    return deepEquals(agentData, deserialized);
  }
);

/**
 * Canvas data roundtrip property.
 *
 * Tests that canvas data structure survives JSON roundtrip.
 * Uses fc.record() with canvas-specific fields.
 *
 * @example
 * ```ts
 * fc.assert(canvasDataRoundtrip);
 * ```
 *
 * Invariant: Canvas data fields and state preserved after serialization
 */
export const canvasDataRoundtrip = fc.property(
  fc.record({
    id: fc.uuid(),
    type: fc.constantFrom('generic', 'docs', 'email', 'sheets', 'orchestration', 'terminal', 'coding' as const),
    state: fc.constantFrom('idle', 'presenting', 'submitted', 'closed', 'error' as const),
    data: fc.jsonObject(),
    created_at: fc.date(),
    updated_at: fc.option(fc.date(), { nil: undefined }),
    metadata: fc.option(fc.record({
      title: fc.string(),
      description: fc.string(),
    }), { nil: undefined }),
  }),
  (canvasData) => {
    const serialized = JSON.stringify(canvasData);
    const deserialized = JSON.parse(serialized);

    // Verify all fields preserved
    return deepEquals(canvasData, deserialized);
  }
);

/**
 * Array order preserved property.
 *
 * Tests that array order is preserved in JSON roundtrip.
 * Uses fc.array(fc.jsonObject()) for arbitrary arrays.
 *
 * @example
 * ```ts
 * fc.assert(arrayOrderPreserved);
 * ```
 *
 * Invariant: Array element order unchanged after serialization
 */
export const arrayOrderPreserved = fc.property(
  fc.array(fc.jsonObject(), { minLength: 0, maxLength: 20 }),
  (originalArray) => {
    const serialized = JSON.stringify(originalArray);
    const deserialized = JSON.parse(serialized) as unknown[];

    // Verify length preserved
    if (originalArray.length !== deserialized.length) {
      return false;
    }

    // Verify order preserved
    for (let i = 0; i < originalArray.length; i++) {
      if (!deepEquals(originalArray[i], deserialized[i])) {
        return false;
      }
    }

    return true;
  }
);

/**
 * Null and undefined handling property.
 *
 * Tests that null and undefined are handled correctly in JSON roundtrip.
 * Note: JSON.stringify() converts undefined to null or omits the field.
 *
 * @example
 * ```ts
 * fc.assert(nullAndUndefinedHandling);
 * ```
 *
 * Invariant: Null values preserved, undefined handled consistently
 */
export const nullAndUndefinedHandling = fc.property(
  fc.record({
    field1: fc.option(fc.string(), { nil: undefined }),
    field2: fc.option(fc.integer(), { nil: null }),
    field3: fc.boolean(),
  }),
  (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);

    // field3 (boolean) should always be preserved
    if (data.field3 !== deserialized.field3) {
      return false;
    }

    // field2 (nullable integer) should be preserved (null stays null)
    if (data.field2 !== deserialized.field2) {
      return false;
    }

    // field1 (undefined) becomes null or is omitted
    // This is expected JSON behavior
    const field1Preserved = deserialized.field1 === null || deserialized.field1 === undefined;

    return field1Preserved;
  }
);

/**
 * Date serialization property.
 *
 * Tests that Date objects are serialized correctly as ISO strings.
 * JSON.stringify() converts Date to ISO string, JSON.parse() returns string.
 *
 * @example
 * ```ts
 * fc.assert(dateSerialization);
 * ```
 *
 * Invariant: Date → ISO string → Date preserves timestamp
 */
export const dateSerialization = fc.property(
  fc.date(),
  (originalDate) => {
    const dataWithDate = { timestamp: originalDate };

    const serialized = JSON.stringify(dataWithDate);
    const deserialized = JSON.parse(serialized) as { timestamp: string };

    // Verify date is converted to ISO string
    if (typeof deserialized.timestamp !== 'string') {
      return false;
    }

    // Verify timestamp can be parsed back to Date
    const parsedDate = new Date(deserialized.timestamp);
    const timeEqual = originalDate.getTime() === parsedDate.getTime();

    return timeEqual;
  }
);

/**
 * Nested object serialization property.
 *
 * Tests that deeply nested objects survive JSON roundtrip.
 * Uses fc.dictionary() for arbitrary nested structures.
 *
 * @example
 * ```ts
 * fc.assert(nestedObjectSerialization);
 * ```
 *
 * Invariant: Nested object structure preserved after serialization
 */
export const nestedObjectSerialization = fc.property(
  fc.dictionary(fc.string(), fc.jsonObject(), { maxKeys: 10 }),
  (nestedObject) => {
    const serialized = JSON.stringify(nestedObject);
    const deserialized = JSON.parse(serialized);

    return deepEquals(nestedObject, deserialized);
  }
);

/**
 * Special characters in strings property.
 *
 * Tests that special characters (Unicode, escape sequences) survive JSON roundtrip.
 *
 * @example
 * ```ts
 * fc.assert(specialCharactersInStrings);
 * ```
 *
 * Invariant: Special characters preserved after serialization
 */
export const specialCharactersInStrings = fc.property(
  fc.stringOf(fc.constantFrom(...'\\n\r\t"\'\u{1F600}-\u{1F64F}'.split(''))),
  (originalString) => {
    const dataWithString = { text: originalString };

    const serialized = JSON.stringify(dataWithString);
    const deserialized = JSON.parse(serialized) as { text: string };

    return deserialized.text === originalString;
  }
);

/**
 * Number precision preservation property.
 *
 * Tests that numeric precision is preserved in JSON roundtrip.
 * JSON.stringify() uses Number.MAX_SAFE_INTEGER range.
 *
 * @example
 * ```ts
 * fc.assert(numberPrecisionPreservation);
 * ```
 *
 * Invariant: Numeric values preserved (within safe integer range)
 */
export const numberPrecisionPreservation = fc.property(
  fc.integer({ min: -Number.MAX_SAFE_INTEGER, max: Number.MAX_SAFE_INTEGER }),
  (originalNumber) => {
    const dataWithNumber = { value: originalNumber };

    const serialized = JSON.stringify(dataWithNumber);
    const deserialized = JSON.parse(serialized) as { value: number };

    return deserialized.value === originalNumber;
  }
);

/**
 * Boolean serialization property.
 *
 * Tests that boolean values survive JSON roundtrip.
 *
 * @example
 * ```ts
 * fc.assert(booleanSerialization);
 * ```
 *
 * Invariant: Boolean values preserved (true/false, not truthy/falsy)
 */
export const booleanSerialization = fc.property(
  fc.boolean(),
  (originalBoolean) => {
    const dataWithBoolean = { flag: originalBoolean };

    const serialized = JSON.stringify(dataWithBoolean);
    const deserialized = JSON.parse(serialized) as { flag: boolean };

    return deserialized.flag === originalBoolean;
  }
);

/**
 * Empty values handling property.
 *
 * Tests that empty arrays, empty objects, and empty strings survive JSON roundtrip.
 *
 * @example
 * ```ts
 * fc.assert(emptyValuesHandling);
 * ```
 *
 * Invariant: Empty values preserved (not converted to null/undefined)
 */
export const emptyValuesHandling = fc.property(
  fc.record({
    emptyString: fc.constantFrom(''),
    emptyArray: fc.constantFrom([]),
    emptyObject: fc.constantFrom({}),
  }),
  (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);

    // Verify empty values preserved
    if (deserialized.emptyString !== '') {
      return false;
    }

    if (!Array.isArray(deserialized.emptyArray) || deserialized.emptyArray.length !== 0) {
      return false;
    }

    if (typeof deserialized.emptyObject !== 'object' || Object.keys(deserialized.emptyObject).length !== 0) {
      return false;
    }

    return true;
  }
);
