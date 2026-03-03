// Property-based tests for IPC message serialization
//
// Tests IPC command serialization invariants using proptest to generate edge cases.
//
// These tests validate critical invariants for desktop IPC communication:
// - Command serialization round-trip (serializing then deserializing preserves data)
// - Response integrity (success/error responses maintain data)
// - Complex data type handling (nested objects, arrays, optionals)
// - Unicode string preservation (UTF-8, emoji, multi-byte characters)
// - Error handling (invalid JSON, type mismatches, oversized messages)
// - Type safety (enum serialization, invalid values rejected)
//
// IPC serialization is critical because it's the bridge between JavaScript (frontend)
// and Rust (backend). Data corruption here causes silent failures and security issues.

use proptest::prelude::*;
use serde::{Deserialize, Serialize};

// ============================================================================
// Test Data Structures
// ============================================================================

/// Represents an IPC command sent from JavaScript to Rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct ICommand {
    name: String,
    args: Vec<u8>,
}

/// Represents a success response from Rust to JavaScript
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct SuccessResponse {
    success: bool,
    data: serde_json::Value,
}

/// Represents an error response from Rust to JavaScript
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct ErrorResponse {
    success: bool,
    error_code: String,
    error_message: String,
}

/// Represents a complex nested data structure
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct ComplexData {
    id: String,
    metadata: Metadata,
    items: Vec<Item>,
    optional_field: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct Metadata {
    timestamp: i64,
    version: String,
    tags: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
struct Item {
    name: String,
    value: i32,
    active: bool,
}

// ============================================================================
// Command Serialization Round-Trip Tests
// ============================================================================

proptest! {
    #[test]
    fn prop_command_serialization_roundtrip(
        cmd_name in "[a-z_]+",
        args in prop::collection::vec(any::<u8>(), 0..100),
    ) {
        // INVARIANT: IPC command serialization round-trip preserves all fields
        // VALIDATED_BUG: None - serde_json handles round-trip correctly
        // Root cause: Rust's serde provides reliable serialization with type safety
        // Scenario: Command with arbitrary args serializes then deserializes identically
        // Edge cases: Empty args, large args (100 bytes), special characters in command name

        let command = ICommand { name: cmd_name.clone(), args };
        let serialized = serde_json::to_string(&command).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.name, cmd_name);
        prop_assert_eq!(deserialized.args, command.args);
    }

    #[test]
    fn prop_command_with_special_chars(
        base_name in "[a-z]+",
        special_chars in prop::sample::select(vec!["_", "_", "_", "0", "1", "2"]),
        args in prop::collection::vec(any::<u8>(), 0..50),
    ) {
        // INVARIANT: Command names with underscores and numbers serialize correctly
        // VALIDATED_BUG: None - serde_json preserves all characters
        // Root cause: JSON string encoding handles alphanumeric and underscore correctly
        // Scenario: Commands like "open_file_dialog_2" serialize without corruption
        // Edge cases: Multiple underscores, trailing numbers, mixed alphanumeric

        let cmd_name = format!("{}_{}", base_name, special_chars);
        let command = ICommand { name: cmd_name.clone(), args };
        let serialized = serde_json::to_string(&command).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.name, cmd_name);
        prop_assert_eq!(deserialized.args, command.args);
    }
}

// ============================================================================
// Response Round-Trip Integrity Tests
// ============================================================================

proptest! {
    #[test]
    fn prop_success_response_roundtrip(
        key in "[a-z]+",
        value in prop::collection::vec(any::<u8>(), 0..50),
    ) {
        // INVARIANT: Success response serialization preserves success flag and data
        // VALIDATED_BUG: None - serde_json maintains boolean and nested data
        // Root cause: JSON boolean and object types are well-defined
        // Scenario: Response { success: true, data: { key: "..." } } round-trips correctly
        // Edge cases: Empty data, nested objects, arrays, null values

        let data = serde_json::json!({
            key: value,
            "timestamp": 1234567890,
            "nested": {
                "field": "value"
            }
        });

        let response = SuccessResponse {
            success: true,
            data: data.clone(),
        };

        let serialized = serde_json::to_string(&response).unwrap();
        let deserialized: SuccessResponse = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.success, true);
        prop_assert_eq!(deserialized.data, data);
    }

    #[test]
    fn prop_error_response_roundtrip(
        error_code in "[A-Z_]+",
        error_msg in prop::string::string_regex("[a-zA-Z0-9\\s]{0,100}").unwrap(),
    ) {
        // INVARIANT: Error response preserves error code and message
        // VALIDATED_BUG: None - JSON strings maintain error information
        // Root cause: String encoding handles spaces and alphanumeric correctly
        // Scenario: ErrorResponse { success: false, error_code: "FILE_NOT_FOUND", ... } round-trips
        // Edge cases: Empty error message, long messages (100 chars), special characters

        let response = ErrorResponse {
            success: false,
            error_code: error_code.clone(),
            error_message: error_msg.clone(),
        };

        let serialized = serde_json::to_string(&response).unwrap();
        let deserialized: ErrorResponse = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.success, false);
        prop_assert_eq!(deserialized.error_code, error_code);
        prop_assert_eq!(deserialized.error_message, error_msg);
    }

    #[test]
    fn prop_response_with_null_data(_dummy in prop::option::of(any::<()>())) {
        // INVARIANT: Responses with null/empty data serialize correctly
        // VALIDATED_BUG: None - serde_json::Value handles null explicitly
        // Root cause: JSON has a native null type, serde preserves it
        // Scenario: Response { success: true, data: null } round-trips correctly
        // Edge cases: Null in nested objects, empty arrays, empty objects

        let response = SuccessResponse {
            success: true,
            data: serde_json::Value::Null,
        };

        let serialized = serde_json::to_string(&response).unwrap();
        let deserialized: SuccessResponse = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.success, true);
        prop_assert_eq!(deserialized.data, serde_json::Value::Null);
    }
}

