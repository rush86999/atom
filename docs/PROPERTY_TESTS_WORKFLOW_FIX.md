# Property-Based Tests Workflow - Fix Required

## Issue

The Property-Based Tests workflow in [atom-saas](https://github.com/rush86999/atom-saas) repository is failing.

## Root Cause Analysis

The workflow file `.github/workflows/property-tests.yml` has YAML syntax errors:

1. **Incorrect action references**:
   - `actions/checkoutv4` should be `actions/checkout@v4`
   - `actions/setup-node@v4` typo in indentation

2. **Typo in workflow configuration**:
   - `node-versiol: '18'` should be `node-version: '18'`

3. **Indentation issues** with quote characters causing parsing errors

## Fixed Workflow

```yaml
name: Property-Based Tests
on:
  pull_request:
    branches: [main]

jobs:
  property-tests:
    name: Property-Based Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'

      - name: Install main dependencies
        run: npm ci
        working-directory: ./

      - name: Install property test dependencies
        run: npm ci
        working-directory: ./property-tests

      - name: Validate contracts
        run: npm run validate:contracts
        working-directory: ./property-tests

      - name: Check for forbidden imports
        run: npm run check:imports
        working-directory: ./property-tests

      - name: Run property tests
        run: npm test
        working-directory: ./property-tests

      - name: Generate coverage report
        run: npm run test:coverage
        working-directory: ./property-tests
        continue-on-error: true

      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          files: ./property-tests/coverage/lcov.info
          flags: property-tests
          name: property-tests-coverage
```

## Changes Made

1. ✅ Fixed action references: `checkoutv4` → `checkout@v4`
2. ✅ Fixed typo: `node-versiol` → `node-version`
3. ✅ Fixed indentation and syntax
4. ✅ Updated to codecov-action@v3 (latest stable)

## How to Apply Fix

1. Open `.github/workflows/property-tests.yml` in the atom-saas repository
2. Replace entire file with fixed version above
3. Commit and push to main branch

## Verification

After applying the fix, the workflow should:
- ✅ Checkout code successfully
- ✅ Setup Node.js 18
- ✅ Install dependencies
- ✅ Run property tests
- ✅ Generate coverage reports
- ✅ Upload to Codecov

---

**Generated**: 2026-02-23
**Related**: Phase 74 - Quality Gates & Property Testing
