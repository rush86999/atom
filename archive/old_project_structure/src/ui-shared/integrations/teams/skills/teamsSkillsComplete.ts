/**
 * Microsoft Teams Integration Skills
 * Complete Teams integration with comprehensive messaging and collaboration capabilities
 */

export interface TeamsSkillConfig {
  accessToken?: string;
  baseUrl?: string;
  userAgent?: string;
}

export interface TeamsChannel {
  id: string;
  displayName: string;
  description: string;
  email: string;
  webUrl: string;
  membershipType: string;
  tenantId: string;
  isFavoriteByDefault: boolean;
  teamId: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
}

export interface TeamsMessage {
  id: string;
  subject: string;
  body: string;
  summary: string;
  importance: string;
  locale: string;
  fromUser: string;
  fromEmail: string;
  conversationId: string;
  threadId: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  attachments: any[];
  mentions: any[];
  reactions: any[];
}

export interface TeamsUser {
  id: string;
  displayName: string;
  givenName: string;
  surname: string;
  mail: string;
  userPrincipalName: string;
  jobTitle: string;
  officeLocation: string;
  businessPhones: string[];
  mobilePhone: string;
  photoAvailable: boolean;
  accountEnabled: boolean;
  userType: string;
}

export interface TeamsMeeting {
  id: string;
  subject: string;
  body: string;
  startDateTime: string;
  endDateTime: string;
  location: string;
  attendees: any[];
  importance: string;
  isOnlineMeeting: boolean;
  onlineMeetingUrl: string;
  joinWebUrl: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
}

export interface TeamsFile {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  fileType: string;
  webUrl: string;
  createdBy: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  parentReference: any;
  shared: any;
}

/**
 * Teams Skills Registry - Complete set of Teams integration capabilities
 */
