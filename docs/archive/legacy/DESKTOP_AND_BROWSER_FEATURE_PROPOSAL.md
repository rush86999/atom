# Proposal: Tauri Desktop Client, Browser Automation, and Local-First Deployment

This document outlines a proposal to extend Atom's capabilities with a native desktop client, a browser automation skill for the agent, and a fully local deployment option. These features will make Atom more accessible, powerful, and private.

## 1. Local-First Deployment

A robust local-first deployment is the foundation for a true desktop experience. The goal is to enable users to run the entire Atom stack on their personal machines without relying on remote servers.

### Implementation Strategy

1.  **Review Existing Docker Compose Setup:** The existing `docker-compose.yml` in `atomic-docker/` is the starting point. I will analyze it to identify all services and their dependencies.
2.  **Eliminate Remote Dependencies:** I will identify all services that rely on remote endpoints (e.g., AWS services, remote databases) and replace them with local alternatives.
    *   **Database:** The current `docker-compose.yml` already includes a Postgres service, which is great. I will ensure it's configured to persist data locally.
    *   **Vector Store:** The current setup uses LanceDB, which can run locally. I will ensure it's configured for local file-based storage.
    *   **Other Services:** I will review all other services to ensure they can run offline.
3.  **Create a `local-only.env` File:** To make this easy for users, I will create a `.env.local-only` file with all the necessary environment variables pre-configured for a local setup.
4.  **Update Documentation:** I will create a new `README.md` in a `desktop/` directory to provide clear, step-by-step instructions on how to launch the local-only version of Atom.

## 2. Tauri Desktop Client

Tauri is an excellent choice for building a desktop client because it allows us to leverage the existing web frontend. This will give us a native-like experience on all major desktop platforms.

### Implementation Strategy

1.  **Set Up a New Tauri Project:** I will create a new directory, `desktop/`, and initialize a Tauri project within it.
2.  **Integrate the Web Frontend:** I will configure Tauri to use the existing Next.js frontend from `atomic-docker/app_build_docker/` as its web-view. This will require some adjustments to the frontend's build process to ensure it's compatible with Tauri.
3.  **Native-Like Experience:** I will add native menus, keyboard shortcuts, and other platform-specific features to make the application feel at home on macOS, Windows, and Linux.
4.  **Build and Packaging:** I will set up the necessary build scripts to package the Tauri application for distribution on all three platforms.

## 3. Browser Automation Skill

Empowering the Atom agent with the ability to control a web browser will unlock a vast new range of automation possibilities.

### Implementation Strategy

1.  **Choose a Browser Automation Library:** I will use a modern and robust browser automation library like Playwright or Puppeteer. These libraries provide a high-level API for controlling browsers and are well-suited for this task.
2.  **Create a New `browser` Skill:** I will create a new skill for the Atom agent called `browser`. This skill will encapsulate all the browser automation logic.
3.  **Implement Core Browser Actions:** The `browser` skill will support the following actions:
    *   `goto(url)`: Navigate to a specific URL.
    *   `click(selector)`: Click on an element on the page.
    *   `type(selector, text)`: Type text into an input field.
    *   `extract(selector, attribute)`: Extract text or an attribute from an element.
    *   `screenshot(path)`: Take a screenshot of the page.
4.  **Natural Language Interface:** I will enhance the agent's NLU to understand natural language commands for browser automation. For example:
    *   "Atom, open tauri-apps.com and take a screenshot."
    *   "Atom, go to GitHub, search for 'Atom', and click on the first result."
5.  **Security and Privacy:** Browser automation will be handled with care to ensure user privacy and security. All browser operations will be executed locally, and no sensitive information will be logged or transmitted to remote servers.

## Next Steps

After you approve this proposal, I will begin by implementing the **Local-First Deployment**. This is the most critical piece, as it provides the foundation for the other two features. Once that is complete, I will move on to the **Tauri Desktop Client** and the **Browser Automation Skill**.
