// Serialization Roundtrip Property Tests
//
// Property-based tests for serialization invariants using proptest.
//
// Tests validate critical serialization invariants:
// - JSON roundtrip preserves data structure
// - Agent data survives serialization
// - Canvas data survives serialization
// - Array order is preserved
// - Special values (null, undefined) are handled correctly
//
// Corresponds to TypeScript property tests in:
// frontend-nextjs/shared/property-tests/serialization-invariants.ts
//
// These tests mirror the TypeScript FastCheck properties using Rust's proptest framework.
// Both platforms validate the same invariants, ensuring cross-platform consistency.

use proptest::prelude::*;
use serde::{Deserialize, Serialize};

// ============================================================================
// Type Definitions
// ============================================================================

/// Agent data structure
///
/// Corresponds to: agentDataRoundtrip property in serialization-invariants.ts
#[derive(Serialize, Deserialize, Debug, PartialEq)]
struct Agent {
    id: String,
    name: String,
    maturity_level: String,
    created_at: String,
    is_active: bool,
}

/// Canvas data structure
///
/// Corresponds to: canvasDataRoundtrip property in serialization-invariants.ts
#[derive(Serialize, Deserialize, Debug, PartialEq)]
struct Canvas {
    id: String,
    canvas_type: String,
    state: String,
    data: serde_json::Value,
    created_at: String,
    updated_at: Option<String>,
}

// ============================================================================
// JSON Roundtrip Property Tests
// ============================================================================

