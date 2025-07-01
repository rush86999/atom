# Development Guide for Atom Agent (Docker Compose Setup)

This guide provides recommendations for developers working on the Atom Agent project, particularly when using the Docker Compose setup for local development. Following these practices will help maintain code quality, consistency, and make collaboration easier.

## 1. Prerequisites for Development

Ensure you have the following installed on your development machine:

*   **Git:** For version control.
*   **Docker and Docker Compose:** For running the application stack locally. Refer to the main `README.md` in this directory for setup instructions.
*   **Node.js (LTS version):** Required for UI (`app`, `handshake`, `oauth`) and backend (`functions`) services. Ensure `npm` or `yarn` is available.
*   **Python (e.g., 3.9+):** Required for the `python-agent` service. Ensure `pip` is available.
*   **IDE Recommendations:**
    *   VS Code is a popular choice with excellent support for TypeScript/JavaScript and Python, including extensions for Docker, ESLint, Prettier, Pylint, Black, etc.
    *   WebStorm (for Node.js/TypeScript) and PyCharm (for Python) are also powerful alternatives.

## 2. Code Quality & Linting (Static Analysis)

Maintaining consistent code style and catching errors early is crucial. We use linters and formatters for this.

### General Guidelines
*   Follow the existing code style within each service/module.
*   Write clean, readable, and well-commented code where necessary.
*   Ensure your IDE is configured to use the project's linting and formatting configurations.

### Node.js/TypeScript Services
(Applies to `app_build_docker`, `functions_build_docker`, `handshake_build_docker`, `oauth_build_docker`)

*   **ESLint:** Used for identifying and reporting on patterns in JavaScript/TypeScript.
    *   Configuration: Typically found in `.eslintrc.js` or `.eslintrc.json` in the service's root directory.
    *   To run: `npm run lint` or `yarn lint` (assuming scripts are defined in `package.json`).
*   **Prettier:** Used for automatic code formatting to ensure consistent style.
    *   Configuration: Typically found in `.prettierrc.js` or similar.
    *   To run: `npm run format` or `yarn format` (assuming scripts are defined).
*   **Dependency Vulnerabilities:** Regularly check for vulnerabilities in Node.js dependencies.
    *   Run: `npm audit` or `yarn audit`. Address critical vulnerabilities promptly.

### Python Services
(Applies to `python_agent_build_docker`)

*   **Flake8:** A wrapper around PyFlakes, pycodestyle, and McCabe. Good for checking style and complexity.
    *   To run: `flake8 .` from the service directory.
*   **Black:** The uncompromising Python code formatter.
    *   To run: `black .` from the service directory.
*   **Pylint:** A more comprehensive linter checking for errors, enforcing coding standards, and looking for code smells.
    *   To run: `pylint **/*.py` (or specific modules) from the service directory.
*   **Bandit:** A tool designed to find common security issues in Python code.
    *   To run: `bandit -r .` from the service directory.
*   Configuration files (e.g., `pyproject.toml` for Black, `.pylintrc` for Pylint) may be present in the service directory.

### Pre-commit Hooks (Highly Recommended)

To automate the process of running linters and formatters before code is committed:

1.  Install Husky: `npm install husky --save-dev` (in a root `package.json` or relevant service `package.json`).
2.  Install lint-staged: `npm install lint-staged --save-dev`.
3.  Configure Husky to run lint-staged on pre-commit (e.g., in `.husky/pre-commit` or `package.json`).
4.  Configure `lint-staged` in `package.json` to run specific linters/formatters on staged files.

Example `lint-staged` configuration in a Node.js service's `package.json`:
```json
{
  "lint-staged": {
    "*.{js,jsx,ts,tsx}": ["eslint --fix", "prettier --write"]
  }
}
```

## 3. Unit Testing

Unit tests are essential for verifying the correctness of individual components and functions, and for enabling safe refactoring.

### General Guidelines
*   Write unit tests for new features and bug fixes.
*   Aim for good test coverage of critical logic.
*   Tests should be small, fast, and independent.
*   Use descriptive names for your tests.

### Mocking Dependencies
When unit testing, it's crucial to isolate the unit under test from its external dependencies (e.g., database calls, external API requests, other services). Use mocking libraries to replace these dependencies with controlled substitutes (mocks/stubs/spies).

*   **Node.js/TypeScript (Jest):** Jest has built-in mocking capabilities (`jest.mock()`, `jest.fn()`, `jest.spyOn()`). Refer to Jest documentation for detailed usage. Mocked data should be used to simulate various scenarios.
*   **Python (PyTest/unittest):** Python's `unittest.mock` module (with `patch`, `Mock`, `MagicMock`) is standard. `pytest-mock` provides a convenient fixture for PyTest.

### Node.js/TypeScript Services

