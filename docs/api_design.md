# API Design for Autonomous Personal Finance System

This document outlines the design for the backend API that will power the finance features.

## 1. Transaction Management

Handles all operations related to financial transactions and their categorization rules.

### 1.1. Transactions API

**Endpoints for managing individual transactions.**

#### `POST /api/financial/transactions`

*   **Description:** Creates a new transaction.
*   **Auth:** Required.
*   **Request Body:**
    ```json
    {
      "user_id": "string",
      "account_id": "integer",
      "amount": "number",
      "description": "string",
      "date": "string (YYYY-MM-DD)",
      "category": "string (optional)"
    }
    ```
*   **Response (201 Created):** The newly created transaction object.
*   **Side Effect:** After creation, the transaction is processed by the autonomous categorization engine.

#### `POST /api/financial/transactions/search`

*   **Description:** Retrieves a list of transactions based on specified filters.
*   **Auth:** Required.
*   **Request Body:** (Matches the Zod schema in `financeAgentService.ts`)
    ```json
    {
      "userId": "string",
      "query": "string (optional)",
      "category": "string (optional)",
      "amountRange": { "min": "number", "max": "number" },
      "dateRange": { "start": "string (YYYY-MM-DD)", "end": "string (YYYY-MM-DD)" },
      "limit": "integer (optional, default: 50)"
    }
    ```
*   **Response (200 OK):**
    ```json
    {
      "transactions": [
        {
          "id": "integer",
          "description": "string",
          "amount": "number",
          "date": "string",
          "category": "string"
        }
      ]
    }
    ```

#### `PUT /api/financial/transactions/{id}`

*   **Description:** Updates an existing transaction.
*   **Auth:** Required.
*   **Request Body:** A JSON object with the fields to update.
*   **Response (200 OK):** The updated transaction object.

#### `DELETE /api/financial/transactions/{id}`

*   **Description:** Deletes a transaction by its ID.
*   **Auth:** Required.
*   **Response (204 No Content):**

---

### 1.2. Transaction Rules API

**Endpoints for managing autonomous categorization rules.**

#### `POST /api/financial/rules`

*   **Description:** Creates a new transaction categorization rule.
*   **Auth:** Required.
*   **Request Body:**
    ```json
    {
      "userId": "string",
      "rule_name": "string",
      "pattern": "string",
      "pattern_type": "string (e.g., 'contains', 'exact', 'regex')",
      "action": "string (e.g., 'categorize')",
      "target_value": "string (e.g., the category to assign)"
    }
    ```
*   **Response (201 Created):** The newly created rule object.

#### `GET /api/financial/rules`

*   **Description:** Retrieves all rules for a user.
*   **Auth:** Required.
*   **Query Parameters:** `userId=string`
*   **Response (200 OK):** An array of rule objects.

#### `PUT /api/financial/rules/{id}`

*   **Description:** Updates an existing rule.
*   **Auth:** Required.
*   **Request Body:** A JSON object with the fields to update.
*   **Response (200 OK):** The updated rule object.

#### `DELETE /api/financial/rules/{id}`

*   **Description:** Deletes a rule by its ID.
*   **Auth:** Required.
*   **Response (204 No Content):**

---

## 2. Budgeting

Handles the creation and management of budgets.

### `POST /api/financial/budgets`

*   **Description:** Creates a new budget for a category.
*   **Auth:** Required.
*   **Request Body:**
    ```json
    {
      "user_id": "string",
      "name": "string",
      "category": "string",
      "amount": "number",
      "period_type": "string (e.g., 'monthly', 'yearly')",
      "start_date": "string (YYYY-MM-DD)"
    }
    ```
*   **Response (201 Created):** The newly created budget object.

### `GET /api/financial/budgets`

*   **Description:** Retrieves all budgets for a user.
*   **Auth:** Required.
*   **Query Parameters:** `userId=string`
*   **Response (200 OK):** An array of budget objects.

### `GET /api/financial/budgets/summary`

*   **Description:** Retrieves a summary of spending versus budget for a given period.
*   **Auth:** Required.
*   **Query Parameters:** `userId=string`, `period=string`
*   **Response (200 OK):** A budget summary object, as defined in `financeAgentService.ts`.

