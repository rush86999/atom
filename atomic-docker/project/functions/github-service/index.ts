import express from 'express';
import { Request, Response } from 'express';
import { Octokit } from '@octokit/rest';
import { AuthorizationCode } from 'simple-oauth2';
import { saveGitHubToken, getGitHubToken, deleteGitHubToken } from '../_utils/dbService';
import { getUserRoles } from '../_utils/userService';

const router = express.Router();

// Middleware to check for 'developer' role
const checkDeveloperRole = async (req: Request, res: Response, next: Function) => {
  const userId = (req as any).user.sub;
  if (!userId) {
    return res.status(401).send('Unauthorized: User ID not found.');
  }

  try {
    const roles = await getUserRoles(userId);
    if (roles.includes('developer')) {
      next();
    } else {
      res.status(403).send('Forbidden: Developer role required.');
    }
  } catch (error) {
    console.error('Error checking user role:', error);
    res.status(500).send('Internal Server Error');
  }
};

// Apply the middleware to all routes in this router
router.use(checkDeveloperRole);

// GitHub OAuth2 configuration
const githubOAuth2 = new AuthorizationCode({
  client: {
    id: process.env.GITHUB_CLIENT_ID || '',
    secret: process.env.GITHUB_CLIENT_SECRET || '',
  },
  auth: {
    tokenHost: 'https://github.com',
    tokenPath: '/login/oauth/access_token',
    authorizePath: '/login/oauth/authorize',
  },
});

// Route to get the GitHub OAuth URL
router.get('/auth/url', (req, res) => {
  const authorizationUri = githubOAuth2.authorizeURL({
    redirect_uri: process.env.GITHUB_REDIRECT_URI || '',
    scope: 'repo,user', // specify the scopes you need
  });
  res.redirect(authorizationUri);
});

// Route to handle the GitHub OAuth callback
router.get('/auth/callback', async (req, res) => {
    const { code } = req.query;
    if (!code) {
        return res.status(400).send('Bad Request: Missing code');
    }

    const options = {
        code: code as string,
        redirect_uri: process.env.GITHUB_REDIRECT_URI || '',
    };

    try {
        const result = await githubOAuth2.getToken(options);
        const token = result.token.access_token as string;

        const octokit = new Octokit({ auth: token });
        const { data: user } = await octokit.users.getAuthenticated();

        const userId = (req as any).user.sub;
        await saveGitHubToken({
            userId,
            githubUserId: user.id.toString(),
            githubUsername: user.login,
            accessToken: token,
            scopes: 'repo,user',
        });

        res.send('GitHub authentication successful!');
    } catch (error) {
        console.error('Access Token Error', error.message);
        res.status(500).json('Authentication failed');
    }
});

// Route to check the GitHub connection status
router.get('/status', async (req, res) => {
    try {
        const userId = (req as any).user.sub;
        const token = await getGitHubToken(userId);
        if (token) {
            res.json({ connected: true, username: token.githubUsername });
        } else {
            res.json({ connected: false });
        }
    } catch (error) {
        console.error('Error getting GitHub status:', error);
        res.status(500).send('Internal Server Error');
    }
});

// Route to disconnect the GitHub account
router.post('/disconnect', async (req, res) => {
    try {
        const userId = (req as any).user.sub;
        await deleteGitHubToken(userId);
        res.send('GitHub account disconnected.');
    } catch (error) {
        console.error('Error disconnecting GitHub account:', error);
        res.status(500).send('Internal Server Error');
    }
});

export default router;
