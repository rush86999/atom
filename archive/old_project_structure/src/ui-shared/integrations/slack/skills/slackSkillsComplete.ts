/**
 * Slack Integration Skills
 * Complete Slack integration with comprehensive messaging and collaboration capabilities
 */

export interface SlackSkillConfig {
  accessToken?: string;
  baseUrl?: string;
  userAgent?: string;
}

export interface SlackChannel {
  id: string;
  name: string;
  isChannel: boolean;
  isGroup: boolean;
  isIm: boolean;
  isMpim: boolean;
  isPrivate: boolean;
  isArchived: boolean;
  isGeneral: boolean;
  nameNormalized: string;
  isShared: boolean;
  isOrgShared: boolean;
  isPendingExtShared: boolean;
  parentConversation: string;
  creator: string;
  isExtShared: boolean;
  sharedTeamIds: string[];
  numMembers: number;
  topic: string;
  purpose: string;
  previousNames: string[];
  priority: string;
  created: number;
  connectedTeamIds: string[];
  conversationHostId: string;
  internalTeamIds: string[];
  unlinked: boolean;
  notifications: any;
  joined: boolean;
  pendingShared: string[];
  dateLastRead: string;
  unreadCount: number;
  unreadCountDisplay: number;
  userLimit: number;
  whoCanPost: string;
  slackCommandsEnabled: boolean;
  blocks: any[];
  attachments: any[];
  team: string;
}

export interface SlackMessage {
  ts: string;
  text: string;
  user: string;
  channel: string;
  threadTs: string;
  username: string;
  botId: string;
  files: SlackFile[];
  reactions: SlackReaction[];
  pinnedTo: string[];
  messageType: string;
  subtype: string;
  blocks: any[];
  attachments: any[];
  team: string;
  appId: string;
  edited: any;
  lastRead: string;
}

export interface SlackUser {
  id: string;
  name: string;
  realName: string;
  displayName: string;
  email: string;
  image24: string;
  image32: string;
  image48: string;
  image72: string;
  image192: string;
  image512: string;
  title: string;
  phone: string;
  skype: string;
  teamId: string;
  deleted: boolean;
  status: string;
  isBot: boolean;
  isAdmin: boolean;
  isOwner: boolean;
  isPrimaryOwner: boolean;
  isRestricted: boolean;
  isUltraRestricted: boolean;
  isAppUser: boolean;
  hasFiles: boolean;
  presence: string;
  tz: string;
  tzLabel: string;
  tzOffset: number;
  pronouns: string;
  isWorkflowBot: boolean;
}

export interface SlackFile {
  id: string;
  created: number;
  timestamp: number;
  name: string;
  title: string;
  mimetype: string;
  filetype: string;
  prettyType: string;
  user: string;
  mode: string;
  editable: boolean;
  size: number;
  isPublic: boolean;
  publicUrlShared: boolean;
  urlPrivate: string;
  urlPrivateDownload: string;
  displayAsBot: boolean;
  commentsCount: number;
  shares: any;
  channels: string[];
  groups: string[];
  ims: string[];
  hasRichPreview: boolean;
  externalId: string;
  externalUrl: string;
  uploaded: boolean;
  initialComment: any;
  permalink: string;
  permalinkPublic: string;
  hasMore: boolean;
  previewHighlight: any;
}

export interface SlackReaction {
  name: string;
  count: number;
}

/**
 * Slack Skills Registry - Complete set of Slack integration capabilities
 */