### `PUT /api/financial/budgets/{id}`

*   **Description:** Updates an existing budget.
*   **Auth:** Required.
*   **Request Body:** A JSON object with the fields to update.
*   **Response (200 OK):** The updated budget object.

### `DELETE /api/financial/budgets/{id}`

*   **Description:** Deletes a budget by its ID.
*   **Auth:** Required.
*   **Response (204 No Content):**

---

## 3. Financial Goals

Handles the creation and management of financial goals.

### `POST /api/financial/goals`

*   **Description:** Creates a new financial goal.
*   **Auth:** Required.
*   **Request Body:**
    ```json
    {
      "user_id": "string",
      "title": "string",
      "target_amount": "number",
      "goal_type": "string (e.g., 'savings', 'debt_payoff')",
      "target_date": "string (YYYY-MM-DD, optional)"
    }
    ```
*   **Response (201 Created):** The newly created goal object.

### `GET /api/financial/goals`

*   **Description:** Retrieves all financial goals for a user.
*   **Auth:** Required.
*   **Query Parameters:** `userId=string`
*   **Response (200 OK):** An array of financial goal objects.

### `PUT /api/financial/goals/{id}`

*   **Description:** Updates a financial goal (e.g., to add a contribution).
*   **Auth:** Required.
*   **Request Body:** A JSON object with the fields to update.
*   **Response (200 OK):** The updated goal object.

### `DELETE /api/financial/goals/{id}`

*   **Description:** Deletes a financial goal by its ID.
*   **Auth:** Required.
*   **Response (204 No Content):**

---

## 4. Net Worth & Investments

Handles aggregating and summarizing net worth and investment data.

### `GET /api/financial/net-worth/summary`

*   **Description:** Retrieves a summary of the user's current net worth and historical data.
*   **Auth:** Required.
*   **Query Parameters:** `userId=string`, `includeHistory=boolean` (optional)
*   **Response (200 OK):** A net worth summary object, as defined in `financeAgentService.ts`.

### `POST /api/financial/net-worth/snapshots`

*   **Description:** Manually triggers the creation of a new net worth snapshot. Can also be used by a scheduled job.
*   **Auth:** Required.
*   **Request Body:**
    ```json
    {
      "user_id": "string"
    }
    ```
*   **Response (201 Created):** The newly created snapshot object.

### `GET /api/financial/investments/summary`

*   **Description:** Retrieves a summary of the user's investment portfolio.
*   **Auth:** Required.
*   **Query Parameters:** `userId=string`
*   **Response (200 OK):** An investment summary object, as defined in `financeAgentService.ts`.

---

## 5. NLU Agent Expansion

To support natural language control, the `FinanceAgent` will be expanded to recognize the following intents and entities.

### New Intents

*   `create_budget`
*   `list_budgets`
*   `get_budget_summary`
*   `create_financial_goal`
*   `list_financial_goals`
*   `get_net_worth`
*   `get_investment_summary`
*   `add_transaction`
*   `search_transactions`

### Example Utterances & Entity Extraction

*   **"Create a monthly budget of $500 for groceries."**
    *   **Intent:** `create_budget`
    *   **Entities:** `period: "monthly"`, `amount: 500`, `category: "groceries"`
*   **"Show me my budgets."**
    *   **Intent:** `list_budgets`
*   **"How am I doing on my budgets this month?"**
    *   **Intent:** `get_budget_summary`
    *   **Entities:** `period: "this month"`
*   **"I want to save $10,000 for a down payment by next year."**
    *   **Intent:** `create_financial_goal`
    *   **Entities:** `amount: 10000`, `name: "down payment"`, `target_date: "next year"`
*   **"What's my net worth?"**
    *   **Intent:** `get_net_worth`
*   **"Add a transaction of $25 for lunch at Sweetgreen."**
    *   **Intent:** `add_transaction`
    *   **Entities:** `amount: 25`, `category: "lunch"`, `description: "Sweetgreen"`
*   **"Find all my transactions over $100 in the last week."**
    *   **Intent:** `search_transactions`
    *   **Entities:** `amount_min: 100`, `period: "last week"`
