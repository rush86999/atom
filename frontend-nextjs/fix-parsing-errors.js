#!/usr/bin/env node
'use strict';

const message = 'fix-parsing-errors.js is obsolete; run npx eslint instead.';

function main() {
  process.stdout.write(`${message}\n`);
}

if (require.main === module) {
  main();
}

module.exports = { main, message };