export const slackSkills = {
  
  /**
   * Create a new Slack channel
   */
  slackCreateChannel: {
    id: 'slackCreateChannel',
    name: 'Create Slack Channel',
    description: 'Create a new Slack channel with configuration options',
    category: 'communication',
    icon: '💬',
    parameters: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Channel name (required)',
          minLength: 1,
          maxLength: 21,
          pattern: '^[a-z0-9-_]+$'
        },
        isPrivate: {
          type: 'boolean',
          description: 'Whether channel should be private (default: false)',
          default: false
        },
        topic: {
          type: 'string',
          description: 'Channel topic (optional)',
          maxLength: 250
        },
        purpose: {
          type: 'string',
          description: 'Channel purpose (optional)',
          maxLength: 250
        }
      },
      required: ['name']
    }
  },

  /**
   * List Slack channels
   */
  slackListChannels: {
    id: 'slackListChannels',
    name: 'List Slack Channels',
    description: 'List channels accessible to the authenticated user',
    category: 'communication',
    icon: '📋',
    parameters: {
      type: 'object',
      properties: {
        types: {
          type: 'array',
          items: {
            type: 'string',
            enum: ['public_channel', 'private_channel', 'im', 'mpim']
          },
          description: 'Channel types to include (default: all)',
          default: ['public_channel', 'private_channel']
        },
        excludeArchived: {
          type: 'boolean',
          description: 'Exclude archived channels (default: true)',
          default: true
        },
        limit: {
          type: 'number',
          description: 'Maximum number of channels to return (default: 100, max: 1000)',
          default: 100,
          minimum: 1,
          maximum: 1000
        }
      }
    }
  },

  /**
   * Send a Slack message
   */
  slackSendMessage: {
    id: 'slackSendMessage',
    name: 'Send Slack Message',
    description: 'Send a message to a Slack channel',
    category: 'communication',
    icon: '📤',
    parameters: {
      type: 'object',
      properties: {
        channel: {
          type: 'string',
          description: 'Channel ID or name (required)',
          minLength: 1
        },
        text: {
          type: 'string',
          description: 'Message text (required)',
          minLength: 1,
          maxLength: 40000
        },
        threadTs: {
          type: 'string',
          description: 'Thread timestamp to reply to (optional)'
        },
        parse: {
          type: 'string',
          enum: ['full', 'none'],
          description: 'Parsing mode (optional)'
        },
        blocks: {
          type: 'array',
          items: {
            type: 'object'
          },
          description: 'Block Kit blocks (optional)'
        },
        attachments: {
          type: 'array',
          items: {
            type: 'object'
          },
          description: 'Message attachments (optional)'
        }
      },
      required: ['channel', 'text']
    }
  },

  /**
   * List Slack messages
   */
  slackListMessages: {
    id: 'slackListMessages',
    name: 'List Slack Messages',
    description: 'List messages from a Slack channel',
    category: 'communication',
    icon: '📝',
    parameters: {
      type: 'object',
      properties: {
        channel: {
          type: 'string',
          description: 'Channel ID or name (required)',
          minLength: 1
        },
        limit: {
          type: 'number',
          description: 'Maximum number of messages to return (default: 100, max: 1000)',
          default: 100,
          minimum: 1,
          maximum: 1000
        },
        oldest: {
          type: 'string',
          description: 'Start of time range (optional)'
        },
        latest: {
          type: 'string',
          description: 'End of time range (optional)'
        },
        inclusive: {
          type: 'boolean',
          description: 'Include messages with oldest/latest timestamps (default: false)',
          default: false
        }
      },
      required: ['channel']
    }
  },

  /**
   * Upload a file to Slack
   */
  slackUploadFile: {
    id: 'slackUploadFile',
    name: 'Upload File to Slack',
    description: 'Upload a file to Slack channels',
    category: 'file-management',
    icon: '📁',
    parameters: {
      type: 'object',
      properties: {
        filePath: {
          type: 'string',
          description: 'Path to file to upload (required)',
          minLength: 1
        },
        filename: {
          type: 'string',
          description: 'Custom filename (optional)'
        },
        title: {
          type: 'string',
          description: 'File title (optional)',
          maxLength: 200
        },
        initialComment: {
          type: 'string',
          description: 'Initial comment for the file (optional)',
          maxLength: 1000
        },
        channels: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Channel IDs to share file with (optional)'
        }
      },
      required: ['filePath']
    }
  },

  /**
   * List Slack files
   */
  slackListFiles: {
    id: 'slackListFiles',
    name: 'List Slack Files',
    description: 'List files uploaded to Slack',
    category: 'file-management',
    icon: '📄',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of files to return (default: 100, max: 1000)',
          default: 100,
          minimum: 1,
          maximum: 1000
        },
        userFilter: {
          type: 'string',
          description: 'Filter by user ID (optional)'
        },
        channel: {
          type: 'string',
          description: 'Filter by channel ID (optional)'
        },
        typesFilter: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Filter by file types (optional)'
        }
      }
    }
  },

  /**
   * List Slack users
   */
  slackListUsers: {
    id: 'slackListUsers',
    name: 'List Slack Users',
    description: 'List users in the Slack workspace',
    category: 'user-management',
    icon: '👥',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of users to return (default: 1000, max: 1000)',
          default: 1000,
          minimum: 1,
          maximum: 1000
        },
        presence: {
          type: 'boolean',
          description: 'Include user presence information (default: false)',
          default: false
        },
        teamId: {
          type: 'string',
          description: 'Filter by team ID (optional)'
        }
      }
    }
  },

  /**
   * Get Slack user information
   */
  slackGetUserInfo: {
    id: 'slackGetUserInfo',
    name: 'Get Slack User Info',
    description: 'Get detailed information about a Slack user',
    category: 'user-management',
    icon: '👤',
    parameters: {
      type: 'object',
      properties: {
        targetUserId: {
          type: 'string',
          description: 'User ID to get information for (required)',
          minLength: 1
        }
      },
      required: ['targetUserId']
    }
  },

  /**
   * Search Slack messages
   */
  slackSearchMessages: {
    id: 'slackSearchMessages',
    name: 'Search Slack Messages',
    description: 'Search for messages in Slack channels',
    category: 'search',
    icon: '🔍',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query (required)',
          minLength: 1,
          maxLength: 1000
        },
        channel: {
          type: 'string',
          description: 'Channel to search in (optional)'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        },
        sort: {
          type: 'string',
          enum: ['timestamp', 'relevance'],
          description: 'Sort order (default: relevance)',
          default: 'relevance'
        },
        sortDir: {
          type: 'string',
          enum: ['asc', 'desc'],
          description: 'Sort direction (default: desc)',
          default: 'desc'
        }
      },
      required: ['query']
    }
  },

  /**
   * Join a Slack channel
   */
  slackJoinChannel: {
    id: 'slackJoinChannel',
    name: 'Join Slack Channel',
    description: 'Join a Slack channel',
    category: 'communication',
    icon: '🔗',
    parameters: {
      type: 'object',
      properties: {
        channel: {
          type: 'string',
          description: 'Channel ID to join (required)',
          minLength: 1
        }
      },
      required: ['channel']
    }
  },

  /**
   * Leave a Slack channel
   */
  slackLeaveChannel: {
    id: 'slackLeaveChannel',
    name: 'Leave Slack Channel',
    description: 'Leave a Slack channel',
    category: 'communication',
    icon: '🚪',
    parameters: {
      type: 'object',
      properties: {
        channel: {
          type: 'string',
          description: 'Channel ID to leave (required)',
          minLength: 1
        }
      },
      required: ['channel']
    }
  },

  /**
   * Get channel information
   */
  slackGetChannelInfo: {
    id: 'slackGetChannelInfo',
    name: 'Get Channel Info',
    description: 'Get detailed information about a Slack channel',
    category: 'communication',
    icon: 'ℹ️',
    parameters: {
      type: 'object',
      properties: {
        channelId: {
          type: 'string',
          description: 'Channel ID to get information for (required)',
          minLength: 1
        },
        includeLocale: {
          type: 'boolean',
          description: 'Include locale information (default: true)',
          default: true
        },
        includeNumMembers: {
          type: 'boolean',
          description: 'Include member count (default: false)',
          default: false
        }
      },
      required: ['channelId']
    }
  }
};

