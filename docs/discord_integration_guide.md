# Discord Integration Guide

This guide provides instructions on how to set up and use the Discord integration in Atom.

## Prerequisites

- You must have an Atom account.
- You must have a Discord account.

## 1. Connect Your Discord Account

1.  Go to **Settings** > **Integrations**.
2.  You should see the **Discord** integration.
3.  Click the **Connect** button.
4.  You will be redirected to Discord to authorize the application.
5.  Once you have authorized the application, you will be redirected back to Atom.

Your Discord account is now connected.

## 2. Using the Discord Integration

You can now use the Discord integration to interact with your servers and channels.

### List Your Servers

You can list your servers using the `listDiscordGuilds` skill.

**Example:**

```
listDiscordGuilds()
```

### List Channels in a Server

You can list the channels in a server using the `listDiscordChannels` skill.

**Example:**

```
listDiscordChannels(guildId: "your_guild_id")
```

### Send a Message to a Channel

You can send a message to a channel using the `sendDiscordMessage` skill.

**Example:**

```
sendDiscordMessage(channelId: "your_channel_id", message: "Hello from Atom!")
```
