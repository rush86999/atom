# Atom Frontend - Next.js

This is a [Next.js](https://nextjs.org/) project for the Atom AI-powered business automation platform.

## ⚠️ Security Notice

**NEVER commit sensitive files to version control:**

- `.claude/` - Claude Code API keys and configuration
- `.env.local` - Environment variables with secrets
- `.env*` - Any environment files containing API keys
- `*.pem`, `*.key` - TLS certificates and private keys
- `**/credentials.json` - OAuth credentials, API keys

These files are in `.gitignore`. Always verify with `git status` before committing.

**See:** [CONTRIBUTING.md](../CONTRIBUTING.md#security-guidelines) for complete security guidelines.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `pages/index.tsx`. The page auto-updates as you edit the file.

[API routes](https://nextjs.org/docs/api-routes/introduction) can be accessed on [http://localhost:3000/api/hello](http://localhost:3000/api/hello). This endpoint can be edited in `pages/api/hello.ts`.

The `pages/api` directory is mapped to `/api/*`. Files in this directory are treated as [API routes](https://nextjs.org/docs/api-routes/introduction) instead of React pages.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js/) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_mediup=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/deployment) for more details.
# atomic-app