/**
 * Slack skill utilities and formatting helpers
 */
export const slackUtils = {
  /**
   * Format channel for display
   */
  formatChannel: (channel: SlackChannel): string => {
    const privacy = channel.isPrivate ? '🔒' : '🌍';
    const members = channel.numMembers > 0 ? ` (${channel.numMembers} members)` : '';
    return `${privacy} #${channel.name}${members}`;
  },

  /**
   * Format message for display
   */
  formatMessage: (message: SlackMessage): string => {
    const reactions = message.reactions.length > 0 
      ? ` ${message.reactions.map(r => `:${r.name}: ${r.count}`).join(' ')}` 
      : '';
    const isThread = message.threadTs ? ' 💬' : '';
    return `💬 ${message.text}${isThread}${reactions}`;
  },

  /**
   * Format user for display
   */
  formatUser: (user: SlackUser): string => {
    const presence = user.presence === 'active' ? '🟢' : user.presence === 'away' ? '🟡' : '⚪';
    const bot = user.isBot ? '🤖' : '';
    const admin = user.isAdmin ? '👑' : '';
    return `${presence} ${user.realName || user.name}${bot}${admin}`;
  },

  /**
   * Format file for display
   */
  formatFile: (file: SlackFile): string => {
    const type = file.filetype || file.prettyType || 'file';
    const size = file.size > 0 ? ` (${this.formatFileSize(file.size)})` : '';
    return `📎 ${file.name} (${type})${size}`;
  },

  /**
   * Get channel URL
   */
  getChannelUrl: (channel: SlackChannel, teamDomain: string = 'company'): string => {
    return `https://${teamDomain}.slack.com/archives/${channel.id}`;
  },

  /**
   * Get message URL
   */
  getMessageUrl: (message: SlackMessage, teamDomain: string = 'company'): string => {
    return `https://${teamDomain}.slack.com/archives/${message.channel}/p${message.ts.replace('.', '')}`;
  },

  /**
   * Get user URL
   */
  getUserUrl: (user: SlackUser, teamDomain: string = 'company'): string => {
    return `https://${teamDomain}.slack.com/team/${user.id}`;
  },

  /**
   * Get file URL
   */
  getFileUrl: (file: SlackFile): string => {
    return file.permalink || file.urlPrivate;
  },

  /**
   * Extract channel name from ID
   */
  extractChannelName: (channelId: string): string => {
    return channelId.startsWith('#') ? channelId.substring(1) : channelId;
  },

  /**
   * Validate channel name
   */
  validateChannelName: (name: string): boolean => {
    return /^[a-z0-9-_]+$/.test(name) && name.length >= 1 && name.length <= 21;
  },

  /**
   * Format file size
   */
  formatFileSize: (bytes: number): string => {
    const sizes = ['B', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${Math.round(bytes / Math.pow(1024, i) * 100) / 100} ${sizes[i]}`;
  },

  /**
   * Get file type icon
   */
  getFileTypeIcon: (filetype: string, mimetype: string = ''): string => {
    const icons: Record<string, string> = {
      'pdf': '📄',
      'doc': '📝',
      'docx': '📝',
      'xls': '📊',
      'xlsx': '📊',
      'ppt': '📈',
      'pptx': '📈',
      'jpg': '🖼️',
      'jpeg': '🖼️',
      'png': '🖼️',
      'gif': '🖼️',
      'svg': '🎨',
      'mp4': '🎥',
      'mov': '🎥',
      'avi': '🎥',
      'mp3': '🎵',
      'wav': '🎵',
      'zip': '🗜️',
      'rar': '🗜️',
      'txt': '📃',
      'md': '📃',
      'json': '📋',
      'xml': '📋',
      'code': '💻'
    };
    
    if (icons[filetype]) return icons[filetype];
    
    // Check by MIME type
    if (mimetype.includes('image')) return '🖼️';
    if (mimetype.includes('video')) return '🎥';
    if (mimetype.includes('audio')) return '🎵';
    if (mimetype.includes('pdf')) return '📄';
    if (mimetype.includes('text')) return '📃';
    
    return '📎';
  },

  /**
   * Format timestamp
   */
  formatTimestamp: (timestamp: string): string => {
    const date = new Date(parseFloat(timestamp) * 1000);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    
    if (hours < 1) {
      const minutes = Math.floor(diff / (1000 * 60));
      return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    } else if (hours < 24) {
      return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    } else {
      const days = Math.floor(hours / 24);
      return `${days} day${days !== 1 ? 's' : ''} ago`;
    }
  },

  /**
   * Truncate text
   */
  truncateText: (text: string, maxLength: number = 50): string => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
  },

  /**
   * Get presence color
   */
  getPresenceColor: (presence: string): string => {
    const colors: Record<string, string> = {
      'active': '#4caf50',
      'away': '#ff9800',
      'dnd': '#f44336',
      'offline': '#9e9e9e'
    };
    return colors[presence] || '#9e9e9e';
  },

  /**
   * Parse Slack mention
   */
  parseMention: (text: string, users: SlackUser[]): string => {
    return text.replace(/<@([UW][A-Z0-9]+)(?:\|([^>]+))?>/g, (match, userId, name) => {
      const user = users.find(u => u.id === userId);
      return `@${user?.displayName || user?.name || name || userId}`;
    });
  },

  /**
   * Parse Slack channel link
   */
  parseChannelLink: (text: string): string => {
    return text.replace(/<#([CG][A-Z0-9]+)(?:\|([^>]+))?>/g, (match, channelId, name) => {
      return `#${name || channelId}`;
    });
  },

  /**
   * Check if message is from bot
   */
  isBotMessage: (message: SlackMessage): boolean => {
    return !!(message.botId || message.subtype === 'bot_message');
  },

  /**
   * Check if message is in thread
   */
  isThreadMessage: (message: SlackMessage): boolean => {
    return !!(message.threadTs && message.threadTs !== message.ts);
  },

  /**
   * Get thread parent timestamp
   */
  getThreadParentTs: (message: SlackMessage): string => {
    return message.threadTs || message.ts;
  }
};

export default slackSkills;