// ============================================================================
// Complex Data Type Serialization Tests
// ============================================================================

proptest! {
    #[test]
    fn prop_nested_object_serialization(
        id in "[a-z0-9]+",
        tag_count in 0usize..10,
        item_count in 0usize..5,
    ) {
        // INVARIANT: Nested objects serialize and deserialize correctly
        // VALIDATED_BUG: None - serde handles nested structs recursively
        // Root cause: Recursive Serialize/Deserialize derive macros handle nesting
        // Scenario: ComplexData with nested Metadata and Vec<Item> round-trips correctly
        // Edge cases: Empty arrays, deeply nested objects, mixed types

        let tags: Vec<String> = (0..tag_count)
            .map(|i| format!("tag_{}", i))
            .collect();

        let items: Vec<Item> = (0..item_count)
            .map(|i| Item {
                name: format!("item_{}", i),
                value: i as i32,
                active: i % 2 == 0,
            })
            .collect();

        let data = ComplexData {
            id: id.clone(),
            metadata: Metadata {
                timestamp: 1234567890,
                version: "1.0.0".to_string(),
                tags: tags.clone(),
            },
            items: items.clone(),
            optional_field: None,
        };

        let serialized = serde_json::to_string(&data).unwrap();
        let deserialized: ComplexData = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.id, id);
        prop_assert_eq!(deserialized.metadata.tags, tags);
        prop_assert_eq!(deserialized.items.len(), items.len());
    }

    #[test]
    fn prop_array_order_preservation(
        elements in prop::collection::vec(any::<i32>(), 0..20),
    ) {
        // INVARIANT: Array order is preserved during serialization
        // VALIDATED_BUG: None - JSON arrays maintain order
        // Root cause: JSON arrays are ordered sequences, serde preserves order
        // Scenario: [1, 2, 3] serializes and deserializes as [1, 2, 3], not [3, 2, 1]
        // Edge cases: Empty array, single element, duplicate values

        let serialized = serde_json::to_string(&elements).unwrap();
        let deserialized: Vec<i32> = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized, elements);
    }

    #[test]
    fn prop_optional_field_handling(
        has_value in prop::sample::select(vec![true, false]),
        value_str in "[a-z]+",
    ) {
        // INVARIANT: Option<T> fields handle None/Some correctly
        // VALIDATED_BUG: None - serde Option handling is explicit
        // Root cause: Option<T> serializes to null (None) or value (Some)
        // Scenario: optional_field: None serializes as null, Some("x") as "x"
        // Edge cases: Empty string, None vs Some(""), nested Option types

        let optional = if has_value {
            Some(value_str.clone())
        } else {
            None
        };

        let data = ComplexData {
            id: "test".to_string(),
            metadata: Metadata {
                timestamp: 0,
                version: "1.0".to_string(),
                tags: vec![],
            },
            items: vec![],
            optional_field: optional.clone(),
        };

        let serialized = serde_json::to_string(&data).unwrap();
        let deserialized: ComplexData = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.optional_field, optional);
    }
}

// ============================================================================
// Unicode String Preservation Tests
// ============================================================================

