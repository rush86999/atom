/**
 * Communication Platform Data Transformers
 * Transforms platform-specific data to unified CommunicationHub format
 */

import { Message } from './CommunicationHub';

export const transformSlackToMessage = (slackMessage: any): Message => {
  return {
    id: slackMessage.ts || slackMessage.id,
    platform: "slack" as const,
    from: slackMessage.user || slackMessage.username || "Unknown",
    to: slackMessage.channel,
    subject: slackMessage.subject || "",
    preview: (slackMessage.text || slackMessage.content || '')?.substring(0, 100) + '...' || "",
    content: slackMessage.text || slackMessage.content || "",
    timestamp: new Date(parseFloat(slackMessage.ts || slackMessage.timestamp) * 1000),
    unread: !slackMessage.read || slackMessage.unread,
    priority: "normal" as const,
    status: "received" as const,
    attachments: slackMessage.files?.map((f: any) => f.name || f.id) || slackMessage.attachments?.map((a: any) => a.title) || [],
    threadId: slackMessage.thread_ts || slackMessage.threadId,
    isReply: !!slackMessage.thread_ts && slackMessage.thread_ts !== slackMessage.ts,
    color: "#4A154B",
    // Additional metadata for internal use
    reactions: slackMessage.reactions || {},
    replyCount: slackMessage.reply_count || 0,
    isEdited: !!slackMessage.edited,
    isDeleted: slackMessage.deleted || false,
    mentions: slackMessage.mentions || [],
    channelInfo: {
      id: slackMessage.channel_id,
      name: slackMessage.channel_name,
      teamId: slackMessage.team_id
    }
  };
};

export const transformTeamsToMessage = (teamsMessage: any): Message => {
  const content = teamsMessage.body?.content || teamsMessage.content || "";
  const senderName = teamsMessage.from?.user?.displayName || 
                    teamsMessage.from?.application?.displayName || 
                    "Unknown";
  
  return {
    id: teamsMessage.id,
    platform: "teams" as const,
    from: senderName,
    to: teamsMessage.channelId || teamsMessage.channel_info?.name,
    subject: teamsMessage.subject || "",
    preview: content.substring(0, 100) + (content.length > 100 ? "..." : ""),
    content: content,
    timestamp: new Date(teamsMessage.createdDateTime || teamsMessage.timestamp),
    unread: false, // Teams doesn't easily provide read status
    priority: "normal" as const,
    status: "received" as const,
    attachments: teamsMessage.attachments?.map((a: any) => a.name || a.id) || [],
    threadId: teamsMessage.replyToId || teamsMessage.thread_id || teamsMessage.id,
    isReply: !!teamsMessage.replyToId,
    color: "#6264A7",
    // Additional metadata for internal use
    reactions: transformTeamsReactions(teamsMessage.reactions || []),
    replyCount: teamsMessage.replyCount || teamsMessage.reply_count || 0,
    isEdited: teamsMessage.lastModifiedDateTime !== teamsMessage.createdDateTime,
    isDeleted: !!teamsMessage.deletedDateTime,
    mentions: teamsMessage.mentions || [],
    channelInfo: {
      id: teamsMessage.channel_id,
      name: teamsMessage.channel_name,
      teamId: teamsMessage.team_id
    }
  };
};

export const transformEmailToMessage = (emailMessage: any): Message => {
  return {
    id: emailMessage.id || emailMessage.messageId,
    platform: "email" as const,
    from: emailMessage.from?.emailAddress?.address || emailMessage.from || "Unknown",
    to: emailMessage.toRecipients?.[0]?.emailAddress?.address || emailMessage.to || "",
    subject: emailMessage.subject || "",
    preview: (emailMessage.bodyPreview || emailMessage.snippet || "")?.substring(0, 100) + '...' || "",
    content: emailMessage.body?.content || emailMessage.content || "",
    timestamp: new Date(emailMessage.receivedDateTime || emailMessage.date),
    unread: emailMessage.isRead === false,
    priority: emailMessage.importance === "high" ? "high" : 
              emailMessage.importance === "low" ? "low" : "normal" as const,
    status: "received" as const,
    attachments: emailMessage.attachments?.map((a: any) => a.name || a.fileName) || [],
    threadId: emailMessage.conversationId || emailMessage.threadId,
    isReply: !!emailMessage.conversationId,
    color: "#3182CE",
    // Additional metadata for internal use
    reactions: {},
    replyCount: emailMessage.conversationId ? 1 : 0,
    isEdited: false,
    isDeleted: false,
    mentions: [],
    channelInfo: {
      id: emailMessage.id,
      name: "inbox",
      teamId: ""
    }
  };
};

