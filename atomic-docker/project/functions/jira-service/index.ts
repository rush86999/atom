import express from 'express';
import { Request, Response } from 'express';
import { Version2Client } from 'jira.js';
import { getJiraAccessToken } from '../../skills/jiraSkills'; // Assuming this function will be created

const router = express.Router();

// Middleware to get the user's access token and create a Jira client
const jiraClientMiddleware = async (req: Request, res: Response, next: Function) => {
    const userId = (req as any).user.sub;
    if (!userId) {
        return res.status(401).send('Unauthorized: User ID not found.');
    }

    try {
        const accessToken = await getJiraAccessToken(userId);
        if (!accessToken) {
            return res.status(403).send('Forbidden: Jira access token not found.');
        }

        const client = new Version2Client({
            host: 'https://your-domain.atlassian.net', // This needs to be configured
            authentication: {
                oauth2: {
                    accessToken,
                },
            },
        });

        (req as any).jiraClient = client;
        next();
    } catch (error) {
        console.error('Error creating Jira client:', error);
        res.status(500).send('Internal Server Error');
    }
};

router.use(jiraClientMiddleware);

// Route to get the list of projects
router.get('/projects', async (req, res) => {
    try {
        const client = (req as any).jiraClient;
        const projects = await client.projects.getAllProjects();
        res.json(projects);
    } catch (error) {
        console.error('Error getting projects:', error);
        res.status(500).send('Internal Server Error');
    }
});

// Route to get the issues in a project
router.get('/issues/:projectId', async (req, res) => {
    try {
        const client = (req as any).jiraClient;
        const issues = await client.issueSearch.searchForIssuesUsingJql({
            jql: `project = ${req.params.projectId}`,
        });
        res.json(issues);
    } catch (error) {
        console.error('Error getting issues:', error);
        res.status(500).send('Internal Server Error');
    }
});

// Route to create a new issue
router.post('/issues', async (req, res) => {
    try {
        const client = (req as any).jiraClient;
        const newIssue = await client.issues.createIssue(req.body);
        res.json(newIssue);
    } catch (error) {
        console.error('Error creating issue:', error);
        res.status(500).send('Internal Server Error');
    }
});

export default router;