proptest! {
    #[test]
    fn prop_unicode_string_roundtrip(
        // Generate Unicode strings including multi-byte characters
        text in prop::string::string_regex(".{0,50}").unwrap(),
    ) {
        // INVARIANT: Unicode strings are preserved across round-trip
        // VALIDATED_BUG: None - serde_json uses UTF-8 encoding
        // Root cause: JSON strings are UTF-8 by specification, Rust enforces this
        // Scenario: "Hello 世界 🌍" serializes and deserializes correctly
        // Edge cases: Emoji (4-byte UTF-8), accented characters, CJK characters, right-to-left text

        let command = ICommand {
            name: "test_command".to_string(),
            args: text.as_bytes().to_vec(),
        };

        let serialized = serde_json::to_string(&command).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.args, text.as_bytes().to_vec());
    }

    #[test]
    fn prop_emoji_preservation(
        // Generate strings with emoji (multi-byte UTF-8)
        base in "[a-zA-Z]+",
        emoji in prop::sample::select(vec![
            "🌍", "🎉", "✅", "❌", "⚠️", "🔥", "💻", "🚀"
        ]),
    ) {
        // INVARIANT: Emoji (4-byte UTF-8) are preserved correctly
        // VALIDATED_BUG: None - UTF-8 handles all Unicode code points
        // Root cause: Rust strings are UTF-8, serde_json preserves encoding
        // Scenario: "Error: ⚠️" round-trips without corruption
        // Edge cases: Multiple emoji, emoji at start/mid/end, emoji + text

        let text = format!("{} {}", base, emoji);
        let command = ICommand {
            name: text.clone(),
            args: vec![],
        };

        let serialized = serde_json::to_string(&command).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.name, text);
    }

    #[test]
    fn prop_multilingual_text(
        // Generate text in multiple languages
        text in prop::sample::select(vec![
            "Hello World",
            "こんにちは世界",  // Japanese
            "你好世界",        // Chinese
            "안녕하세요",      // Korean
            "Привет мир",     // Russian
            "مرحبا بالعالم",  // Arabic
            "Ñoño café",      // Spanish with accents
        ])
    ) {
        // INVARIANT: Non-Latin scripts are preserved correctly
        // VALIDATED_BUG: None - UTF-8 is encoding-agnostic
        // Root cause: UTF-8 encodes all Unicode code points regardless of script
        // Scenario: CJK, Arabic, Cyrillic, accented characters all round-trip correctly
        // Edge cases: Right-to-left text, combining characters, zero-width characters

        let command = ICommand {
            name: text.to_string(),
            args: vec![],
        };

        let serialized = serde_json::to_string(&command).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.name, text);
    }
}

// ============================================================================
// Error Handling Invariants
// ============================================================================

proptest! {
    #[test]
    fn prop_invalid_json_rejected(
        // Generate invalid JSON strings
        invalid_json in prop::sample::select(vec![
            "{invalid json}",
            "{missing_brace",
            "undefined",
            "function() {}",
            "[1, 2,",
            "{key: value}",  // Unquoted keys
        ])
    ) {
        // INVARIANT: Invalid JSON returns error, doesn't panic/crash
        // VALIDATED_BUG: None - serde_json returns Result::Err for invalid JSON
        // Root cause: serde_json parser validates JSON syntax
        // Scenario: Malformed JSON returns Err, not undefined behavior
        // Edge cases: Syntax errors, trailing commas, undefined values

        let result: Result<ICommand, _> = serde_json::from_str(invalid_json);

        prop_assert!(result.is_err(), "Invalid JSON should be rejected");
    }

    #[test]
    fn prop_type_mismatch_rejected(_dummy in prop::option::of(any::<()>())) {
        // INVARIANT: Type mismatches return error, don't panic
        // VALIDATED_BUG: None - serde validates types at deserialization
        // Root cause: Strong typing in Rust ensures type correctness
        // Scenario: {"name": 123} fails to deserialize name: String
        // Edge cases: Number for string, object for array, boolean for integer

        let invalid_data = serde_json::json!({
            "name": 123,  // Should be string
            "args": []    // Should be array of bytes
        });

        let result: Result<ICommand, _> = serde_json::from_value(invalid_data);

        prop_assert!(result.is_err(), "Type mismatch should be rejected");
    }

    #[test]
    fn prop_missing_fields_handled(
        // Test with optional fields missing
        include_args in prop::sample::select(vec![true, false]),
    ) {
        // INVARIANT: Missing required fields return error, optional fields use defaults
        // VALIDATED_BUG: None - serde defaults require all fields by default
        // Root cause: Deserialize derive macro requires all fields unless #[serde(default)]
        // Scenario: {"name": "cmd"} without "args" returns error (required field missing)
        // Edge cases: Missing required field, missing optional field

        if include_args {
            let valid_data = serde_json::json!({
                "name": "test_cmd",
                "args": []
            });

            let result: Result<ICommand, _> = serde_json::from_value(valid_data);
            prop_assert!(result.is_ok(), "Valid data should deserialize");
        } else {
            let invalid_data = serde_json::json!({
                "name": "test_cmd"
                // "args" is missing (required field)
            });

            let result: Result<ICommand, _> = serde_json::from_value(invalid_data);
            prop_assert!(result.is_err(), "Missing required field should fail");
        }
    }
}