export const transformGenericToMessage = (genericMessage: any, platform: string): Message => {
  switch (platform) {
    case 'slack':
      return transformSlackToMessage(genericMessage);
    case 'teams':
      return transformTeamsToMessage(genericMessage);
    case 'email':
      return transformEmailToMessage(genericMessage);
    default:
      // Generic fallback
      return {
        id: genericMessage.id,
        platform: platform as any,
        from: genericMessage.from || "Unknown",
        to: genericMessage.to || "",
        subject: genericMessage.subject || "",
        preview: (genericMessage.content || genericMessage.message || "")?.substring(0, 100) + '...' || "",
        content: genericMessage.content || genericMessage.message || "",
        timestamp: new Date(genericMessage.timestamp || genericMessage.created_at),
        unread: genericMessage.unread || false,
        priority: genericMessage.priority || "normal" as const,
        status: genericMessage.status || "received" as const,
        attachments: genericMessage.attachments || [],
        threadId: genericMessage.thread_id || genericMessage.id,
        isReply: !!genericMessage.thread_id,
        color: getPlatformColor(platform),
        reactions: genericMessage.reactions || {},
        replyCount: genericMessage.reply_count || 0,
        isEdited: genericMessage.is_edited || false,
        isDeleted: genericMessage.is_deleted || false,
        mentions: genericMessage.mentions || [],
        channelInfo: {
          id: genericMessage.channel_id,
          name: genericMessage.channel_name,
          teamId: genericMessage.team_id
        }
      };
  }
};

// Helper function to get platform colors
export const getPlatformColor = (platform: string): string => {
  switch (platform) {
    case "email":
      return "#3182CE";
    case "slack":
      return "#4A154B";
    case "teams":
      return "#6264A7";
    case "discord":
      return "#5865F2";
    case "whatsapp":
      return "#25D366";
    case "sms":
      return "#34B7F1";
    default:
      return "#718096";
  }
};

// Transform Teams reactions to unified format
function transformTeamsReactions(teamsReactions: any[]): Record<string, number> {
  const reactions = {
    like: 0,
    heart: 0,
    laugh: 0,
    surprised: 0,
    sad: 0,
    angry: 0,
    thumbsup: 0,
    thumbsdown: 0,
    eyes: 0,
    raised_hands: 0,
    rocket: 0
  };

  teamsReactions.forEach(reaction => {
    const reactionType = reaction.reactionType?.toLowerCase();
    const count = reaction.count || 0;

    switch (reactionType) {
      case 'like':
        reactions.like += count;
        break;
      case 'heart':
        reactions.heart += count;
        break;
      case 'laugh':
        reactions.laugh += count;
        break;
      case 'surprised':
        reactions.surprised += count;
        break;
      case 'sad':
        reactions.sad += count;
        reactions.thumbsdown += count;
        break;
      case 'angry':
        reactions.angry += count;
        reactions.thumbsdown += count;
        break;
      default:
        reactions.thumbsup += count;
    }
  });

  return reactions;
}

// Transform unified message back to platform-specific format
export const transformMessageToSlack = (message: Message): any => {
  return {
    channel: message.channelInfo?.id,
    text: message.content,
    thread_ts: message.threadId === message.id ? undefined : message.threadId,
    attachments: message.attachments?.map((name, index) => ({
      id: `attachment_${index}`,
      title: name,
      fallback: name
    })) || []
  };
};

export const transformMessageToTeams = (message: Message): any => {
  return {
    body: {
      contentType: "text",
      content: message.content
    },
    attachments: message.attachments?.map((name, index) => ({
      id: `attachment_${index}`,
      name: name,
      contentType: "reference"
    })) || []
  };
};

export const transformMessageToEmail = (message: Message): any => {
  return {
    subject: message.subject,
    body: {
      contentType: "text",
      content: message.content
    },
    toRecipients: message.to ? [{
      emailAddress: {
        address: message.to
      }
    }] : [],
    attachments: message.attachments?.map((name, index) => ({
      name: name,
      contentType: "application/octet-stream"
    })) || []
  };
};

// Channel transformers
export const transformSlackChannel = (slackChannel: any): any => {
  return {
    id: slackChannel.id,
    name: slackChannel.name,
    displayName: slackChannel.name,
    platform: "slack",
    teamId: slackChannel.team_id,
    type: slackChannel.channel_type || slackChannel.type,
    isPrivate: slackChannel.is_private,
    isArchived: slackChannel.is_archived,
    memberCount: slackChannel.member_count,
    purpose: slackChannel.purpose?.value || slackChannel.purpose,
    topic: slackChannel.topic?.value || slackChannel.topic
  };
};

export const transformTeamsChannel = (teamsChannel: any): any => {
  return {
    id: teamsChannel.id,
    name: teamsChannel.displayName,
    displayName: teamsChannel.displayName,
    platform: "teams",
    teamId: teamsChannel.team_id,
    type: teamsChannel.membershipType || teamsChannel.type,
    isPrivate: teamsChannel.membershipType === "private",
    isArchived: teamsChannel.isArchived || false,
    memberCount: 0, // Not provided in basic Teams API
    purpose: teamsChannel.description || "",
    topic: ""
  };
};

// Team/Workspace transformers
export const transformSlackTeam = (slackTeam: any): any => {
  return {
    id: slackTeam.id,
    name: slackTeam.name,
    displayName: slackTeam.name,
    platform: "slack",
    domain: slackTeam.domain,
    icon: slackTeam.image?.image?.["230"],
    isVerified: slackTeam.is_verified,
    type: "workspace"
  };
};

export const transformTeamsTeam = (teamsTeam: any): any => {
  return {
    id: teamsTeam.id,
    name: teamsTeam.displayName,
    displayName: teamsTeam.displayName,
    platform: "teams",
    description: teamsTeam.description,
    visibility: teamsTeam.visibility,
    isArchived: teamsTeam.isArchived,
    webUrl: teamsTeam.webUrl,
    type: "team"
  };
};