*   **Framework:** Jest is commonly used. (Check specific service `package.json` for test scripts and dependencies).
*   **Running Tests:** Typically `npm test` or `yarn test`.
*   **Test Files:** Often placed in `__tests__` directories or alongside source files with a `.test.ts` or `.spec.ts` extension.

### Python Services

*   **Framework:** PyTest or `unittest` are common. (Check for `pytest.ini` or test runner configurations).
*   **Running Tests:** Typically `pytest` from the service directory, or `python -m unittest discover`.
*   **Test Files:** Often placed in a `tests/` directory or named `test_*.py`.

## 4. Running All Checks (Example)

It's good practice to have a way to run all linters and tests across the project. This could be a shell script at the root of the `atomic-docker` directory or the main project root.

Example `scripts/run-all-checks.sh` (conceptual):
```bash
#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Running linters for Node.js services..."
# cd app_build_docker && npm run lint && cd ..
# cd functions_build_docker && npm run lint && cd ..
# ... (add for other Node.js services)

echo "Running linters for Python services..."
# cd python_agent_build_docker && flake8 . && black --check . && bandit -r . && cd ..

echo "Running unit tests for Node.js services..."
# cd app_build_docker && npm test && cd ..
# cd functions_build_docker && npm test && cd ..
# ...

echo "Running unit tests for Python services..."
# cd python_agent_build_docker && pytest && cd ..

echo "All checks passed!"
```
*(Note: The exact commands and paths in the script above would need to be verified and adjusted based on each service's actual setup and `package.json` / build system.)*

---

By following these guidelines, developers can contribute to a more stable, maintainable, and reliable Atom Agent application.

## 5. Code Review Process

All code contributions (new features, bug fixes, improvements) must go through a code review process before being merged into the main development branch (e.g., `main` or `develop`). This process helps maintain code quality, catch potential issues, and share knowledge across the team.

### Pull Request (PR) / Merge Request (MR) Workflow
1.  **Create a Feature Branch:** Create a new branch from the latest version of the main development branch for your changes.
    ```bash
    git checkout main
    git pull origin main
    git checkout -b your-feature-branch-name
    ```
2.  **Implement Changes:** Make your code changes, including adding relevant unit tests (see Section 3) and ensuring all code quality checks (see Section 2) pass locally.
3.  **Commit Changes:** Make clear, atomic commits with descriptive messages.
4.  **Push Branch:** Push your feature branch to the remote repository.
    ```bash
    git push origin your-feature-branch-name
    ```
5.  **Open a Pull/Merge Request:** Create a PR/MR from your feature branch targeting the main development branch.
    *   Provide a clear title and a detailed description of the changes, including the problem being solved or the feature being added.
    *   Reference any relevant issue numbers.
    *   Ensure any automated CI checks (linters, unit tests) pass on the PR.

### Reviewer Expectations
*   **Timeliness:** Reviewers should aim to provide feedback in a timely manner.
*   **Thoroughness:** Review the changes against the checklist below.
*   **Constructiveness:** Provide clear, actionable, and respectful feedback. Explain *why* a change is suggested, not just *what* to change. The goal is collaboration and improvement.
*   **Approval:** At least one (ideally two for significant changes) reviewer approval is required before merging.

### Review Checklist (Focus Areas)
Reviewers should consider the following aspects:
*   **Correctness & Functionality:**
    *   Does the code achieve its stated purpose?
    *   Does it correctly address the issue or implement the feature according to requirements?
    *   Are there any logical errors or flaws?
*   **Clarity & Readability:**
    *   Is the code well-structured and easy to understand?
    *   Are variable, function, and class names clear and descriptive?
    *   Is the code unnecessarily complex?
*   **Error Handling:**
    *   Are potential errors and edge cases handled gracefully?
    *   Is logging adequate for errors?
*   **Testing:**
    *   Are new unit tests included for new logic?
    *   Do existing tests still pass?
    *   Is the test coverage sufficient for the changes made?
*   **Security:**
    *   Are there any obvious security vulnerabilities (e.g., injection flaws, insecure handling of data/credentials, XSS)?
    *   Is input properly validated?
*   **Performance:**
    *   Are there any obvious performance bottlenecks or inefficient operations?
*   **Adherence to Standards:**
    *   Does the code follow the project's coding style, linting rules, and established best practices?
*   **Documentation:**
    *   Are code comments clear and sufficient where needed?
    *   Is any relevant user-facing or developer documentation (e.g., READMEs, API docs) updated?
*   **Non-Functional Requirements:**
    *   Are aspects like configuration, logging, and potential operational impact considered?

### Author Responsibilities
*   Clearly explain the changes in the PR/MR description.
*   Respond to review comments and engage in discussion.
*   Make necessary code revisions based on feedback.
*   Ensure all CI checks are passing before requesting a final review or merge.

By adhering to this code review process, we can collectively improve the quality and reliability of the Atom Agent codebase.
