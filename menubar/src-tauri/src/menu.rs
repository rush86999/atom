use tauri::{App, Manager, menu::{Menu, MenuItem, PredefinedMenuItem, Submenu, IsMenuItem}, Runtime};

/// Create the system tray menu for the menu bar app
pub fn create_menu<R: Runtime>(app: &App<R>) -> Result<Menu<R>, String> {
    let show_item = MenuItem::with_id(app, "show", "Show", true, Some("Cmd+Shift+A"))
        .map_err(|e| e.to_string())?;
    let hide_item = MenuItem::with_id(app, "hide", "Hide", true, None as Option<&str>)
        .map_err(|e| e.to_string())?;
    let quit_item = MenuItem::with_id(app, "quit", "Quit", true, Some("Cmd+Q"))
        .map_err(|e| e.to_string())?;

    // Create submenu for quick actions (placeholders for future use)
    let _quick_chat_item = MenuItem::with_id(
        app,
        "quick-chat",
        "Quick Chat",
        true,
        Some("Cmd+Shift+A")
    ).map_err(|e| e.to_string())?;

    let _recent_agents_item = MenuItem::with_id(
        app,
        "recent-agents",
        "Recent Agents",
        true,
        None as Option<&str>
    ).map_err(|e| e.to_string())?;

    let _recent_canvases_item = MenuItem::with_id(
        app,
        "recent-canvases",
        "Recent Canvases",
        true,
        None as Option<&str>
    ).map_err(|e| e.to_string())?;

    // Create main menu
    let menu = Menu::with_items(app, &[
        &show_item as &dyn IsMenuItem<R>,
        &hide_item as &dyn IsMenuItem<R>,
        &quit_item as &dyn IsMenuItem<R>,
    ]).map_err(|e| e.to_string())?;

    Ok(menu)
}

/// Create the native macOS menu bar menu
pub fn create_menu_bar_menu<R: Runtime>(app: &App<R>) -> Result<Menu<R>, String> {
    // App menu
    let about = MenuItem::with_id(app, "about", "About Atom", true, None as Option<&str>)
        .map_err(|e| e.to_string())?;
    let hide_app = PredefinedMenuItem::hide(app, None)
        .map_err(|e| e.to_string())?;
    let hide_others = PredefinedMenuItem::hide_others(app, None)
        .map_err(|e| e.to_string())?;
    let show_all = PredefinedMenuItem::show_all(app, None)
        .map_err(|e| e.to_string())?;
    let quit = PredefinedMenuItem::quit(app, None)
        .map_err(|e| e.to_string())?;

    let app_menu = Submenu::with_items(
        app,
        "Atom",
        true,
        &[
            &about as &dyn IsMenuItem<R>,
            &hide_app as &dyn IsMenuItem<R>,
            &hide_others as &dyn IsMenuItem<R>,
            &show_all as &dyn IsMenuItem<R>,
            &quit as &dyn IsMenuItem<R>,
        ],
    ).map_err(|e| e.to_string())?;

    // File menu
    let new_chat = MenuItem::with_id(app, "new-chat", "New Chat", true, Some("Cmd+N"))
        .map_err(|e| e.to_string())?;
    let close_window = MenuItem::with_id(app, "close", "Close Window", true, Some("Cmd+W"))
        .map_err(|e| e.to_string())?;

    let file_menu = Submenu::with_items(
        app,
        "File",
        true,
        &[
            &new_chat as &dyn IsMenuItem<R>,
            &close_window as &dyn IsMenuItem<R>,
        ],
    ).map_err(|e| e.to_string())?;

    // Edit menu
    let cut = PredefinedMenuItem::cut(app, None)
        .map_err(|e| e.to_string())?;
    let copy = PredefinedMenuItem::copy(app, None)
        .map_err(|e| e.to_string())?;
    let paste = PredefinedMenuItem::paste(app, None)
        .map_err(|e| e.to_string())?;
    let select_all = PredefinedMenuItem::select_all(app, None)
        .map_err(|e| e.to_string())?;

    let edit_menu = Submenu::with_items(
        app,
        "Edit",
        true,
        &[
            &cut as &dyn IsMenuItem<R>,
            &copy as &dyn IsMenuItem<R>,
            &paste as &dyn IsMenuItem<R>,
            &select_all as &dyn IsMenuItem<R>,
        ],
    ).map_err(|e| e.to_string())?;

    // View menu
    let refresh = MenuItem::with_id(app, "refresh", "Refresh", true, Some("Cmd+R"))
        .map_err(|e| e.to_string())?;
    let toggle_agents = MenuItem::with_id(
        app,
        "toggle-agents",
        "Show Agents",
        true,
        Some("Cmd+Shift+A")
    ).map_err(|e| e.to_string())?;

    let view_menu = Submenu::with_items(
        app,
        "View",
        true,
        &[
            &refresh as &dyn IsMenuItem<R>,
            &toggle_agents as &dyn IsMenuItem<R>,
        ],
    ).map_err(|e| e.to_string())?;

    // Create main menu bar
    let menu = Menu::with_items(app, &[
        &app_menu as &dyn IsMenuItem<R>,
        &file_menu as &dyn IsMenuItem<R>,
        &edit_menu as &dyn IsMenuItem<R>,
        &view_menu as &dyn IsMenuItem<R>,
    ]).map_err(|e| e.to_string())?;

    Ok(menu)
}
