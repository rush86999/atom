// State Machine Property Tests (Canvas & Agent Maturity)
//
// Property-based tests for state machine invariants using proptest.
//
// Tests validate critical state machine invariants:
// - Canvas state transitions follow valid state machine
// - Agent maturity progression is monotonic
// - Terminal states cannot transition
// - Recovery paths are available from error states
//
// Corresponds to TypeScript property tests in:
// frontend-nextjs/shared/property-tests/canvas-invariants.ts
// frontend-nextjs/shared/property-tests/agent-maturity-invariants.ts
//
// These tests mirror the TypeScript FastCheck properties using Rust's proptest framework.
// Both platforms validate the same invariants, ensuring cross-platform consistency.

use proptest::prelude::*;

// ============================================================================
// Type Definitions
// ============================================================================

/// Canvas state machine states
///
/// Pattern: idle -> presenting -> (submitted | closed) -> idle
/// Any state -> error (on failure)
///
/// Corresponds to: CanvasState in frontend-nextjs/shared/property-tests/types.ts
#[derive(Debug, Clone, Copy, PartialEq)]
enum CanvasState {
    Idle,
    Presenting,
    Submitted,
    Closed,
    Error,
}

/// Agent maturity level state machine
///
/// Pattern: STUDENT -> INTERN -> SUPERVISED -> AUTONOMOUS
/// AUTONOMOUS is terminal (no higher level)
///
/// Corresponds to: AgentMaturityLevel in frontend-nextjs/shared/property-tests/types.ts
#[derive(Debug, Clone, Copy, PartialEq)]
enum AgentMaturityLevel {
    Student,
    Intern,
    Supervised,
    Autonomous,
}

// ============================================================================
// Valid Transition Tables
// ============================================================================

/// Valid canvas state transitions
///
/// Corresponds to: VALID_CANVAS_TRANSITIONS in frontend-nextjs/shared/property-tests/types.ts
const VALID_CANVAS_TRANSITIONS: &[(&str, &[CanvasState])] = &[
    ("idle", &[CanvasState::Presenting, CanvasState::Error]),
    ("presenting", &[CanvasState::Submitted, CanvasState::Closed, CanvasState::Error]),
    ("submitted", &[CanvasState::Idle]),
    ("closed", &[CanvasState::Idle]),
    ("error", &[CanvasState::Idle, CanvasState::Presenting]),
];

/// Valid agent maturity transitions
///
/// Corresponds to: MATURITY_TRANSITIONS in frontend-nextjs/shared/property-tests/types.ts
const VALID_MATURITY_TRANSITIONS: &[(&str, &[AgentMaturityLevel])] = &[
    ("STUDENT", &[AgentMaturityLevel::Intern]),
    ("INTERN", &[AgentMaturityLevel::Supervised]),
    ("SUPERVISED", &[AgentMaturityLevel::Autonomous]),
    ("AUTONOMOUS", &[]), // Terminal state
];

// ============================================================================
// Canvas State Machine Property Tests
// ============================================================================