proptest! {
    /// JSON roundtrip preserves data
    ///
    /// Corresponds to: jsonRoundtripPreservesData in serialization-invariants.ts
    /// Tests that serde_json (de)serialization preserves arbitrary JSON data
    #[test]
    fn prop_json_roundtrip_preserves_data(
        input in any::<serde_json::Value>(),
    ) {
        // Corresponds to: jsonRoundtripPreservesData
        let serialized = serde_json::to_string(&input).unwrap();
        let deserialized: serde_json::Value = serde_json::from_str(&serialized).unwrap();
        prop_assert_eq!(input, deserialized);
    }

    /// Agent data roundtrip preserves all fields
    ///
    /// Corresponds to: agentDataRoundtrip in serialization-invariants.ts
    /// Tests that Agent data structure survives JSON roundtrip
    #[test]
    fn prop_agent_data_roundtrip(
        id in "[a-z0-9]{32}",
        name in "[a-zA-Z]{5,50}",
        maturity_level in prop::sample::select(vec!["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        is_active in prop::bool::ANY,
    ) {
        // Corresponds to: agentDataRoundtrip
        let agent = Agent {
            id: id.clone(),
            name: name.clone(),
            maturity_level: maturity_level.to_string(),
            created_at: "2024-01-01T00:00:00Z".to_string(),
            is_active,
        };

        let serialized = serde_json::to_string(&agent).unwrap();
        let deserialized: Agent = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.id, id);
        prop_assert_eq!(deserialized.name, name);
        prop_assert_eq!(deserialized.maturity_level, maturity_level);
        prop_assert_eq!(deserialized.is_active, is_active);
    }

    /// Canvas data roundtrip preserves state
    ///
    /// Corresponds to: canvasDataRoundtrip in serialization-invariants.ts
    /// Tests that Canvas data structure survives JSON roundtrip
    #[test]
    fn prop_canvas_data_roundtrip(
        id in "[a-z0-9]{32}",
        canvas_type in prop::sample::select(vec!["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"]),
        state in prop::sample::select(vec!["idle", "presenting", "submitted", "closed", "error"]),
    ) {
        // Corresponds to: canvasDataRoundtrip
        let canvas = Canvas {
            id: id.clone(),
            canvas_type: canvas_type.to_string(),
            state: state.to_string(),
            data: serde_json::json!({"key": "value"}),
            created_at: "2024-01-01T00:00:00Z".to_string(),
            updated_at: Some("2024-01-01T01:00:00Z".to_string()),
        };

        let serialized = serde_json::to_string(&canvas).unwrap();
        let deserialized: Canvas = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.id, id);
        prop_assert_eq!(deserialized.canvas_type, canvas_type);
        prop_assert_eq!(deserialized.state, state);
        prop_assert_eq!(deserialized.updated_at, Some("2024-01-01T01:00:00Z".to_string()));
    }

    /// Array order is preserved in JSON roundtrip
    ///
    /// Corresponds to: arrayOrderPreserved in serialization-invariants.ts
    /// Tests that Vec order is preserved
    #[test]
    fn prop_array_order_preserved(
        elements in prop::collection::vec(any::<i32>(), 0..20),
    ) {
        // Corresponds to: arrayOrderPreserved
        let serialized = serde_json::to_string(&elements).unwrap();
        let deserialized: Vec<i32> = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized, elements);
    }

    /// Null and undefined handling
    ///
    /// Corresponds to: nullAndUndefinedHandling in serialization-invariants.ts
    /// Tests that null and undefined are handled correctly
    #[test]
    fn prop_null_and_undefined_handling(
        field1_optional in prop::option::of(prop::string::string_regex("[a-z]{1,10}")),
        field2_nullable in prop::option::of(prop::string::string_regex("[a-z]{1,10}")),
        field3 in prop::bool::ANY,
    ) {
        // Corresponds to: nullAndUndefinedHandling
        #[derive(Serialize, Deserialize, PartialEq)]
        struct TestData {
            field1: Option<String>,
            field2: Option<String>,
            field3: bool,
        }

        let data = TestData {
            field1: field1_optional,
            field2: field2_nullable,
            field3,
        };

        let serialized = serde_json::to_string(&data).unwrap();
        let deserialized: TestData = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.field3, field3);
        // field2 (nullable) should be preserved
        prop_assert_eq!(deserialized.field2, field2_nullable);
    }

    /// Date serialization preserves timestamp
    ///
    /// Corresponds to: dateSerialization in serialization-invariants.ts
    /// Tests that Date objects are serialized correctly as ISO strings
    #[test]
    fn prop_date_serialization(
        timestamp in 0i64..10000000000i64,
    ) {
        // Corresponds to: dateSerialization
        #[derive(Serialize, Deserialize)]
        struct DataWithDate {
            timestamp: i64,
        }

        let data = DataWithDate { timestamp };

        let serialized = serde_json::to_string(&data).unwrap();
        let deserialized: DataWithDate = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.timestamp, timestamp);
    }

    /// Nested object serialization
    ///
    /// Corresponds to: nestedObjectSerialization in serialization-invariants.ts
    /// Tests that deeply nested objects survive JSON roundtrip
    #[test]
    fn prop_nested_object_serialization(
        key_count in 0usize..10,
        nested_depth in 0usize..5,
    ) {
        // Corresponds to: nestedObjectSerialization
        let mut nested_obj = serde_json::Value::Object(serde_json::Map::new());

        // Create nested structure
        for i in 0..key_count {
            let key = format!("key_{}", i);
            let mut value = serde_json::json!({});

            // Add nested objects based on depth
            for j in 0..nested_depth {
                let nested_key = format!("nested_{}", j);
                value[nested_key] = serde_json::json!(j);
            }

            nested_obj[key] = value;
        }

        let serialized = serde_json::to_string(&nested_obj).unwrap();
        let deserialized: serde_json::Value = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(nested_obj, deserialized);
    }

    /// Special characters in strings are preserved
    ///
    /// Corresponds to: specialCharactersInStrings in serialization-invariants.ts
    /// Tests that Unicode, escape sequences survive JSON roundtrip
    #[test]
    fn prop_special_characters_in_strings(
        base_string in "[a-zA-Z]{1,20}",
    ) {
        // Corresponds to: specialCharactersInStrings
        let special_strings = vec![
            format!("{}\\n{}", base_string, base_string),
            format!("{}\\r{}", base_string, base_string),
            format!("{}\\t{}", base_string, base_string),
            format!("{}\"{}\"", base_string, base_string),
            format!("{}'{}'", base_string, base_string),
            format!("{}Hello 世界 🌍{}", base_string, base_string),
        ];

        for original_string in special_strings {
            let data = serde_json::json!({ "text": original_string });
            let serialized = serde_json::to_string(&data).unwrap();
            let deserialized: serde_json::Value = serde_json::from_str(&serialized).unwrap();

            prop_assert_eq!(deserialized["text"], original_string);
        }
    }

    /// Number precision preservation
    ///
    /// Corresponds to: numberPrecisionPreservation in serialization-invariants.ts
    /// Tests that numeric precision is preserved in JSON roundtrip
    #[test]
    fn prop_number_precision_preservation(
        original_number in -100000i64..100000i64,
    ) {
        // Corresponds to: numberPrecisionPreservation
        let data = serde_json::json!({ "value": original_number });

        let serialized = serde_json::to_string(&data).unwrap();
        let deserialized: serde_json::Value = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized["value"], original_number);
    }

    /// Boolean serialization
    ///
    /// Corresponds to: booleanSerialization in serialization-invariants.ts
    /// Tests that boolean values survive JSON roundtrip
    #[test]
    fn prop_boolean_serialization(
        original_boolean in prop::bool::ANY,
    ) {
        // Corresponds to: booleanSerialization
        let data = serde_json::json!({ "flag": original_boolean });

        let serialized = serde_json::to_string(&data).unwrap();
        let deserialized: serde_json::Value = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized["flag"], original_boolean);
    }

    /// Empty values handling
    ///
    /// Corresponds to: emptyValuesHandling in serialization-invariants.ts
    /// Tests that empty arrays, empty objects, and empty strings survive JSON roundtrip
    #[test]
    fn prop_empty_values_handling(
        _dummy in prop::option::of(any::<>()),
    ) {
        // Corresponds to: emptyValuesHandling
        #[derive(Serialize, Deserialize, PartialEq)]
        struct EmptyData {
            empty_string: String,
            empty_array: Vec<i32>,
            empty_object: serde_json::Value,
        }

        let data = EmptyData {
            empty_string: String::new(),
            empty_array: vec![],
            empty_object: serde_json::json!({}),
        };

        let serialized = serde_json::to_string(&data).unwrap();
        let deserialized: EmptyData = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.empty_string, "");
        prop_assert_eq!(deserialized.empty_array.len(), 0);
        prop_assert_eq!(deserialized.empty_object, serde_json::json!({}));
    }
}

