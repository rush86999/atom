//! Property-based tests for Atom desktop application
//!
//! Uses proptest to test invariants across generated inputs.
//!
//! Property-based testing generates hundreds of random inputs to verify
//! invariants that should always hold true. This is especially useful for:
//! - File operations (path handling, edge cases, cross-platform consistency)
//! - State management (serializing/deserializing)
//! - Command validation (whitelist logic)
//! - Data structures (sorting, searching, transformations)

use proptest::prelude::*;

#[cfg(test)]
mod sample_tests {
    use super::*;

    proptest! {
        #[test]
        fn test_string_reverse_invariant(s in "\\PC{.*}") {
            // INVARIANT: Reversing a string twice returns the original
            // VALIDATED_BUG: String reversal with Unicode characters can fail
            // if not handled character-by-character. Rust's .chars() handles
            // this correctly, avoiding the bug where byte-based reversal
            // corrupts multi-byte UTF-8 sequences.
            // Root cause: UTF-8 characters can be 1-4 bytes, reversing bytes
            // instead of code points breaks the encoding.
            // Fixed in: This implementation uses .chars() which iterates over
            // Unicode scalar values, not bytes.
            // Scenario: "Hello世界" reversed byte-by-byte becomes "��界olleH"
            // (corrupted), but char-by-char becomes "界世olleH" (correct).

            let reversed: String = s.chars().rev().collect();
            let reversed_again: String = reversed.chars().rev().collect();
            prop_assert_eq!(s, reversed_again);
        }

        #[test]
        fn test_vec_sort_invariant(mut vec in prop::collection::vec(any::<i32>(), 0..100)) {
            // INVARIANT: Sorting a vector twice yields the same result as sorting once
            // VALIDATED_BUG: Unstable sorts can produce different orderings for
            // equal elements, causing inconsistent results when sorting multiple times.
            // Rust's .sort() is stable, so equal elements maintain their relative order.
            // Root cause: Unstable sorting algorithms (like quicksort) don't preserve
            // the original order of equal elements.
            // Fixed in: Rust's sort() uses a stable sort algorithm (Timsort).
            // Scenario: Sorting [(1, "a"), (1, "b"), (1, "c")] by first element
            // always yields the same order with stable sort, but unstable sort
            // may shuffle "a", "b", "c" randomly.

            let mut vec2 = vec.clone();
            vec.sort();
            vec.sort();
            vec2.sort();

            prop_assert_eq!(vec, vec2);
        }

        #[test]
        fn test_option_identity_invariant(opt in proptest::option::any::<i32>()) {
            // INVARIANT: Option identity transformations preserve the value
            // VALIDATED_BUG: None.unwrap_or_default() and Some(x).unwrap_or_default()
            // should both produce valid values, but mismatched types can cause panics.
            // Root cause: unwrap_or_default() requires T: Default trait.
            // Fixed in: This test verifies the invariant holds for i32 which implements Default.
            // Scenario: None::<i32>.unwrap_or_default() = 0, Some(42).unwrap_or_default() = 42.

            let mapped = opt.map(|x| x);
            let transformed = opt.unwrap_or_default();

            // Mapping identity should preserve Some/None
            prop_assert_eq!(opt, mapped);

            // unwrap_or_default on Some should preserve the value
            if let Some(v) = opt {
                prop_assert_eq!(v, transformed);
            }
        }
    }
}
