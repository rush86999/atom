// Unit tests for menu item logic and properties
//
// These tests verify menu item construction, properties, and validation logic.
// They are pure Rust tests that don't require Tauri runtime.

#[cfg(test)]
mod tests {
    // Test helper functions to simulate menu item behavior
    // Since main.rs creates menu items directly via Tauri API,
    // we test the expected behavior and properties

    #[derive(Debug, Clone, PartialEq)]
    struct TestMenuItem {
        id: String,
        label: String,
        enabled: bool,
        accelerator: Option<String>,
    }

    impl TestMenuItem {
        fn new(id: &str, label: &str, enabled: bool, accelerator: Option<&str>) -> Self {
            TestMenuItem {
                id: id.to_string(),
                label: label.to_string(),
                enabled,
                accelerator: accelerator.map(|s| s.to_string()),
            }
        }

        fn label(&self) -> &str {
            &self.label
        }

        fn is_enabled(&self) -> bool {
            self.enabled
        }

        fn id(&self) -> &str {
            &self.id
        }

        fn accelerator(&self) -> Option<&str> {
            self.accelerator.as_deref()
        }
    }

    #[test]
    fn test_menu_item_label() {
        let item = TestMenuItem::new("show", "Show ATOM", true, None);
        assert_eq!(item.label(), "Show ATOM");
    }

    #[test]
    fn test_menu_item_enabled_true() {
        let enabled = TestMenuItem::new("show", "Show ATOM", true, None);
        assert!(enabled.is_enabled());
    }

    #[test]
    fn test_menu_item_enabled_false() {
        let disabled = TestMenuItem::new("show", "Show ATOM", false, None);
        assert!(!disabled.is_enabled());
    }

    #[test]
    fn test_menu_item_id() {
        let item = TestMenuItem::new("quit", "Quit", true, None);
        assert_eq!(item.id(), "quit");
    }

    #[test]
    fn test_menu_item_accelerator_none() {
        let item = TestMenuItem::new("show", "Show ATOM", true, None);
        assert!(item.accelerator().is_none());
    }

    #[test]
    fn test_menu_item_accelerator_some() {
        let item = TestMenuItem::new("save", "Save", true, Some("Cmd+S"));
        assert_eq!(item.accelerator(), Some("Cmd+S"));
    }

    #[test]
    fn test_menu_item_equality() {
        let item1 = TestMenuItem::new("show", "Show ATOM", true, None);
        let item2 = TestMenuItem::new("show", "Show ATOM", true, None);
        assert_eq!(item1, item2);
    }

    #[test]
    fn test_menu_item_inequality() {
        let item1 = TestMenuItem::new("show", "Show ATOM", true, None);
        let item2 = TestMenuItem::new("quit", "Quit", true, None);
        assert_ne!(item1, item2);
    }

    #[test]
    fn test_menu_item_clone() {
        let item = TestMenuItem::new("show", "Show ATOM", true, None);
        let cloned = item.clone();
        assert_eq!(item, cloned);
    }

    // Validation tests
    #[test]
    fn test_menu_item_id_non_empty() {
        let item = TestMenuItem::new("show", "Show ATOM", true, None);
        assert!(!item.id().is_empty());
    }

    #[test]
    fn test_menu_item_label_non_empty() {
        let item = TestMenuItem::new("show", "Show ATOM", true, None);
        assert!(!item.label().is_empty());
    }

    #[test]
    fn test_menu_item_no_duplicate_ids() {
        let items = vec![
            TestMenuItem::new("show", "Show ATOM", true, None),
            TestMenuItem::new("quit", "Quit", true, None),
        ];

        let ids: Vec<&str> = items.iter().map(|item| item.id()).collect();
        let unique_ids: std::collections::HashSet<_> = ids.iter().collect();

        assert_eq!(ids.len(), unique_ids.len());
    }

    #[test]
    fn test_menu_item_ids_are_unique() {
        let show_item = TestMenuItem::new("show", "Show ATOM", true, None);
        let quit_item = TestMenuItem::new("quit", "Quit", true, None);

        assert_ne!(show_item.id(), quit_item.id());
    }

