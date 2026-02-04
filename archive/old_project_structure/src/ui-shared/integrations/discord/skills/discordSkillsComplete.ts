/**
 * Discord Integration Skills
 * Complete Discord integration with comprehensive server management and bot capabilities
 */

export interface DiscordSkillConfig {
  accessToken?: string;
  botToken?: string;
  clientId?: string;
  clientSecret?: string;
  baseUrl?: string;
  userAgent?: string;
}

export interface DiscordUser {
  id: string;
  username: string;
  discriminator: string;
  globalName: string;
  displayName: string;
  avatarHash: string;
  avatarUrl: string;
  bannerHash: string;
  bannerUrl: string;
  bot: boolean;
  system: boolean;
  mfaEnabled: boolean;
  accentColor: number;
  locale: string;
  email: string;
  verified: boolean;
  flags: number;
  premiumType: number;
  publicFlags: number;
}

export interface DiscordGuild {
  id: string;
  name: string;
  iconHash: string;
  iconUrl: string;
  splashHash: string;
  bannerHash: string;
  bannerUrl: string;
  ownerId: string;
  owner: any;
  permissions: string;
  region: string;
  afkChannelId: string;
  afkTimeout: number;
  widgetEnabled: boolean;
  widgetChannelId: string;
  verificationLevel: number;
  defaultMessageNotifications: number;
  explicitContentFilter: number;
  mfaLevel: number;
  applicationId: string;
  systemChannelId: string;
  systemChannelFlags: number;
  rulesChannelId: string;
  joinedAt: string;
  large: boolean;
  unavailable: boolean;
  memberCount: number;
  presenceCount: number;
  maxMembers: number;
  maxPresences: number;
  description: string;
  premiumTier: number;
  premiumSubscriptionCount: number;
  vanityUrlCode: string;
  preferredLocale: string;
  publicUpdatesChannelId: string;
  approximateMemberCount: number;
  approximatePresenceCount: number;
  features: string[];
  channels: DiscordChannel[];
  roles: DiscordRole[];
  emojis: any[];
}

export interface DiscordChannel {
  id: string;
  type: number;
  typeName: string;
  guildId: string;
  position: number;
  permissionOverwrites: any[];
  name: string;
  topic: string;
  nsfw: boolean;
  lastMessageId: string;
  bitrate: number;
  userLimit: number;
  rateLimitPerUser: number;
  recipients: any[];
  iconHash: string;
  ownerId: string;
  applicationId: string;
  parentId: string;
  lastPinTimestamp: string;
  rtcRegion: string;
  videoQualityMode: number;
  messageCount: number;
  memberCount: number;
  defaultAutoArchiveDuration: number;
  permissions: string;
  flags: number;
}

export interface DiscordMessage {
  id: string;
  channelId: string;
  guildId: string;
  author: {
    id: string;
    username: string;
    discriminator: string;
    displayName: string;
    avatarHash: string;
    avatarUrl: string;
    bot: boolean;
  };
  member: any;
  content: string;
  timestamp: string;
  editedTimestamp: string;
  tts: boolean;
  mentionEveryone: boolean;
  mentions: any[];
  mentionRoles: string[];
  mentionChannels: any[];
  attachments: any[];
  embeds: any[];
  reactions: any[];
  nonce: string;
  pinned: boolean;
  webhookId: string;
  type: number;
  activity: any;
  application: any;
  applicationId: string;
  messageReference: any;
  flags: number;
  stickers: any[];
  referencedMessage: any;
  components: any[];
}

export interface DiscordRole {
  id: string;
  name: string;
  color: number;
  colorHex: string;
  hoist: boolean;
  position: number;
  managed: boolean;
  mentionable: boolean;
  iconHash: string;
  unicodeEmoji: string;
  permissions: string;
  flags: number;
}

export interface DiscordBot {
  id: string;
  username: string;
  discriminator: string;
  avatarHash: string;
  avatarUrl: string;
  code: string;
  redirectUris: string[];
  applications: any[];
}

export interface DiscordWebhook {
  id: string;
  type: number;
  guildId: string;
  channelId: string;
  user: DiscordUser;
  name: string;
  avatarHash: string;
  token: string;
  applicationId: string;
  sourceGuild: any;
  sourceChannel: any;
  url: string;
}

/**
 * Discord Skills Registry - Complete set of Discord integration capabilities
 */
