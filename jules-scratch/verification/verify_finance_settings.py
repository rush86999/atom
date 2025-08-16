from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Navigate to the settings page
    page.goto("http://localhost:3000/Settings")

    # Click on the "Transaction Rules" link
    page.get_by_role("link", name="Transaction Rules").click()
    page.wait_for_url("**/Settings/TransactionRules")
    page.screenshot(path="jules-scratch/verification/transaction_rules.png")

    # Navigate back to the settings page
    page.goto("http://localhost:3000/Settings")

    # Click on the "Budget Alert Settings" link
    page.get_by_role("link", name="Budget Alert Settings").click()
    page.wait_for_url("**/Settings/BudgetAlerts")
    page.screenshot(path="jules-scratch/verification/budget_alerts.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
