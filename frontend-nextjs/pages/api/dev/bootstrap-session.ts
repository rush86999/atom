import fs from 'fs';
import path from 'path';
import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_BASE = process.env.PYTHON_BACKEND_URL || 'http://127.0.0.1:8000';
const DEV_EMAIL = process.env.NEXT_PUBLIC_DEV_BOOTSTRAP_EMAIL || 'admin@example.com';

function readBootstrapPassword(): string | null {
  const candidates = [
    path.resolve(process.cwd(), '..', 'backend', 'logs', 'bootstrap_admin_password.txt'),
    path.resolve(process.cwd(), '..', 'backend', 'bootstrap_admin_password.txt'),
  ];

  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) {
        const value = fs.readFileSync(candidate, 'utf-8').trim();
        if (value) return value;
      }
    } catch {
      // Try next candidate.
    }
  }

  return null;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (process.env.NODE_ENV === 'production') {
    return res.status(404).json({ error: 'not_found' });
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'method_not_allowed' });
  }

  const password = readBootstrapPassword();
  if (!password) {
    return res.status(404).json({ error: 'bootstrap_password_not_found' });
  }

  try {
    const response = await fetch(`${BACKEND_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: DEV_EMAIL, password }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data?.access_token) {
      return res.status(401).json({
        error: 'bootstrap_login_failed',
        detail: data?.detail || 'Could not authenticate the bootstrap user',
      });
    }

    return res.status(200).json({
      access_token: data.access_token,
      email: DEV_EMAIL,
    });
  } catch (error: any) {
    return res.status(500).json({
      error: 'bootstrap_login_error',
      detail: error?.message || 'Unexpected error',
    });
  }
}
