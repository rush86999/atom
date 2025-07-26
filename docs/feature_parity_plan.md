### **Plan to Implement Feature Parity with `maybe-finance/maybe`**

**Objective:** To integrate the core personal finance features of the "Maybe" application into Atom, providing users with a comprehensive, self-hostable platform for tracking net worth, investments, and budgets. This plan will leverage Atom's existing infrastructure, including Plaid integration and financial services.

**Phase 1: In-Depth Analysis and Scoping**

1.  **Full Feature Audit of "Maybe":**
    *   Action: Thoroughly review the "Maybe" codebase, UI, and documentation to create a detailed feature matrix.
    *   Key Areas:
        *   Account Aggregation (Plaid, etc.)
        *   Investment Tracking (Securities, performance, allocation)
        *   Net Worth Calculation and History
        *   Budgeting and Expense Categorization
        *   Financial Goal Setting and Tracking
        *   Reporting and Visualization Dashboards
        *   Manual Account and Transaction Management

2.  **Data Model Gap Analysis:**
    *   Action: Compare the "Maybe" database schema (`schema.rb`) with Atom's existing financial tables (`0011-create-accounts-table.sql`, etc.).
    *   Goal: Identify missing tables and fields required to support all "Maybe" features. This includes schemas for budgets, goals, investment asset classes, and historical net worth snapshots.

3.  **API and Service Design:**
    *   Action: Define the required API endpoints and backend service logic.
    *   Focus: Design how the frontend will interact with the Python backend for all new financial features, building upon existing services like `financial_handler.py` and `plaid_service.py`.

**Phase 2: Backend Development**

1.  **Extend Database Schemas:**
    *   Action: Write and apply new SQL migration scripts to create the tables and fields identified in the gap analysis.

2.  **Enhance Plaid Integration:**
    *   Action: Expand `plaid_service.py` to fetch and process all necessary data types, including investment holdings, security details, and liabilities. Ensure robust error handling and data synchronization.

3.  **Develop Core Financial Logic:**
    *   Action: Implement or enhance the Python services for:
        *   **Net Worth Service:** Calculate current and historical net worth.
        *   **Investment Service:** Track investment performance, including returns and allocation.
        *   **Transaction Service:** Add support for categorization, splitting, and rule-based automation.
        *   **Budgeting Service (New):** Create and manage budgets, and track spending against categories.

4.  **Build APIs for Manual Management:**
    *   Action: Create endpoints for users to manually add, edit, and delete accounts, holdings, and transactions.

**Phase 3: Frontend Development**

1.  **Develop Core UI Components:**
    *   Action: Using the existing React components in `atomic-docker/app_build_docker/components` as a foundation, build new components for all major financial features.

2.  **Implement Feature Pages:**
    *   Action: Create the primary pages for the finance module, mirroring the structure in `desktop/tauri/src/Finance.tsx` and `atomic-docker/app_build_docker/pages/Finance/index.tsx`.
    *   Pages:
        *   **Dashboard/Overview:** A central view of net worth, recent transactions, and budget status.
        *   **Investments:** A detailed portfolio view with holdings and performance charts.
        *   **Transactions:** An interactive table for viewing and managing all transactions.
        *   **Budgeting:** A dedicated section for creating and monitoring budgets.
        *   **Account Management:** An enhanced settings page to manage linked and manual accounts.

3.  **Integrate Frontend with Backend:**
    *   Action: Connect all frontend components to the new backend APIs, ensuring seamless data flow and a responsive user experience. Utilize the `financeContext.tsx` for state management.

**Phase 4: Testing and Documentation**

1.  **End-to-End Testing:**
    *   Action: Develop a comprehensive test suite covering the entire financial feature set.
    *   Examples:
        *   Link a bank account and verify that net worth is updated correctly.
        *   Add a manual transaction and see it reflected in the budget.
        *   Test investment performance calculations against a known benchmark.

2.  **Create User Documentation:**
    *   Action: Write clear, concise guides for users on how to use the new financial features.

3.  **Update Technical Documentation:**
    *   Action: Document the new API endpoints, database schemas, and service architecture in the `docs/` directory.