export const teamsSkills = {
  
  /**
   * Create a new Teams channel
   */
  teamsCreateChannel: {
    id: 'teamsCreateChannel',
    name: 'Create Teams Channel',
    description: 'Create a new Microsoft Teams channel',
    category: 'communication',
    icon: '👥',
    parameters: {
      type: 'object',
      properties: {
        displayName: {
          type: 'string',
          description: 'Channel display name (required)',
          minLength: 1,
          maxLength: 255
        },
        description: {
          type: 'string',
          description: 'Channel description (optional)',
          maxLength: 1024
        },
        teamId: {
          type: 'string',
          description: 'Team ID to create channel in (required)',
          minLength: 1
        },
        membershipType: {
          type: 'string',
          enum: ['standard', 'private', 'shared'],
          description: 'Channel membership type (default: standard)',
          default: 'standard'
        }
      },
      required: ['displayName', 'teamId']
    }
  },

  /**
   * List Teams channels
   */
  teamsListChannels: {
    id: 'teamsListChannels',
    name: 'List Teams Channels',
    description: 'List channels accessible to the authenticated user',
    category: 'communication',
    icon: '📋',
    parameters: {
      type: 'object',
      properties: {
        membershipFilter: {
          type: 'string',
          enum: ['user', 'shared', 'private'],
          description: 'Filter channels by membership type (default: user)',
          default: 'user'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of channels to return (default: 50, max: 200)',
          default: 50,
          minimum: 1,
          maximum: 200
        }
      }
    }
  },

  /**
   * Get Teams channel information
   */
  teamsGetChannelInfo: {
    id: 'teamsGetChannelInfo',
    name: 'Get Channel Info',
    description: 'Get detailed information about a Teams channel',
    category: 'communication',
    icon: 'ℹ️',
    parameters: {
      type: 'object',
      properties: {
        channelId: {
          type: 'string',
          description: 'Channel ID to get information for (required)',
          minLength: 1
        }
      },
      required: ['channelId']
    }
  },

  /**
   * Send a Teams message
   */
  teamsSendMessage: {
    id: 'teamsSendMessage',
    name: 'Send Teams Message',
    description: 'Send a message to a Teams channel',
    category: 'communication',
    icon: '📤',
    parameters: {
      type: 'object',
      properties: {
        channelId: {
          type: 'string',
          description: 'Channel ID to send message to (required)',
          minLength: 1
        },
        content: {
          type: 'string',
          description: 'Message content in HTML or plain text (required)',
          minLength: 1,
          maxLength: 28000
        },
        subject: {
          type: 'string',
          description: 'Message subject (optional)',
          maxLength: 255
        },
        importance: {
          type: 'string',
          enum: ['low', 'normal', 'high'],
          description: 'Message importance (default: normal)',
          default: 'normal'
        },
        threadId: {
          type: 'string',
          description: 'Thread ID to reply to (optional)',
          minLength: 1
        }
      },
      required: ['channelId', 'content']
    }
  },

  /**
   * List Teams messages
   */
  teamsListMessages: {
    id: 'teamsListMessages',
    name: 'List Teams Messages',
    description: 'List messages from a Teams channel',
    category: 'communication',
    icon: '📝',
    parameters: {
      type: 'object',
      properties: {
        channelId: {
          type: 'string',
          description: 'Channel ID to get messages from (required)',
          minLength: 1
        },
        limit: {
          type: 'number',
          description: 'Maximum number of messages to return (default: 50, max: 200)',
          default: 50,
          minimum: 1,
          maximum: 200
        },
        before: {
          type: 'string',
          description: 'Get messages before this timestamp (optional)'
        },
        after: {
          type: 'string',
          description: 'Get messages after this timestamp (optional)'
        }
      },
      required: ['channelId']
    }
  },

  /**
   * Create a Teams meeting
   */
  teamsCreateMeeting: {
    id: 'teamsCreateMeeting',
    name: 'Create Teams Meeting',
    description: 'Create a new Microsoft Teams meeting',
    category: 'collaboration',
    icon: '📅',
    parameters: {
      type: 'object',
      properties: {
        subject: {
          type: 'string',
          description: 'Meeting subject (required)',
          minLength: 1,
          maxLength: 255
        },
        content: {
          type: 'string',
          description: 'Meeting description/agenda (optional)',
          maxLength: 5000
        },
        startTime: {
          type: 'string',
          description: 'Meeting start time in ISO 8601 format (required)',
          pattern: '^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{3})?Z?$'
        },
        endTime: {
          type: 'string',
          description: 'Meeting end time in ISO 8601 format (required)',
          pattern: '^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{3})?Z?$'
        },
        attendees: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              emailAddress: {
                type: 'object',
                properties: {
                  address: {
                    type: 'string',
                    format: 'email'
                  },
                  name: {
                    type: 'string'
                  }
                }
              }
            }
          },
          description: 'Meeting attendees (optional)',
          default: []
        },
        location: {
          type: 'string',
          description: 'Physical meeting location (optional)',
          maxLength: 255
        },
        importance: {
          type: 'string',
          enum: ['low', 'normal', 'high'],
          description: 'Meeting importance (default: normal)',
          default: 'normal'
        }
      },
      required: ['subject', 'startTime', 'endTime']
    }
  },

  /**
   * List Teams meetings
   */
  teamsListMeetings: {
    id: 'teamsListMeetings',
    name: 'List Teams Meetings',
    description: 'List meetings for the authenticated user',
    category: 'collaboration',
    icon: '📅',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of meetings to return (default: 50, max: 200)',
          default: 50,
          minimum: 1,
          maximum: 200
        },
        startDate: {
          type: 'string',
          description: 'Start date filter in ISO 8601 format (optional)'
        },
        endDate: {
          type: 'string',
          description: 'End date filter in ISO 8601 format (optional)'
        }
      }
    }
  },

  /**
   * Upload a file to Teams
   */
  teamsUploadFile: {
    id: 'teamsUploadFile',
    name: 'Upload File to Teams',
    description: 'Upload a file to user\'s OneDrive for Teams',
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
          description: 'Custom filename (optional)',
          maxLength: 255
        },
        folderPath: {
          type: 'string',
          description: 'OneDrive folder path to upload to (optional)',
          maxLength: 500
        }
      },
      required: ['filePath']
    }
  },

  /**
   * List Teams files
   */
  teamsListFiles: {
    id: 'teamsListFiles',
    name: 'List Teams Files',
    description: 'List files from user\'s OneDrive',
    category: 'file-management',
    icon: '📄',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of files to return (default: 50, max: 200)',
          default: 50,
          minimum: 1,
          maximum: 200
        },
        folderPath: {
          type: 'string',
          description: 'OneDrive folder path to list files from (optional)',
          maxLength: 500
        }
      }
    }
  },

  /**
   * List Teams users
   */
  teamsListUsers: {
    id: 'teamsListUsers',
    name: 'List Teams Users',
    description: 'List users in the Teams organization',
    category: 'user-management',
    icon: '👥',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of users to return (default: 100, max: 500)',
          default: 100,
          minimum: 1,
          maximum: 500
        },
        searchQuery: {
          type: 'string',
          description: 'Search query to filter users (optional)',
          maxLength: 100
        }
      }
    }
  },

  /**
   * Get Teams user information
   */
  teamsGetUserInfo: {
    id: 'teamsGetUserInfo',
    name: 'Get Teams User Info',
    description: 'Get detailed information about a Teams user',
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
   * Search Teams messages
   */
  teamsSearchMessages: {
    id: 'teamsSearchMessages',
    name: 'Search Teams Messages',
    description: 'Search for messages in Teams channels',
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
        channelId: {
          type: 'string',
          description: 'Channel ID to search in (optional)',
          minLength: 1
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results (default: 50, max: 200)',
          default: 50,
          minimum: 1,
          maximum: 200
        }
      },
      required: ['query']
    }
  }
};