export const discordSkills = {
  
  /**
   * Get current Discord user information
   */
  discordGetUser: {
    id: 'discordGetUser',
    name: 'Get Discord User',
    description: 'Get current authenticated Discord user information',
    category: 'user-management',
    icon: '👤',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        }
      },
      required: ['user_id']
    }
  },

  /**
   * List Discord guilds (servers)
   */
  discordListGuilds: {
    id: 'discordListGuilds',
    name: 'List Discord Guilds',
    description: 'List guilds (servers) accessible to the authenticated user',
    category: 'server-management',
    icon: '🏰',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        limit: {
          type: 'number',
          description: 'Maximum number of guilds to return (default: 100, max: 200)',
          default: 100,
          minimum: 1,
          maximum: 200
        },
        before: {
          type: 'string',
          description: 'Get guilds before this guild ID',
          minLength: 17
        },
        after: {
          type: 'string',
          description: 'Get guilds after this guild ID',
          minLength: 17
        }
      },
      required: ['user_id']
    }
  },

  /**
   * Get Discord guild information
   */
  discordGetGuild: {
    id: 'discordGetGuild',
    name: 'Get Guild Info',
    description: 'Get detailed information about a Discord guild (server)',
    category: 'server-management',
    icon: '🏰',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        guild_id: {
          type: 'string',
          description: 'Guild ID (required)',
          minLength: 17
        }
      },
      required: ['user_id', 'guild_id']
    }
  },

  /**
   * List Discord channels in a guild
   */
  discordListChannels: {
    id: 'discordListChannels',
    name: 'List Guild Channels',
    description: 'List channels in a Discord guild (server)',
    category: 'channel-management',
    icon: '📺',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        guild_id: {
          type: 'string',
          description: 'Guild ID (required)',
          minLength: 17
        }
      },
      required: ['user_id', 'guild_id']
    }
  },

  /**
   * Create a Discord channel
   */
  discordCreateChannel: {
    id: 'discordCreateChannel',
    name: 'Create Channel',
    description: 'Create a new channel in a Discord guild',
    category: 'channel-management',
    icon: '➕',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        guild_id: {
          type: 'string',
          description: 'Guild ID (required)',
          minLength: 17
        },
        name: {
          type: 'string',
          description: 'Channel name (required)',
          minLength: 1,
          maxLength: 100
        },
        type: {
          type: 'number',
          description: 'Channel type (default: 0 - Text)',
          enum: [0, 2, 4, 5, 13],  # Text, Voice, Category, News, Stage Voice
          default: 0
        },
        topic: {
          type: 'string',
          description: 'Channel topic (text channels only)',
          maxLength: 1024
        },
        position: {
          type: 'number',
          description: 'Channel position (default: 0)',
          minimum: 0
        },
        permission_overwrites: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string' },
              type: { type: 'string' },
              allow: { type: 'string' },
              deny: { type: 'string' }
            }
          },
          description: 'Permission overwrites (optional)',
          default: []
        }
      },
      required: ['user_id', 'guild_id', 'name']
    }
  },

  /**
   * Get messages from a Discord channel
   */
  discordGetMessages: {
    id: 'discordGetMessages',
    name: 'Get Channel Messages',
    description: 'Get messages from a Discord channel',
    category: 'message-management',
    icon: '💬',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        channel_id: {
          type: 'string',
          description: 'Channel ID (required)',
          minLength: 17
        },
        limit: {
          type: 'number',
          description: 'Maximum number of messages to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        },
        before: {
          type: 'string',
          description: 'Get messages before this message ID',
          minLength: 17
        },
        after: {
          type: 'string',
          description: 'Get messages after this message ID',
          minLength: 17
        }
      },
      required: ['user_id', 'channel_id']
    }
  },

  /**
   * Send a message to a Discord channel
   */
  discordSendMessage: {
    id: 'discordSendMessage',
    name: 'Send Message',
    description: 'Send a message to a Discord channel',
    category: 'message-management',
    icon: '📤',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        channel_id: {
          type: 'string',
          description: 'Channel ID (required)',
          minLength: 17
        },
        content: {
          type: 'string',
          description: 'Message content (required)',
          minLength: 1,
          maxLength: 2000
        },
        embeds: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              title: { type: 'string', maxLength: 256 },
              description: { type: 'string', maxLength: 2048 },
              url: { type: 'string' },
              color: { type: 'number' },
              fields: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    name: { type: 'string', maxLength: 256 },
                    value: { type: 'string', maxLength: 1024 },
                    inline: { type: 'boolean' }
                  }
                }
              }
            }
          },
          description: 'Message embeds (optional)',
          default: []
        },
        tts: {
          type: 'boolean',
          description: 'Send as text-to-speech message (default: false)',
          default: false
        },
        allowed_mentions: {
          type: 'object',
          description: 'Allowed mentions (optional)',
          properties: {
            parse: { type: 'array', items: { type: 'string' } },
            roles: { type: 'array', items: { type: 'string' } },
            users: { type: 'array', items: { type: 'string' } },
            replied_user: { type: 'boolean' }
          }
        },
        message_reference: {
          type: 'object',
          description: 'Reply to message (optional)',
          properties: {
            message_id: { type: 'string' },
            channel_id: { type: 'string' },
            guild_id: { type: 'string' }
          }
        }
      },
      required: ['user_id', 'channel_id', 'content']
    }
  },

  /**
   * Get Discord bot information
   */
  discordGetBot: {
    id: 'discordGetBot',
    name: 'Get Bot Info',
    description: 'Get Discord bot application information',
    category: 'bot-management',
    icon: '🤖',
    parameters: {
      type: 'object',
      properties: {}
    }
  },

  /**
   * Start Discord OAuth flow
   */
  discordStartOAuth: {
    id: 'discordStartOAuth',
    name: 'Start Discord OAuth',
    description: 'Start Discord OAuth 2.0 authorization flow',
    category: 'authentication',
    icon: '🔐',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        scopes: {
          type: 'array',
          items: {
            type: 'string',
            enum: [
              'identify', 'email', 'guilds', 'bot', 
              'messages.read', 'channels.read', 
              'webhook.incoming', 'applications.commands'
            ]
          },
          description: 'OAuth scopes (default: identify, guilds)',
          default: ['identify', 'guilds']
        },
        permissions: {
          type: 'string',
          description: 'Bot permissions (default: 8 - Administrator)',
          default: '8'
        }
      },
      required: ['user_id']
    }
  },

  /**
   * Refresh Discord tokens
   */
  discordRefreshTokens: {
    id: 'discordRefreshTokens',
    name: 'Refresh Discord Tokens',
    description: 'Refresh Discord access tokens',
    category: 'authentication',
    icon: '🔄',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        refresh_token: {
          type: 'string',
          description: 'Refresh token (optional - will use stored token)',
          minLength: 1
        }
      },
      required: ['user_id']
    }
  },

  /**
   * Check Discord authentication status
   */
  discordCheckAuth: {
    id: 'discordCheckAuth',
    name: 'Check Auth Status',
    description: 'Check Discord authentication status for user',
    category: 'authentication',
    icon: '✅',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        }
      },
      required: ['user_id']
    }
  },

  /**
   * Disconnect Discord integration
   */
  discordDisconnect: {
    id: 'discordDisconnect',
    name: 'Disconnect Discord',
    description: 'Disconnect Discord integration for user',
    category: 'authentication',
    icon: '❌',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        }
      },
      required: ['user_id']
    }
  },

  /**
   * Sync Discord data
   */
  discordSyncData: {
    id: 'discordSyncData',
    name: 'Sync Discord Data',
    description: 'Sync Discord data for user (guilds, channels, messages)',
    category: 'data-management',
    icon: '🔄',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        sync_types: {
          type: 'array',
          items: {
            type: 'string',
            enum: ['user', 'guilds', 'channels', 'messages']
          },
          description: 'Data types to sync (default: all)',
          default: ['user', 'guilds', 'channels', 'messages']
        }
      },
      required: ['user_id']
    }
  },

  /**
   * Create Discord webhook
   */
  discordCreateWebhook: {
    id: 'discordCreateWebhook',
    name: 'Create Webhook',
    description: 'Create a Discord webhook for a channel',
    category: 'webhook-management',
    icon: '🪝',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        channel_id: {
          type: 'string',
          description: 'Channel ID (required)',
          minLength: 17
        },
        name: {
          type: 'string',
          description: 'Webhook name (required)',
          minLength: 1,
          maxLength: 100
        },
        avatar: {
          type: 'string',
          description: 'Webhook avatar URL (optional)'
        }
      },
      required: ['user_id', 'channel_id', 'name']
    }
  },

  /**
   * Delete Discord message
   */
  discordDeleteMessage: {
    id: 'discordDeleteMessage',
    name: 'Delete Message',
    description: 'Delete a message from a Discord channel',
    category: 'message-management',
    icon: '🗑️',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        channel_id: {
          type: 'string',
          description: 'Channel ID (required)',
          minLength: 17
        },
        message_id: {
          type: 'string',
          description: 'Message ID to delete (required)',
          minLength: 17
        }
      },
      required: ['user_id', 'channel_id', 'message_id']
    }
  },

  /**
   * Edit Discord message
   */
  discordEditMessage: {
    id: 'discordEditMessage',
    name: 'Edit Message',
    description: 'Edit an existing Discord message',
    category: 'message-management',
    icon: '✏️',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        channel_id: {
          type: 'string',
          description: 'Channel ID (required)',
          minLength: 17
        },
        message_id: {
          type: 'string',
          description: 'Message ID to edit (required)',
          minLength: 17
        },
        content: {
          type: 'string',
          description: 'New message content (required)',
          minLength: 1,
          maxLength: 2000
        },
        embeds: {
          type: 'array',
          items: {
            type: 'object'
          },
          description: 'New message embeds (optional)',
          default: []
        }
      },
      required: ['user_id', 'channel_id', 'message_id', 'content']
    }
  },

  /**
   * Pin Discord message
   */
  discordPinMessage: {
    id: 'discordPinMessage',
    name: 'Pin Message',
    description: 'Pin a message in a Discord channel',
    category: 'message-management',
    icon: '📌',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        channel_id: {
          type: 'string',
          description: 'Channel ID (required)',
          minLength: 17
        },
        message_id: {
          type: 'string',
          description: 'Message ID to pin (required)',
          minLength: 17
        }
      },
      required: ['user_id', 'channel_id', 'message_id']
    }
  },

  /**
   * Get Discord channel information
   */
  discordGetChannel: {
    id: 'discordGetChannel',
    name: 'Get Channel Info',
    description: 'Get detailed information about a Discord channel',
    category: 'channel-management',
    icon: '📺',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User ID (required)',
          minLength: 1
        },
        channel_id: {
          type: 'string',
          description: 'Channel ID (required)',
          minLength: 17
        }
      },
      required: ['user_id', 'channel_id']
    }
  }
};