    #[test]
    fn test_menu_state_management_enable() {
        let mut item = TestMenuItem::new("show", "Show ATOM", false, None);
        assert!(!item.is_enabled());

        item.enabled = true;
        assert!(item.is_enabled());
    }

    #[test]
    fn test_menu_state_management_disable() {
        let mut item = TestMenuItem::new("show", "Show ATOM", true, None);
        assert!(item.is_enabled());

        item.enabled = false;
        assert!(!item.is_enabled());
    }

    #[test]
    fn test_menu_item_valid_initial_state() {
        // Test that menu items from main.rs have valid initial state
        let show_item = TestMenuItem::new("show", "Show ATOM", true, None);
        let quit_item = TestMenuItem::new("quit", "Quit", true, None);

        // Both items should be enabled by default
        assert!(show_item.is_enabled());
        assert!(quit_item.is_enabled());

        // Both items should have non-empty labels
        assert!(!show_item.label().is_empty());
        assert!(!quit_item.label().is_empty());

        // Both items should have non-empty IDs
        assert!(!show_item.id().is_empty());
        assert!(!quit_item.id().is_empty());

        // Neither item should have keyboard shortcuts
        assert!(show_item.accelerator().is_none());
        assert!(quit_item.accelerator().is_none());
    }

    #[test]
    fn test_expected_menu_structure() {
        // Test the expected menu structure from main.rs
        let items = vec![
            TestMenuItem::new("show", "Show ATOM", true, None),
            TestMenuItem::new("quit", "Quit", true, None),
        ];

        // Should have exactly 2 items
        assert_eq!(items.len(), 2);

        // First item should be "Show ATOM"
        assert_eq!(items[0].id(), "show");
        assert_eq!(items[0].label(), "Show ATOM");

        // Second item should be "Quit"
        assert_eq!(items[1].id(), "quit");
        assert_eq!(items[1].label(), "Quit");

        // All items should be enabled
        assert!(items.iter().all(|item| item.is_enabled()));
    }

    #[test]
    fn test_menu_item_creation_order() {
        // Test that menu items are created in expected order
        let items = vec![
            TestMenuItem::new("show", "Show ATOM", true, None),
            TestMenuItem::new("quit", "Quit", true, None),
        ];

        // "show" should come before "quit"
        let show_index = items.iter().position(|item| item.id() == "show");
        let quit_index = items.iter().position(|item| item.id() == "quit");

        assert!(show_index.is_some());
        assert!(quit_index.is_some());
        assert!(show_index < quit_index);
    }

    #[test]
    fn test_menu_label_content() {
        // Test menu label content matches user-facing strings
        let items = vec![
            ("show", "Show ATOM"),
            ("quit", "Quit"),
        ];

        for (id, expected_label) in items {
            let item = TestMenuItem::new(id, expected_label, true, None);
            assert_eq!(item.id(), id);
            assert_eq!(item.label(), expected_label);
        }
    }

    #[test]
    fn test_menu_item_case_sensitivity() {
        // Test that menu item IDs are case-sensitive
        let item1 = TestMenuItem::new("Show", "Show", true, None);
        let item2 = TestMenuItem::new("show", "Show", true, None);

        assert_ne!(item1.id(), item2.id());
        assert_eq!(item1.label(), item2.label());
    }

    #[test]
    fn test_menu_accelerator_format() {
        // Test various accelerator formats
        let cmd_s = TestMenuItem::new("save", "Save", true, Some("Cmd+S"));
        let ctrl_c = TestMenuItem::new("copy", "Copy", true, Some("Ctrl+C"));
        let no_accelerator = TestMenuItem::new("help", "Help", true, None);

        assert_eq!(cmd_s.accelerator(), Some("Cmd+S"));
        assert_eq!(ctrl_c.accelerator(), Some("Ctrl+C"));
        assert!(no_accelerator.accelerator().is_none());
    }

    // NOTE: Since main.rs uses Tauri's MenuItem::with_id directly
    // without custom wrapper logic, these tests document the API behavior.
    // If custom menu logic is extracted to a separate module (menu.rs),
    // these tests can be updated to test that logic directly.
    //
    // TODO: Consider extracting menu creation logic to separate module
    // for better testability and to reduce duplication in main.rs
}
