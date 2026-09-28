/**
 * Preview-instance config wrapper.
 *
 * WHY THIS FILE EXISTS
 * The repo's real `frontend-nextjs/next.config.js` is shared and actively
 * used by the user's own dev server (and by other agents). Next 16 sets
 * `experimental.lockDistDir: true` by default and takes an exclusive lock at
 * `<distDir>/dev/lock`, so a second `next dev` in the same project directory
 * exits(1) with "Another next dev server is already running". Editing the
 * shared config to unlock it would disturb the running instance and every
 * other agent, which the readiness plan explicitly forbids
 * ("Do not restart or replace the user's usual environment").
 *
 * Next hardcodes the config file name (`configFileName = 'next.config.js'` in
 * next/dist/server/config.js) with no env override, so a second instance
 * needs its own project directory. This directory is a symlink farm over the
 * real sources: every top-level entry except `.next`, `node_modules`,
 * `next.config.js` and `.env.local` is a symlink, so source edits by any
 * agent are visible here immediately and nothing is duplicated.
 *
 * The ONLY behavioural override is `distDir`, which gives this instance its
 * own build directory and therefore its own lock. Everything else is the
 * repo's real config, required and spread verbatim, so the preview exercises
 * the same rewrites/env/env-contract as production.
 */
const path = require('path');
const realConfig = require('../next.config.js');

module.exports = {
  ...realConfig,
  distDir: '.next-preview',
  // Surface the resolved backend origin in the dev overlay/log so an
  // operator can confirm at a glance which world this instance targets.
  env: {
    ...(realConfig.env || {}),
    ATOM_PREVIEW_INSTANCE: '1',
  },
};
