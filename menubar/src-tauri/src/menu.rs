use tauri::{App, Manager, menu::{Menu, MenuItem, PredefinedMenuItem, Submenu}};

/// Create the system tray menu for the menu bar app
pub fn create_menu(app: &App) -> Menu {
    let show_item = MenuItem::with_id(app, "show", "Show", true, Some("Cmd+Shift+A"))?;
    let hide_item = MenuItem::with_id(app, "hide", "Hide", true, None)?;
    let quit_item = MenuItem::with_id(app, "quit", "Quit", true, Some("Cmd+Q"))?;

    // Create submenu for quick actions
    let quick_chat_item = MenuItem::new(
        app,
        "Quick Chat",
        true,
        Some("Cmd+Shift+A")
    )?;

    let recent_agents_item = MenuItem::new(
        app,
        "Recent Agents",
        true,
        None
    )?;

    let recent_canvases_item = MenuItem::new(
        app,
        "Recent Canvases",
        true,
        None
    )?;

    // Create main menu
    let menu = Menu::with_items(app, &[
        &show_item.into(),
        &hide_item.into(),
        &quit_item.into(),
    ])?;

    menu
}

/// Create the native macOS menu bar menu
pub fn create_menu_bar_menu(app: &App) -> Result<Menu, String> {
    // App menu
    let about = MenuItem::new(app, "About Atom", true, None)?;
    let hide_app = PredefinedMenuItem::hide(app, None)?;
    let hide_others = PredefinedMenuItem::hide_others(app, None)?;
    let show_all = PredefinedMenuItem::show_all(app, None)?;
    let quit = PredefinedMenuItem::quit(app, None)?;

    let app_menu = Submenu::with_items(
        app,
        "Atom",
        true,
        &[
            &about.into(),
            &hide_app.into(),
            &hide_others.into(),
            &show_all.into(),
            &quit.into(),
        ],
    ).map_err(|e| e.to_string())?;

    // File menu
    let new_chat = MenuItem::with_id(app, "new-chat", "New Chat", true, Some("Cmd+N"))?;
    let close_window = MenuItem::with_id(app, "close", "Close Window", true, Some("Cmd+W"))?;

    let file_menu = Submenu::with_items(
        app,
        "File",
        true,
        &[
            &new_chat.into(),
            &close_window.into(),
        ],
    ).map_err(|e| e.to_string())?;

    // Edit menu
    let cut = PredefinedMenuItem::cut(app, None)?;
    let copy = PredefinedMenuItem::copy(app, None)?;
    let paste = PredefinedMenuItem::paste(app, None)?;
    let select_all = PredefinedMenuItem::select_all(app, None)?;

    let edit_menu = Submenu::with_items(
        app,
        "Edit",
        true,
        &[
            &cut.into(),
            &copy.into(),
            &paste.into(),
            &select_all.into(),
        ],
    ).map_err(|e| e.to_string())?;

    // View menu
    let refresh = MenuItem::with_id(app, "refresh", "Refresh", true, Some("Cmd+R"))?;
    let toggle_agents = MenuItem::with_id(
        app,
        "toggle-agents",
        "Show Agents",
        true,
        Some("Cmd+Shift+A")
    )?;

    let view_menu = Submenu::with_items(
        app,
        "View",
        true,
        &[
            &refresh.into(),
            &toggle_agents.into(),
        ],
    ).map_err(|e| e.to_string())?;

    // Create main menu bar
    let menu = Menu::with_items(app, &[
        &app_menu.into(),
        &file_menu.into(),
        &edit_menu.into(),
        &view_menu.into(),
    ]).map_err(|e| e.to_string())?;

    Ok(menu)
}
