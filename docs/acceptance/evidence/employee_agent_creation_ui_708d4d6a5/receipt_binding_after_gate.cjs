/*
 * After-gate for the receipt-binding repair.
 *
 * This is deliberately separate from the root's original 4-case probe: that
 * probe's minimal "valid" twin omits the nested verification.audit_id that
 * the actual backend always returns, so it is not a backend-shaped receipt.
 * This gate requires the exact backend shape and also covers already_applied.
 *
 * It loads the actual TypeScript module with the existing TypeScript compiler
 * and doubles only apiClient.post. No worker source is edited.
 */
const fs = require('fs');
const vm = require('vm');
const cp = require('child_process');

const wt = '/private/tmp/atom-goal14-create-ui-join-20261110';
const ts = require(wt + '/frontend-nextjs/node_modules/typescript/lib/typescript.js');
const source = fs.readFileSync(
  wt + '/frontend-nextjs/lib/agent-onboarding-api.ts', 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;

const op = 'agent:create:intent-1';
const exact = {
  operation_id: op,
  audit_id: op,
  verification: {
    status: 'verified',
    effect: 'committed',
    audit_id: op,
  },
};
const cases = [
  {
    name: 'invalid_wrong_operation',
    expect: 'reject',
    receipt: {
      operation_id: 'agent:create:other',
      audit_id: 'agent:create:other',
      verification: {
        status: 'verified', effect: 'committed',
        audit_id: 'agent:create:other',
      },
    },
  },
  {
    name: 'invalid_missing_receipt',
    expect: 'reject',
    receipt: {
      verification: {
        status: 'verified', effect: 'committed', audit_id: op,
      },
    },
  },
  {
    name: 'invalid_contradictory_effect',
    expect: 'reject',
    receipt: {
      operation_id: op,
      audit_id: op,
      verification: { status: 'verified', effect: 'none', audit_id: op },
    },
  },
  {
    name: 'invalid_missing_nested_audit',
    expect: 'reject',
    receipt: {
      operation_id: op,
      audit_id: op,
      verification: { status: 'verified', effect: 'committed' },
    },
  },
  {
    name: 'invalid_nested_audit_mismatch',
    expect: 'reject',
    receipt: {
      operation_id: op,
      audit_id: op,
      verification: {
        status: 'verified', effect: 'committed',
        audit_id: 'agent:create:other',
      },
    },
  },
  {
    name: 'actual_valid_verified',
    expect: 'accept',
    receipt: exact,
  },
  {
    name: 'actual_valid_already_applied',
    expect: 'accept',
    receipt: {
      ...exact,
      verification: {
        status: 'already_applied',
        effect: 'committed',
        audit_id: op,
        replay: 'do_not_repeat',
      },
    },
  },
];

(async () => {
  const results = [];
  for (const testCase of cases) {
    for (const kind of ['custom', 'guided']) {
      const exp = {};
      const ctx = {
        exports: exp,
        require: () => ({
          apiClient: {
            post: async () => ({
              status: 201,
              data: {
                success: true,
                data: {
                  agent_id: 'agent-returned',
                  name: 'Receipt Gate Agent',
                  category: 'Operations',
                  maturity: 'student',
                  created_by: 'employee',
                  ...testCase.receipt,
                },
              },
            }),
          },
        }),
        Date,
        Math,
      };
      vm.runInNewContext(js, ctx);
      try {
        if (kind === 'custom') {
          await exp.createCustomAgent(
            { name: 'Receipt Gate Agent', category: 'Operations' },
            { operationId: 'intent-1' }
          );
        } else {
          await exp.createGuidedAgent(
            'watch invoices and flag overdue ones', undefined,
            { operationId: 'intent-1' }
          );
        }
        results.push({
          case: testCase.name, kind, expected: testCase.expect,
          accepted: true, ok: testCase.expect === 'accept',
        });
      } catch (error) {
        results.push({
          case: testCase.name, kind, expected: testCase.expect,
          accepted: false, code: error.code || null,
          problem: error.receipt_problem || null,
          ok: testCase.expect === 'reject',
        });
      }
    }
  }
  const failing = results.filter((result) => !result.ok);
  const output = {
    gate: 'creation receipt binding after-gate',
    source_head: cp.execSync('git -C ' + wt + ' rev-parse HEAD', {
      encoding: 'utf8',
    }).trim(),
    source_dirty: cp.execSync(
      'git -C ' + wt + ' status --porcelain=v1 --untracked-files=all',
      { encoding: 'utf8' }).trim().split('\n').filter(Boolean),
    method: 'actual TypeScript module transpiled with existing TypeScript; '
      + 'only apiClient.post doubled; exact backend-shaped nested audit',
    required_operation: op,
    results,
    failing,
  };
  const out = wt + '/docs/acceptance/evidence/'
    + 'employee_agent_creation_ui_708d4d6a5/browser_custom_hire_join/'
    + 'receipt_binding_after_gate.json';
  fs.writeFileSync(out, JSON.stringify(output, null, 2) + '\n');
  console.log(JSON.stringify({
    source_head: output.source_head,
    failing: output.failing.length,
    results: results.map((r) => [
      r.case, r.kind, r.accepted, r.ok,
    ]),
  }, null, 2));
  process.exitCode = failing.length ? 1 : 0;
})();