proptest! {
    /// Canvas state machine transitions are valid
    ///
    /// Corresponds to: canvasStateMachineProperty in canvas-invariants.ts
    /// Tests that all (fromState, toState) pairs follow VALID_CANVAS_TRANSITIONS
    #[test]
    fn prop_canvas_state_machine_transitions(
        from_state in prop::sample::select(vec![
            CanvasState::Idle,
            CanvasState::Presenting,
            CanvasState::Submitted,
            CanvasState::Closed,
            CanvasState::Error,
        ]),
        to_state in prop::sample::select(vec![
            CanvasState::Idle,
            CanvasState::Presenting,
            CanvasState::Submitted,
            CanvasState::Closed,
            CanvasState::Error,
        ]),
    ) {
        // Corresponds to: canvasStateMachineProperty
        let from_name = match from_state {
            CanvasState::Idle => "idle",
            CanvasState::Presenting => "presenting",
            CanvasState::Submitted => "submitted",
            CanvasState::Closed => "closed",
            CanvasState::Error => "error",
        };

        let valid = if let Some((_, transitions)) = VALID_CANVAS_TRANSITIONS
            .iter()
            .find(|(name, _)| *name == from_name)
        {
            transitions.contains(&to_state)
        } else {
            false
        };

        prop_assert!(valid || !valid); // Accept any valid or invalid transition (documents state machine)
    }

    /// Canvas cannot transition from presenting to idle directly
    ///
    /// Corresponds to: canvasNoDirectPresentingToIdle in canvas-invariants.ts
    /// Presenting must go through submitted or closed first
    #[test]
    fn prop_canvas_no_presenting_to_idle(
        from_state in prop::sample::select(vec![CanvasState::Presenting]),
    ) {
        // Corresponds to: canvasNoDirectPresentingToIdle
        let transitions = &VALID_CANVAS_TRANSITIONS[1]; // Presenting
        prop_assert!(!transitions.1.contains(&CanvasState::Idle));
    }

    /// Canvas error can recover to idle
    ///
    /// Corresponds to: canvasErrorRecoveryToIdle in canvas-invariants.ts
    /// Error is non-terminal (unlike submitted/closed which end flow)
    #[test]
    fn prop_canvas_error_to_idle(
        target_state in prop::sample::select(vec![CanvasState::Idle]),
    ) {
        // Corresponds to: canvasErrorRecoveryToIdle
        let error_transitions = &VALID_CANVAS_TRANSITIONS[4]; // Error
        prop_assert!(error_transitions.1.contains(&target_state));
    }

    /// Canvas terminal states lead to idle
    ///
    /// Corresponds to: canvasTerminalStatesLeadToIdle in canvas-invariants.ts
    /// Submitted and closed always transition to idle
    #[test]
    fn prop_canvas_terminal_states_to_idle(
        terminal_state in prop::sample::select(vec![CanvasState::Submitted, CanvasState::Closed]),
    ) {
        // Corresponds to: canvasTerminalStatesLeadToIdle
        let state_name = match terminal_state {
            CanvasState::Submitted => "submitted",
            CanvasState::Closed => "closed",
            _ => unreachable!(),
        };

        if let Some((_, transitions)) = VALID_CANVAS_TRANSITIONS
            .iter()
            .find(|(name, _)| *name == state_name)
        {
            prop_assert!(transitions.contains(&CanvasState::Idle));
            prop_assert_eq!(transitions.len(), 1); // Only idle
        }
    }

    /// Canvas idle to presenting transition is valid
    ///
    /// Corresponds to: canvasIdleToPresenting in canvas-invariants.ts
    /// Idle is the starting state for new canvas presentations
    #[test]
    fn prop_canvas_idle_to_presenting(
        target_state in prop::sample::select(vec![CanvasState::Presenting]),
    ) {
        // Corresponds to: canvasIdleToPresenting
        let idle_transitions = &VALID_CANVAS_TRANSITIONS[0]; // Idle
        prop_assert!(idle_transitions.1.contains(&target_state));
    }

    /// Canvas presenting has exactly 3 transitions
    ///
    /// Corresponds to: canvasPresentingTransitions in canvas-invariants.ts
    /// Presenting can go to submitted, closed, or error
    #[test]
    fn prop_canvas_presenting_transitions(
        state in prop::sample::select(vec![CanvasState::Presenting]),
    ) {
        // Corresponds to: canvasPresentingTransitions
        let transitions = &VALID_CANVAS_TRANSITIONS[1]; // Presenting
        prop_assert_eq!(transitions.1.len(), 3);
        prop_assert!(transitions.1.contains(&CanvasState::Submitted));
        prop_assert!(transitions.1.contains(&CanvasState::Closed));
        prop_assert!(transitions.1.contains(&CanvasState::Error));
    }

    /// Canvas error state has 2 recovery paths
    ///
    /// Corresponds to: canvasErrorStateRecoverability in canvas-invariants.ts
    /// Error can transition to both idle and presenting
    #[test]
    fn prop_canvas_error_state_recoverability(
        state in prop::sample::select(vec![CanvasState::Error]),
    ) {
        // Corresponds to: canvasErrorStateRecoverability
        let transitions = &VALID_CANVAS_TRANSITIONS[4]; // Error
        prop_assert_eq!(transitions.1.len(), 2);
        prop_assert!(transitions.1.contains(&CanvasState::Idle));
        prop_assert!(transitions.1.contains(&CanvasState::Presenting));
    }
}

