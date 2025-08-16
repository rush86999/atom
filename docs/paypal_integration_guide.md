# PayPal Integration Guide

This guide provides instructions on how to set up and use the PayPal integration in Atom.

## Prerequisites

- You must have an Atom account.
- You must have a PayPal Business account.

## 1. Connect Your PayPal Account

1.  Go to **Settings** > **Integrations**.
2.  You should see the **PayPal** integration.
3.  Click the **Connect** button.
4.  This will trigger the `client_credentials` flow on the backend to get an access token.

Your PayPal account is now connected.

## 2. Using the PayPal Integration

You can now use the PayPal integration to interact with your payments and transactions.

### Get Your Balance

You can get your PayPal balance using the `getPaypalBalance` skill.

**Example:**

```
getPaypalBalance()
```

### List Your Transactions

You can list your recent transactions using the `listPaypalTransactions` skill.

**Example:**

```
listPaypalTransactions()
```