/**
 * Discord skill utilities and formatting helpers
 */
export const discordUtils = {
  /**
   * Format user for display
   */
  formatUser: (user: DiscordUser): string => {
    const username = user.displayName || user.globalName || user.username;
    return `${username}#${user.discriminator}`;
  },

  /**
   * Format user with avatar
   */
  formatUserWithAvatar: (user: DiscordUser): string => {
    const username = user.displayName || user.globalName || user.username;
    const avatar = user.avatarUrl ? `[👤](${user.avatarUrl})` : '👤';
    return `${avatar} ${username}#${user.discriminator}`;
  },

  /**
   * Format guild for display
   */
  formatGuild: (guild: DiscordGuild): string => {
    const icon = guild.iconUrl ? `[🏰](${guild.iconUrl})` : '🏰';
    return `${icon} ${guild.name}`;
  },

  /**
   * Format channel for display
   */
  formatChannel: (channel: DiscordChannel): string => {
    const typeIcons: Record<number, string> = {
      0: '#',  // Text
      1: '👥', // DM
      2: '🎤', // Voice
      3: '👥', // Group DM
      4: '📁', // Category
      5: '📢', // News
      10: '🧵', // News Thread
      11: '🧵', // Public Thread
      12: '🧵', // Private Thread
      13: '🎭', // Stage Voice
    };
    
    const icon = typeIcons[channel.type] || '📺';
    return `${icon} ${channel.name}`;
  },

  /**
   * Format message for display
   */
  formatMessage: (message: DiscordMessage): string => {
    const author = message.author.displayName || message.author.username;
    const content = message.content.length > 100 
      ? message.content.substring(0, 100) + '...' 
      : message.content;
    return `**${author}**: ${content}`;
  },

  /**
   * Format message with embeds
   */
  formatMessageFull: (message: DiscordMessage): string => {
    const author = message.author.displayName || message.author.username;
    let result = `**${author}**: ${message.content}`;
    
    if (message.embeds && message.embeds.length > 0) {
      result += '\n\n**Embeds:**';
      message.embeds.forEach((embed, index) => {
        if (embed.title) {
          result += `\n*${index + 1}. ${embed.title}*`;
        }
        if (embed.description) {
          result += `\n${embed.description}`;
        }
      });
    }
    
    if (message.attachments && message.attachments.length > 0) {
      result += '\n\n**Attachments:**';
      message.attachments.forEach((attachment, index) => {
        result += `\n*${index + 1}. ${attachment.filename || 'Attachment'}*`;
      });
    }
    
    return result;
  },

  /**
   * Format role for display
   */
  formatRole: (role: DiscordRole): string => {
    const color = role.color > 0 ? `**${role.name}**` : role.name;
    return color;
  },

  /**
   * Get channel type name
   */
  getChannelTypeName: (type: number): string => {
    const typeNames: Record<number, string> = {
      0: "Text",
      1: "DM",
      2: "Voice",
      3: "Group DM",
      4: "Category",
      5: "News",
      10: "News Thread",
      11: "Public Thread",
      12: "Private Thread",
      13: "Stage Voice"
    };
    return typeNames[type] || "Unknown";
  },

  /**
   * Get user initial
   */
  getUserInitial: (user: DiscordUser): string => {
    const name = user.displayName || user.globalName || user.username;
    return name ? name.substring(0, 1).toUpperCase() : '?';
  },

  /**
   * Validate Discord ID format
   */
  validateDiscordId: (id: string): boolean => {
    return /^\d{17,19}$/.test(id);
  },

  /**
   * Validate channel ID format
   */
  validateChannelId: (channelId: string): boolean => {
    return /^\d{17,19}$/.test(channelId);
  },

  /**
   * Validate guild ID format
   */
  validateGuildId: (guildId: string): boolean => {
    return /^\d{17,19}$/.test(guildId);
  },

  /**
   * Format date time
   */
  formatDateTime: (dateTime: string): string => {
    try {
      const date = new Date(dateTime);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return dateTime;
    }
  },

  /**
   * Format relative time
   */
  getRelativeTime: (dateTime: string): string => {
    try {
      const date = new Date(dateTime);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      
      if (diffDays > 0) {
        return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
      }
      
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      if (diffHours > 0) {
        return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
      }
      
      const diffMinutes = Math.floor(diffMs / (1000 * 60));
      if (diffMinutes > 0) {
        return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
      }
      
      return 'Just now';
    } catch {
      return dateTime;
    }
  },

  /**
   * Truncate message content
   */
  truncateContent: (content: string, maxLength: number = 100): string => {
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength - 3) + '...';
  },

  /**
   * Format permissions
   */
  formatPermissions: (permissions: string): string => {
    try {
      const perm = parseInt(permissions);
      if (perm === 8) return 'Administrator';
      if (perm === 68608) return 'Basic';
      if (perm === 2147483647) return 'All';
      return `${perm}`;
    } catch {
      return permissions;
    }
  },

  /**
   * Format message content with markdown
   */
  formatMessageMarkdown: (content: string): string => {
    // Discord markdown to basic formatting
    return content
      .replace(/\*\*(.*?)\*\*/g, '**$1**')  // Bold
      .replace(/\*(.*?)\*/g, '*$1*')       // Italic
      .replace(/__(.*?)__/g, '**$1**')      // Bold
      .replace(/_(.*?)_/g, '*$1*')         // Italic
      .replace(/`([^`]+)`/g, '`$1`')     // Code
      .replace(/```([\s\S]*?)```/g, '```$1```'); // Code block
  },

  /**
   * Get user status indicator
   */
  getUserStatusIndicator: (status: string): string => {
    const indicators: Record<string, string> = {
      'online': '🟢',
      'idle': '🟡',
      'dnd': '🔴',
      'invisible': '⚫',
      'offline': '⚪'
    };
    return indicators[status] || '⚪';
  },

  /**
   * Get voice channel status
   */
  getVoiceChannelStatus: (channel: DiscordChannel): string => {
    if (channel.type !== 2) return '';  // Not a voice channel
    
    let status = `🎤 ${channel.name}`;
    if (channel.userLimit) {
      status += ` (${channel.userLimit} users)`;
    }
    if (channel.bitrate) {
      status += ` 📶 ${Math.round(channel.bitrate / 1000)}kbps`;
    }
    return status;
  },

  /**
   * Format embed for display
   */
  formatEmbed: (embed: any): string => {
    let result = '';
    
    if (embed.title) {
      result += `**${embed.title}**\n`;
    }
    
    if (embed.description) {
      result += `${embed.description}\n`;
    }
    
    if (embed.fields && embed.fields.length > 0) {
      embed.fields.forEach((field: any) => {
        result += `**${field.name}**: ${field.value}\n`;
      });
    }
    
    if (embed.url) {
      result += `[🔗 Link](${embed.url})`;
    }
    
    return result.trim();
  },

  /**
   * Get guild invite URL
   */
  getGuildInviteUrl: (guildId: string): string => {
    return `https://discord.gg/${guildId}`;
  },

  /**
   * Get channel URL
   */
  getChannelUrl: (guildId: string, channelId: string): string => {
    return `https://discord.com/channels/${guildId}/${channelId}`;
  },

  /**
   * Get message URL
   */
  getMessageUrl: (guildId: string, channelId: string, messageId: string): string => {
    return `https://discord.com/channels/${guildId}/${channelId}/${messageId}`;
  }
};

export default discordSkills;