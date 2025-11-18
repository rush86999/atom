# DEEPSEEK Integration Guide

This file contains corrected examples and troubleshooting steps for using the DeepSeek Chat Completions API from Node.js (server) and from a Next.js front-end.

Important: Never commit real secret keys into source control. Keep them in `.env` / `.env.local` and add those files to `.gitignore`.

1. Server-side Node.js (recommended)

- Install `dotenv` (if you haven't):

  npm install dotenv axios

- In your server entry (CommonJS):

  // server.js or index.js
  require('dotenv').config(); // loads .env/.env.local
  const axios = require('axios');

  async function sendChat() {
  const res = await axios.post(
  'https://api.deepseek.com/v1/chat/completions',
  {
  model: 'deepseek-chat',
  messages: [{ role: 'user', content: 'Hello!' }]
  },
  {
  headers: {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${process.env.DEEPSEEK_API_KEY}`
  }
  }
  );
  console.log(res.data);
  }

- For ESM (package.json "type": "module"):

  import 'dotenv/config';
  import axios from 'axios';

  // same axios.post call above, using process.env.DEEPSEEK_API_KEY

2. Next.js / Frontend (client) — CAUTION

- You should NOT expose secret API keys on the client. If a request must be made from the browser, create a server-side API route (or proxy) that holds the secret and forwards requests to DeepSeek. Example below shows both approaches:

- Server-side API route (recommended): `pages/api/deepseek.js` or `app/api/deepseek/route.js`

  // pages/api/deepseek.js (Next.js API route, Node environment)
  import axios from 'axios';
  import 'dotenv/config';

  export default async function handler(req, res) {
  try {
  const response = await axios.post(
  'https://api.deepseek.com/v1/chat/completions',
  {
  model: 'deepseek-chat',
  messages: [{ role: 'user', content: req.body?.message || 'Hello!' }]
  },
  {
  headers: {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${process.env.DEEPSEEK_API_KEY}`
  }
  }
  );
  res.status(200).json(response.data);
  } catch (err) {
  res.status(err.response?.status || 500).json({ error: err.message });
  }
  }

- Client fetch (browser) → call your API route instead of DeepSeek directly:

  await fetch('/api/deepseek', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Hello!' })
  });

- If you absolutely must use a public key (not recommended), prefix env name with `NEXT_PUBLIC_` and note it's exposed to the client. Prefer server-only secrets.

3. Common mistakes that cause 401 or auth errors

- Wrong header name: Use `Authorization: Bearer <API_KEY>`
- Using `apiKey` or other formats instead of Bearer
- Expired token: regenerate from DeepSeek dashboard
- Forgot to load .env: add `require('dotenv').config()` (or `import 'dotenv/config'`)
- Wrong endpoint: ensure `/v1/chat/completions`

4. Check environment variable loaded

- macOS / Linux (bash/zsh):

  echo $DEEPSEEK_API_KEY

- Windows PowerShell (your environment):

  echo $env:DEEPSEEK_API_KEY

If the command prints empty, the key is not loaded in the current shell.

5. Restart server after adding `.env` or `.env.local`

- Development server (Node/Express):

  npm run dev

  # or

  node server.js

- Next.js

  npm run dev

6. Quick troubleshooting checklist

- Confirm `DEEPSEEK_API_KEY` exists in `.env`/.env.local and is correct.
- Ensure `require('dotenv').config()` is executed before accessing `process.env`.
- Keep keys out of client code; use server API routes.
- Test call with `curl` or Postman using `Authorization: Bearer <KEY>` to isolate app vs key issues.

7. Minimal curl example

curl -X POST https://api.deepseek.com/v1/chat/completions \
 -H "Content-Type: application/json" \
 -H "Authorization: Bearer <YOUR_KEY>" \
 -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"Hello!"}]}'

If you want, I can:

- Add a server-side example file to your repo that calls DeepSeek.
- Add a Next.js API route file to `src/` or `pages/api/` and wire a small frontend demo.

Tell me which of the above you'd like next.
