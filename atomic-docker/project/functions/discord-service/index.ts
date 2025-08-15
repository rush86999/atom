import express from 'express';
import { Request, Response } from 'express';
import { Client, GatewayIntentBits } from 'discord.js';
import { getDiscordAccessToken } from '../../skills/discordSkills'; // Assuming this function will be created

const router = express.Router();

// Middleware to get the user's access token and create a Discord client
const discordClientMiddleware = async (req: Request, res: Response, next: Function) => {
    const userId = (req as any).user.sub;
    if (!userId) {
        return res.status(401).send('Unauthorized: User ID not found.');
    }

    try {
        const accessToken = await getDiscordAccessToken(userId);
        if (!accessToken) {
            return res.status(403).send('Forbidden: Discord access token not found.');
        }

        const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent] });
        await client.login(accessToken);

        (req as any).discordClient = client;
        next();
    } catch (error) {
        console.error('Error creating Discord client:', error);
        res.status(500).send('Internal Server Error');
    }
};

router.use(discordClientMiddleware);

// Route to get the list of guilds the user is in
router.get('/guilds', async (req, res) => {
    try {
        const client = (req as any).discordClient;
        const guilds = await client.guilds.fetch();
        res.json(guilds);
    } catch (error) {
        console.error('Error getting guilds:', error);
        res.status(500).send('Internal Server Error');
    }
});

// Route to get the list of channels in a guild
router.get('/channels/:guildId', async (req, res) => {
    try {
        const client = (req as any).discordClient;
        const guild = await client.guilds.fetch(req.params.guildId);
        const channels = await guild.channels.fetch();
        res.json(channels);
    } catch (error) {
        console.error('Error getting channels:', error);
        res.status(500).send('Internal Server Error');
    }
});

// Route to get the messages from a channel
router.get('/messages/:channelId', async (req, res) => {
    try {
        const client = (req as any).discordClient;
        const channel = await client.channels.fetch(req.params.channelId);
        if (channel.isTextBased()) {
            const messages = await channel.messages.fetch({ limit: 50 });
            res.json(messages);
        } else {
            res.status(400).send('Bad Request: Not a text channel.');
        }
    } catch (error) {
        console.error('Error getting messages:', error);
        res.status(500).send('Internal Server Error');
    }
});

export default router;