/**
 * Teams skill utilities and formatting helpers
 */
export const teamsUtils = {
  /**
   * Format channel for display
   */
  formatChannel: (channel: TeamsChannel): string => {
    const membership = channel.membershipType === 'private' ? '🔒' : 
                     channel.membershipType === 'shared' ? '👥' : '🌍';
    const favorite = channel.isFavoriteByDefault ? '⭐' : '';
    return `${membership} ${favorite} ${channel.displayName}`;
  },

  /**
   * Format message for display
   */
  formatMessage: (message: TeamsMessage): string => {
    const importance = message.importance === 'high' ? '🔴' :
                     message.importance === 'low' ? '🔵' : '';
    const subject = message.subject ? `[${message.subject}] ` : '';
    const thread = message.threadId && message.threadId !== message.id ? ' 💬' : '';
    return `${importance} ${subject}${message.body}${thread}`;
  },

  /**
   * Format user for display
   */
  formatUser: (user: TeamsUser): string => {
    const enabled = user.accountEnabled ? '✅' : '❌';
    const photo = user.photoAvailable ? '📷' : '';
    return `${enabled} ${photo} ${user.displayName}`;
  },

  /**
   * Format meeting for display
   */
  formatMeeting: (meeting: TeamsMeeting): string => {
    const online = meeting.isOnlineMeeting ? '🌐' : '📍';
    const importance = meeting.importance === 'high' ? '🔴' :
                      meeting.importance === 'low' ? '🔵' : '';
    const start = teamsUtils.formatDateTime(meeting.startDateTime);
    const end = teamsUtils.formatDateTime(meeting.endDateTime);
    return `${online} ${importance} ${meeting.subject} (${start} - ${end})`;
  },

  /**
   * Format file for display
   */
  formatFile: (file: TeamsFile): string => {
    const typeIcon = teamsUtils.getFileTypeIcon(file.mimeType);
    const size = file.size > 0 ? ` (${teamsUtils.formatFileSize(file.size)})` : '';
    return `${typeIcon} ${file.name}${size}`;
  },

  /**
   * Get channel URL
   */
  getChannelUrl: (channel: TeamsChannel): string => {
    return channel.webUrl || `https://teams.microsoft.com/l/channel/${channel.id}/${channel.displayName}`;
  },

  /**
   * Get meeting URL
   */
  getMeetingUrl: (meeting: TeamsMeeting): string => {
    return meeting.joinWebUrl || meeting.onlineMeetingUrl || '';
  },

  /**
   * Get file URL
   */
  getFileUrl: (file: TeamsFile): string => {
    return file.webUrl || '';
  },

  /**
   * Get user initials
   */
  getUserInitials: (user: TeamsUser): string => {
    const names = user.displayName.split(' ');
    if (names.length >= 2) {
      return names[0][0].toUpperCase() + names[names.length - 1][0].toUpperCase();
    }
    return names[0] ? names[0].substring(0, 2).toUpperCase() : 'UN';
  },

  /**
   * Extract channel name from ID
   */
  extractChannelName: (channelId: string): string => {
    // Teams channel IDs are complex, return ID or attempt to extract from webUrl
    return channelId;
  },

  /**
   * Validate meeting time
   */
  validateMeetingTime: (startTime: string, endTime: string): boolean => {
    const start = new Date(startTime);
    const end = new Date(endTime);
    const now = new Date();
    
    // Validate date format
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return false;
    }
    
    // End time must be after start time
    if (end <= start) {
      return false;
    }
    
    // Start time should be in the future (or within reasonable past)
    const minPastTime = new Date(now.getTime() - 24 * 60 * 60 * 1000); // 24 hours ago
    if (start < minPastTime) {
      return false;
    }
    
    return true;
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
   * Format date only
   */
  formatDate: (dateTime: string): string => {
    try {
      const date = new Date(dateTime);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateTime;
    }
  },

  /**
   * Format time only
   */
  formatTime: (dateTime: string): string => {
    try {
      const date = new Date(dateTime);
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return dateTime;
    }
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
  getFileTypeIcon: (mimeType: string): string => {
    const icons: Record<string, string> = {
      'application/pdf': '📄',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📝',
      'application/msword': '📝',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '📊',
      'application/vnd.ms-excel': '📊',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': '📈',
      'application/vnd.ms-powerpoint': '📈',
      'image/jpeg': '🖼️',
      'image/png': '🖼️',
      'image/gif': '🖼️',
      'image/svg+xml': '🎨',
      'video/mp4': '🎥',
      'video/quicktime': '🎥',
      'video/x-msvideo': '🎥',
      'audio/mpeg': '🎵',
      'audio/wav': '🎵',
      'text/plain': '📃',
      'text/html': '🌐',
      'application/json': '📋',
      'application/xml': '📋',
      'application/zip': '🗜️',
      'application/x-rar-compressed': '🗜️'
    };
    
    if (icons[mimeType]) return icons[mimeType];
    
    // Check by MIME type categories
    if (mimeType.startsWith('image/')) return '🖼️';
    if (mimeType.startsWith('video/')) return '🎥';
    if (mimeType.startsWith('audio/')) return '🎵';
    if (mimeType.startsWith('text/')) return '📃';
    if (mimeType.includes('pdf')) return '📄';
    if (mimeType.includes('word') || mimeType.includes('document')) return '📝';
    if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return '📊';
    if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return '📈';
    if (mimeType.includes('zip') || mimeType.includes('rar')) return '🗜️';
    
    return '📎';
  },

  /**
   * Get message importance color
   */
  getImportanceColor: (importance: string): string => {
    const colors: Record<string, string> = {
      'high': '#f44336',
      'normal': '#4caf50',
      'low': '#2196f3'
    };
    return colors[importance] || '#757575';
  },

  /**
   * Get meeting status
   */
  getMeetingStatus: (meeting: TeamsMeeting): string => {
    const now = new Date();
    const start = new Date(meeting.startDateTime);
    const end = new Date(meeting.endDateTime);
    
    if (now < start) return 'upcoming';
    if (now >= start && now <= end) return 'in-progress';
    if (now > end) return 'completed';
    
    return 'unknown';
  },

  /**
   * Format meeting status
   */
  formatMeetingStatus: (meeting: TeamsMeeting): string => {
    const status = teamsUtils.getMeetingStatus(meeting);
    const statusIcons: Record<string, string> = {
      'upcoming': '⏰',
      'in-progress': '🟢',
      'completed': '✅',
      'unknown': '❓'
    };
    
    return statusIcons[status] || '❓';
  },

  /**
   * Truncate text
   */
  truncateText: (text: string, maxLength: number = 50): string => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
  },

  /**
   * Check if message is recent
   */
  isRecentMessage: (message: TeamsMessage, hours: number = 24): boolean => {
    const created = new Date(message.createdDateTime);
    const now = new Date();
    const diffHours = (now.getTime() - created.getTime()) / (1000 * 60 * 60);
    return diffHours <= hours;
  },

  /**
   * Get relative time
   */
  getRelativeTime: (dateTime: string): string => {
    const date = new Date(dateTime);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffDays > 0) {
      return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    } else if (diffHours > 0) {
      return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else {
      const diffMinutes = Math.floor(diffMs / (1000 * 60));
      return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
    }
  },

  /**
   * Validate email address
   */
  validateEmail: (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  },

  /**
   * Format attendee list
   */
  formatAttendees: (attendees: any[]): string => {
    if (!attendees || attendees.length === 0) {
      return 'No attendees';
    }
    
    const names = attendees
      .map(attendee => attendee.emailAddress?.name || attendee.emailAddress?.address)
      .filter(Boolean)
      .slice(0, 3);
    
    if (attendees.length > 3) {
      names.push(`+${attendees.length - 3} more`);
    }
    
    return names.join(', ');
  },

  /**
   * Check if user is presenter
   */
  isPresenter: (userId: string, meeting: TeamsMeeting): boolean => {
    // This would need to be implemented based on meeting data
    return false;
  },

  /**
   * Get meeting duration
   */
  getMeetingDuration: (meeting: TeamsMeeting): string => {
    const start = new Date(meeting.startDateTime);
    const end = new Date(meeting.endDateTime);
    const diffMs = end.getTime() - start.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    
    if (diffMinutes < 60) {
      return `${diffMinutes} min`;
    }
    
    const hours = Math.floor(diffMinutes / 60);
    const minutes = diffMinutes % 60;
    
    if (minutes === 0) {
      return `${hours} hour${hours !== 1 ? 's' : ''}`;
    }
    
    return `${hours}h ${minutes}m`;
  }
};

export default teamsSkills;