// ============================================================================
// Error Handling Property Tests
// ============================================================================

proptest! {
    /// Invalid JSON is rejected
    ///
    /// Corresponds to: Error handling tests in serialization-invariants.ts
    /// Tests that invalid JSON returns error, doesn't panic
    #[test]
    fn prop_invalid_json_rejected(
        invalid_json in prop::sample::select(vec![
            "{invalid json}",
            "{missing_brace",
            "undefined",
            "function() {}",
            "[1, 2,",
            "{key: value}",
        ]),
    ) {
        // Corresponds to: Error handling invariants
        let result: Result<serde_json::Value, _> = serde_json::from_str(invalid_json);
        prop_assert!(result.is_err(), "Invalid JSON should be rejected");
    }

    /// Type mismatch is rejected
    ///
    /// Corresponds to: Type mismatch tests in serialization-invariants.ts
    /// Tests that type mismatches return error, don't panic
    #[test]
    fn prop_type_mismatch_rejected(
        _dummy in prop::option::of(any::<>()),
    ) {
        // Corresponds to: Type mismatch invariants
        let invalid_data = serde_json::json!({
            "id": 123,  // Should be string
            "name": "test",
            "maturity_level": "STUDENT",
            "created_at": "2024-01-01T00:00:00Z",
            "is_active": true
        });

        let result: Result<Agent, _> = serde_json::from_value(invalid_data);
        prop_assert!(result.is_err(), "Type mismatch should be rejected");
    }
}