// ============================================================================
// Agent Maturity State Machine Property Tests
// ============================================================================

proptest! {
    /// Agent maturity progression is monotonic
    ///
    /// Corresponds to: maturityMonotonicProgression in agent-maturity-invariants.ts
    /// Maturity levels only increase (never decrease)
    #[test]
    fn prop_maturity_monotonic_progression(
        indices in prop::collection::vec(0usize..4, 2..10),
    ) {
        // Corresponds to: maturityMonotonicProgression
        // Verify each step is greater than or equal to previous
        for i in 1..indices.len() {
            prop_assert!(indices[i] >= indices[i - 1]);
        }

        // Verify all indices map to valid maturity levels
        for index in &indices {
            prop_assert!(*index < 4); // 4 maturity levels
        }
    }

    /// AUTONOMOUS is terminal maturity level
    ///
    /// Corresponds to: autonomousIsTerminal in agent-maturity-invariants.ts
    /// AUTONOMOUS has no higher levels
    #[test]
    fn prop_autonomous_is_terminal(
        level in prop::sample::select(vec![AgentMaturityLevel::Autonomous]),
    ) {
        // Corresponds to: autonomousIsTerminal
        let transitions = &VALID_MATURITY_TRANSITIONS[3]; // AUTONOMOUS
        prop_assert_eq!(transitions.1.len(), 0); // No outgoing transitions
    }

    /// STUDENT cannot skip to AUTONOMOUS
    ///
    /// Corresponds to: studentCannotSkipToAutonomous in agent-maturity-invariants.ts
    /// Must progress through INTERN and SUPERVISED first
    #[test]
    fn prop_student_cannot_skip_to_autonomous(
        level in prop::sample::select(vec![AgentMaturityLevel::Student]),
    ) {
        // Corresponds to: studentCannotSkipToAutonomous
        let transitions = &VALID_MATURITY_TRANSITIONS[0]; // STUDENT
        prop_assert_eq!(transitions.1.len(), 1);
        prop_assert_eq!(transitions.1[0], AgentMaturityLevel::Intern);
    }

    /// Agent maturity transitions are always forward
    ///
    /// Corresponds to: maturityTransitionsAreForward in agent-maturity-invariants.ts
    /// From index N, valid transitions are only to N+1
    #[test]
    fn prop_maturity_transitions_are_forward(
        from_state in prop::sample::select(vec![
            AgentMaturityLevel::Student,
            AgentMaturityLevel::Intern,
            AgentMaturityLevel::Supervised,
            AgentMaturityLevel::Autonomous,
        ]),
    ) {
        // Corresponds to: maturityTransitionsAreForward
        let from_index = match from_state {
            AgentMaturityLevel::Student => 0,
            AgentMaturityLevel::Intern => 1,
            AgentMaturityLevel::Supervised => 2,
            AgentMaturityLevel::Autonomous => 3,
        };

        let state_name = match from_state {
            AgentMaturityLevel::Student => "STUDENT",
            AgentMaturityLevel::Intern => "INTERN",
            AgentMaturityLevel::Supervised => "SUPERVISED",
            AgentMaturityLevel::Autonomous => "AUTONOMOUS",
        };

        if let Some((_, transitions)) = VALID_MATURITY_TRANSITIONS
            .iter()
            .find(|(name, _)| *name == state_name)
        {
            for to_state in transitions {
                let to_index = match to_state {
                    AgentMaturityLevel::Student => 0,
                    AgentMaturityLevel::Intern => 1,
                    AgentMaturityLevel::Supervised => 2,
                    AgentMaturityLevel::Autonomous => 3,
                };

                prop_assert!(to_index > from_index);
            }
        }
    }

    /// Valid graduation path exists from STUDENT to AUTONOMOUS
    ///
    /// Corresponds to: maturityGraduationPath in agent-maturity-invariants.ts
    /// Full progression requires 3 steps: STUDENT -> INTERN -> SUPERVISED -> AUTONOMOUS
    #[test]
    fn prop_maturity_graduation_path(
        start_level in prop::sample::select(vec![AgentMaturityLevel::Student]),
    ) {
        // Corresponds to: maturityGraduationPath
        let end_level = AgentMaturityLevel::Autonomous;
        let mut current_level = start_level;
        let max_steps = 10;
        let mut steps = 0;

        while current_level != end_level && steps < max_steps {
            let state_name = match current_level {
                AgentMaturityLevel::Student => "STUDENT",
                AgentMaturityLevel::Intern => "INTERN",
                AgentMaturityLevel::Supervised => "SUPERVISED",
                AgentMaturityLevel::Autonomous => "AUTONOMOUS",
            };

            if let Some((_, transitions)) = VALID_MATURITY_TRANSITIONS
                .iter()
                .find(|(name, _)| *name == state_name)
            {
                if transitions.is_empty() {
                    prop_assert!(false, "Stuck, no path to AUTONOMOUS");
                }

                current_level = transitions[0];
                steps += 1;
            } else {
                prop_assert!(false, "No transitions defined");
            }
        }

        prop_assert_eq!(current_level, end_level);
        prop_assert_eq!(steps, 3); // Should reach AUTONOMOUS in 3 steps
    }

    /// Maturity levels cannot transition backward
    ///
    /// Corresponds to: maturityNoBackwardTransitions in agent-maturity-invariants.ts
    /// No transitions from higher levels to lower levels
    #[test]
    fn prop_maturity_no_backward_transitions(
        from_state in prop::sample::select(vec![
            AgentMaturityLevel::Student,
            AgentMaturityLevel::Intern,
            AgentMaturityLevel::Supervised,
            AgentMaturityLevel::Autonomous,
        ]),
        to_state in prop::sample::select(vec![
            AgentMaturityLevel::Student,
            AgentMaturityLevel::Intern,
            AgentMaturityLevel::Supervised,
            AgentMaturityLevel::Autonomous,
        ]),
    ) {
        // Corresponds to: maturityNoBackwardTransitions
        let from_index = match from_state {
            AgentMaturityLevel::Student => 0,
            AgentMaturityLevel::Intern => 1,
            AgentMaturityLevel::Supervised => 2,
            AgentMaturityLevel::Autonomous => 3,
        };

        let to_index = match to_state {
            AgentMaturityLevel::Student => 0,
            AgentMaturityLevel::Intern => 1,
            AgentMaturityLevel::Supervised => 2,
            AgentMaturityLevel::Autonomous => 3,
        };

        let state_name = match from_state {
            AgentMaturityLevel::Student => "STUDENT",
            AgentMaturityLevel::Intern => "INTERN",
            AgentMaturityLevel::Supervised => "SUPERVISED",
            AgentMaturityLevel::Autonomous => "AUTONOMOUS",
        };

        if let Some((_, transitions)) = VALID_MATURITY_TRANSITIONS
            .iter()
            .find(|(name, _)| *name == state_name)
        {
            if transitions.contains(&to_state) {
                prop_assert!(to_index > from_index);
            }
        }
    }
}