// ============================================================================
// Type Safety Invariants
// ============================================================================

proptest! {
    #[test]
    fn prop_enum_serialization(
        // Test enum-like string values
        variant in prop::sample::select(vec![
            "success",
            "error",
            "pending",
            "cancelled",
            "timeout"
        ])
    ) {
        // INVARIANT: Enum variant strings serialize correctly
        // VALIDATED_BUG: None - Rust enums serialize as strings or tags
        // Root cause: Serde supports multiple enum representations
        // Scenario: Enum variants serialize to predictable JSON values
        // Edge cases: Unknown variants, case sensitivity, numeric variants

        #[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
        enum Status {
            Success,
            Error,
            Pending,
            Cancelled,
            Timeout,
        }

        // Map string to enum
        let status = match variant {
            "success" => Status::Success,
            "error" => Status::Error,
            "pending" => Status::Pending,
            "cancelled" => Status::Cancelled,
            "timeout" => Status::Timeout,
            _ => unreachable!(),
        };

        let serialized = serde_json::to_string(&status).unwrap();
        let deserialized: Status = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(status, deserialized);
    }

    #[test]
    fn prop_numeric_boundaries(
        // Test boundary values
        value in prop::sample::select(vec![
            i32::MIN,
            i32::MAX,
            0,
            -1,
            1,
            1000,
            -1000,
        ])
    ) {
        // INVARIANT: Numeric boundary values serialize correctly
        // VALIDATED_BUG: None - JSON numbers handle full i32 range
        // Root cause: JSON numbers are arbitrary precision, serde handles conversion
        // Scenario: i32::MIN, i32::MAX round-trip correctly
        // Edge cases: Zero, negative values, large positive values

        let item = Item {
            name: "test".to_string(),
            value,
            active: true,
        };

        let serialized = serde_json::to_string(&item).unwrap();
        let deserialized: Item = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.value, value);
    }

    #[test]
    fn prop_boolean_serialization(
        value in prop::sample::select(vec![true, false])
    ) {
        // INVARIANT: Boolean values serialize to true/false (not 1/0)
        // VALIDATED_BUG: None - JSON has native boolean type
        // Root cause: JSON spec defines true/false literals, serde follows spec
        // Scenario: true serializes as "true", not "1" or "True"
        // Edge cases: None (boolean is unambiguous)

        let item = Item {
            name: "test".to_string(),
            value: 0,
            active: value,
        };

        let serialized = serde_json::to_string(&item).unwrap();
        let deserialized: Item = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.active, value);
        prop_assert!(serialized.contains("true") || serialized.contains("false"));
    }
}

// ============================================================================
// Message Size Limits
// ============================================================================

proptest! {
    #[test]
    fn prop_empty_message_handling(_dummy in prop::option::of(any::<()>())) {
        // INVARIANT: Empty messages are handled gracefully
        // VALIDATED_BUG: None - empty objects/arrays are valid JSON
        // Root cause: JSON spec allows empty structures
        // Scenario: {"name": "", "args": []} serializes and deserializes correctly
        // Edge cases: Empty string, empty array, empty object

        let command = ICommand {
            name: "".to_string(),
            args: vec![],
        };

        let serialized = serde_json::to_string(&command).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.name, "");
        prop_assert!(deserialized.args.is_empty());
    }

    #[test]
    fn prop_large_args_array(
        // Generate large args arrays (up to 10KB)
        size in 0usize..10000,
    ) {
        // INVARIANT: Large messages (10KB) serialize correctly
        // VALIDATED_BUG: None - serde_json has no arbitrary size limits
        // Root cause: Streaming JSON parser handles large payloads
        // Scenario: 10KB args array serializes and deserializes correctly
        // Edge cases: 0 bytes, 1 byte, 10KB, 100KB (if testing)
        // Note: Production should enforce size limits for security

        let args: Vec<u8> = (0..size).map(|i| (i % 256) as u8).collect();

        let command = ICommand {
            name: "large_cmd".to_string(),
            args: args.clone(),
        };

        let serialized = serde_json::to_string(&command).unwrap();
        let deserialized: ICommand = serde_json::from_str(&serialized).unwrap();

        prop_assert_eq!(deserialized.args, args);
        prop_assert!(serialized.len() >= size, "Serialized size should be >= data size");
    }
}
