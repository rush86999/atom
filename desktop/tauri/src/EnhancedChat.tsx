/**
 * Enhanced Chat with Outlook Skills Integration
 * Replaces basic Chat.tsx with skill-based communication
 */

import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/tauri";
import { 
  outlookEmailSkill, 
  outlookCalendarSkill,
  OutlookEmailSkillParams,
  OutlookCalendarSkillParams
} from "./skills/outlookSkills";
import { 
  nlpService, 
  Intent, 
  Entity, 
  SkillExecutionContext 
} from "./services/nlpService";
import { EventBus } from "./utils/EventBus";
import { Logger } from "./utils/Logger";
import "./App.css";

interface Message {
  id: string;
  text: string;
  sender: "user" | "agent";
  timestamp: string;
  skillsUsed?: string[];
  context?: any;
}

interface ChatResponse {
  text: string;
  skillsExecuted?: string[];
  context?: any;
  suggestions?: string[];
}

interface OutlookSkillResult {
  success: boolean;
  data?: any;
  error?: string;
}

function EnhancedChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [outlookConnected, setOutlookConnected] = useState(false);
  
  const logger = new Logger('EnhancedChat');

  // Check Outlook connection status
  useEffect(() => {
    checkOutlookConnection();
    
    // Listen for Outlook events
    EventBus.on('outlook:email:sent', (data) => {
      logger.info('Outlook email sent', data);
      addSystemMessage(`✅ Email sent: ${data.subject}`);
    });
    
    EventBus.on('outlook:calendar:event:created', (data) => {
      logger.info('Outlook calendar event created', data);
      addSystemMessage(`📅 Calendar event created: ${data.subject}`);
    });
    
    EventBus.on('outlook:emails:triaged', (data) => {
      logger.info('Outlook emails triaged', data);
      addSystemMessage(`📧 Triaged ${data.total} emails into ${data.categories.length} categories`);
    });

    return () => {
      EventBus.off('outlook:email:sent');
      EventBus.off('outlook:calendar:event:created');
      EventBus.off('outlook:emails:triaged');
    };
  }, []);

  const checkOutlookConnection = async () => {
    try {
      const result = await invoke<any>('check_outlook_tokens', {
        userId: 'desktop-user'
      });
      setOutlookConnected(result.valid && !result.expired);
    } catch (error) {
      logger.warn('Failed to check Outlook connection', error);
      setOutlookConnected(false);
    }
  };

  const addSystemMessage = (text: string) => {
    const systemMessage: Message = {
      id: Date.now().toString(),
      text,
      sender: "agent",
      timestamp: new Date().toISOString(),
      skillsUsed: ["system"]
    };
    setMessages(prev => [...prev, systemMessage]);
  };

  const handleSend = async () => {
    if (input.trim() === "") return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: input,
      sender: "user",
      timestamp: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, userMessage]);
    const userInput = input;
    setInput("");
    setIsLoading(true);

    try {
      // Process the message with NLP
      const nlpResult = await nlpService.processMessage(userInput);
      const response = await processUserMessage(userInput, nlpResult);
      
      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.text,
        sender: "agent",
        timestamp: new Date().toISOString(),
        skillsUsed: response.skillsExecuted,
        context: response.context
      };
      
      setMessages(prev => [...prev, agentMessage]);
      
      // Add suggestions if available
      if (response.suggestions && response.suggestions.length > 0) {
        setTimeout(() => {
          const suggestionsMessage: Message = {
            id: (Date.now() + 2).toString(),
            text: `💡 Suggestions: ${response.suggestions.join(" • ")}`,
            sender: "agent",
            timestamp: new Date().toISOString(),
            skillsUsed: ["suggestions"]
          };
          setMessages(prev => [...prev, suggestionsMessage]);
        }, 500);
      }
      
    } catch (error) {
      logger.error('Failed to process message', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: "Sorry, I encountered an error processing your request. Please try again.",
        sender: "agent",
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const processUserMessage = async (message: string, nlpResult: any): Promise<ChatResponse> => {
    const { intent, entities, confidence } = nlpResult;
    
    logger.info('Processing message', { intent, entities, confidence });
    
    // Create execution context
    const context: SkillExecutionContext = {
      userId: 'desktop-user',
      sessionId: Date.now().toString(),
      timestamp: new Date().toISOString(),
      intent: intent,
      entities: entities,
      confidence: confidence
    };

    // Handle Outlook-specific intents
    switch (intent) {
      case 'outlook_send_email':
        return await handleOutlookSendEmail(entities, context);
        
      case 'outlook_get_emails':
        return await handleOutlookGetEmails(entities, context);
        
      case 'outlook_search_emails':
        return await handleOutlookSearchEmails(entities, context);
        
      case 'outlook_triage_emails':
        return await handleOutlookTriageEmails(entities, context);
        
      case 'outlook_create_event':
        return await handleOutlookCreateEvent(entities, context);
        
      case 'outlook_get_calendar':
        return await handleOutlookGetCalendar(entities, context);
        
      case 'outlook_search_events':
        return await handleOutlookSearchEvents(entities, context);
        
      case 'outlook_help':
        return getOutlookHelp();
        
      case 'outlook_status':
        return getOutlookStatus();
        
      default:
        return await handleGeneralMessage(message, nlpResult, context);
    }
  };

  const handleOutlookSendEmail = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!outlookConnected) {
      return {
        text: "❌ Outlook is not connected. Please connect your Outlook account in Settings first.",
        skillsExecuted: ["outlook_check"]
      };
    }

    const to = extractEntityValue(entities, 'recipient') || [];
    const subject = extractEntityValue(entities, 'subject');
    const body = extractEntityValue(entities, 'message') || extractEntityValue(entities, 'body');
    const cc = extractEntityValue(entities, 'cc') || [];

    if (!to.length || !subject || !body) {
      return {
        text: "📧 I need the recipient(s), subject, and message content to send an email. For example: \"Send an email to john@example.com with subject 'Meeting Update' and message 'The meeting has been rescheduled to 3 PM.'\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: OutlookEmailSkillParams = {
        action: 'send',
        to: Array.isArray(to) ? to : [to],
        subject,
        body,
        cc: Array.isArray(cc) ? cc : cc ? [cc] : undefined
      };

      const result = await outlookEmailSkill.execute(params, context);
      
      if (result.success) {
        return {
          text: `✅ Email sent successfully to ${params.to.join(', ')} with subject "${subject}"`,
          skillsExecuted: ["outlook_email_send"],
          context: result,
          suggestions: [
            "Check if you need to attach any files",
            "Follow up with the recipients if needed"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to send email: ${error}`,
        skillsExecuted: ["outlook_email_send"]
      };
    }
  };

  const handleOutlookGetEmails = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!outlookConnected) {
      return {
        text: "❌ Outlook is not connected. Please connect your Outlook account in Settings first.",
        skillsExecuted: ["outlook_check"]
      };
    }

    const limit = extractEntityValue(entities, 'count') || extractEntityValue(entities, 'limit') || 10;
    const unread = extractEntityValue(entities, 'unread') !== undefined;

    try {
      const params: OutlookEmailSkillParams = {
        action: 'get',
        limit: typeof limit === 'string' ? parseInt(limit) : limit,
        unread
      };

      const result = await outlookEmailSkill.execute(params, context);
      
      if (result.success && result.emails) {
        const emailList = result.emails.map((email: any) => 
          `• ${email.subject} from ${email.from.name} (${email.isRead ? 'Read' : 'Unread'})`
        ).join('\n');

        return {
          text: `📧 Found ${result.count} emails:\n\n${emailList}`,
          skillsExecuted: ["outlook_email_get"],
          context: result,
          suggestions: [
            "Triage these emails by priority",
            "Search for specific emails",
            "Send replies to important emails"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to retrieve emails: ${error}`,
        skillsExecuted: ["outlook_email_get"]
      };
    }
  };

  const handleOutlookCreateEvent = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!outlookConnected) {
      return {
        text: "❌ Outlook is not connected. Please connect your Outlook account in Settings first.",
        skillsExecuted: ["outlook_check"]
      };
    }

    const subject = extractEntityValue(entities, 'subject') || extractEntityValue(entities, 'title');
    const startTime = extractEntityValue(entities, 'start_time') || extractEntityValue(entities, 'time');
    const endTime = extractEntityValue(entities, 'end_time');
    const location = extractEntityValue(entities, 'location');
    const attendees = extractEntityValue(entities, 'attendees');

    if (!subject || !startTime) {
      return {
        text: "📅 I need the event title and start time to create a calendar event. For example: \"Create a calendar event 'Team Meeting' tomorrow at 2 PM in Conference Room A\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: OutlookCalendarSkillParams = {
        action: 'create',
        subject,
        startTime: typeof startTime === 'string' ? startTime : startTime.toString(),
        endTime: typeof endTime === 'string' ? endTime : endTime || '',
        location,
        attendees: Array.isArray(attendees) ? attendees : attendees ? [attendees] : undefined
      };

      const result = await outlookCalendarSkill.execute(params, context);
      
      if (result.success) {
        return {
          text: `📅 Calendar event "${subject}" created successfully${location ? ` at ${location}` : ''}`,
          skillsExecuted: ["outlook_calendar_create"],
          context: result,
          suggestions: [
            "Send meeting invitations to attendees",
            "Set a reminder for this event",
            "Check for conflicting events"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to create calendar event: ${error}`,
        skillsExecuted: ["outlook_calendar_create"]
      };
    }
  };

  const handleOutlookTriageEmails = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    if (!outlookConnected) {
      return {
        text: "❌ Outlook is not connected. Please connect your Outlook account in Settings first.",
        skillsExecuted: ["outlook_check"]
      };
    }

    try {
      const params: OutlookEmailSkillParams = {
        action: 'triage'
      };

      const result = await outlookEmailSkill.execute(params, context);
      
      if (result.success && result.summary) {
        const { total, highPriority, requiresAction } = result.summary;
        const categories = Object.keys(result.categorized);
        
        return {
          text: `📧 Email triage complete!\n\n📊 Summary:\n• Total emails: ${total}\n• High priority: ${highPriority}\n• Requires action: ${requiresAction}\n\n📂 Categories: ${categories.join(', ')}`,
          skillsExecuted: ["outlook_email_triage"],
          context: result,
          suggestions: [
            "Focus on high-priority emails first",
            "Create follow-up tasks for emails requiring action",
            "Archive categorized emails"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to triage emails: ${error}`,
        skillsExecuted: ["outlook_email_triage"]
      };
    }
  };

  const handleOutlookSearchEmails = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    const searchQuery = extractEntityValue(entities, 'search_query') || extractEntityValue(entities, 'query');
    
    if (!searchQuery) {
      return {
        text: "🔍 What would you like me to search for in your emails? For example: \"Search emails for 'project update'\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: OutlookEmailSkillParams = {
        action: 'search',
        searchQuery: typeof searchQuery === 'string' ? searchQuery : searchQuery.toString(),
        limit: 10
      };

      const result = await outlookEmailSkill.execute(params, context);
      
      if (result.success && result.emails) {
        const emailList = result.emails.map((email: any) => 
          `• ${email.subject} from ${email.from.name}`
        ).join('\n');

        return {
          text: `🔍 Found ${result.count} emails matching "${searchQuery}":\n\n${emailList}`,
          skillsExecuted: ["outlook_email_search"],
          context: result
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to search emails: ${error}`,
        skillsExecuted: ["outlook_email_search"]
      };
    }
  };

  const handleOutlookGetCalendar = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    try {
      const params: OutlookCalendarSkillParams = {
        action: 'get',
        limit: extractEntityValue(entities, 'count') || 5
      };

      const result = await outlookCalendarSkill.execute(params, context);
      
      if (result.success && result.events) {
        const eventList = result.events.map((event: any) => 
          `• ${event.subject} at ${formatDateTime(event.start.dateTime)}`
        ).join('\n');

        return {
          text: `📅 Your upcoming events:\n\n${eventList}`,
          skillsExecuted: ["outlook_calendar_get"],
          context: result,
          suggestions: [
            "Create reminders for important events",
            "Check for scheduling conflicts",
            "Share event details with attendees"
          ]
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to retrieve calendar events: ${error}`,
        skillsExecuted: ["outlook_calendar_get"]
      };
    }
  };

  const handleOutlookSearchEvents = async (entities: Entity[], context: SkillExecutionContext): Promise<ChatResponse> => {
    const searchQuery = extractEntityValue(entities, 'search_query') || extractEntityValue(entities, 'query');
    
    if (!searchQuery) {
      return {
        text: "🔍 What would you like me to search for in your calendar? For example: \"Search calendar for 'team meeting'\"",
        skillsExecuted: ["validation"]
      };
    }

    try {
      const params: OutlookCalendarSkillParams = {
        action: 'search',
        searchQuery: typeof searchQuery === 'string' ? searchQuery : searchQuery.toString()
      };

      const result = await outlookCalendarSkill.execute(params, context);
      
      if (result.success && result.events) {
        const eventList = result.events.map((event: any) => 
          `• ${event.subject} at ${formatDateTime(event.start.dateTime)}`
        ).join('\n');

        return {
          text: `🔍 Found ${result.count} events matching "${searchQuery}":\n\n${eventList}`,
          skillsExecuted: ["outlook_calendar_search"],
          context: result
        };
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      return {
        text: `❌ Failed to search calendar events: ${error}`,
        skillsExecuted: ["outlook_calendar_search"]
      };
    }
  };

  const getOutlookHelp = (): ChatResponse => {
    return {
      text: `📧 **Outlook Help** - Here's what I can help you with:

**Email Management:**
• Send emails: "Send an email to john@example.com with subject 'Meeting Update'"
• Get emails: "Show me my recent emails" or "Get unread emails"
• Search emails: "Search emails for 'project update'"
• Triage emails: "Triage my emails by priority"

**Calendar Management:**
• Create events: "Create a calendar event 'Team Meeting' tomorrow at 2 PM"
• Get events: "Show me my upcoming events"
• Search events: "Search calendar for 'client meeting'"

**Other Commands:**
• Check status: "Is Outlook connected?"
• Get help: "Outlook help"

${outlookConnected ? '✅ Outlook is connected and ready to use!' : '❌ Outlook is not connected. Go to Settings to connect your account.'}`,
      skillsExecuted: ["help"],
      suggestions: [
        "Try sending a test email",
        "Create a sample calendar event",
        "Check your connection status"
      ]
    };
  };

  const getOutlookStatus = (): ChatResponse => {
    return {
      text: outlookConnected 
        ? "✅ Outlook is connected and ready to help with emails and calendar management!"
        : "❌ Outlook is not connected. Please go to Settings to connect your Outlook account.",
      skillsExecuted: ["status_check"],
      suggestions: outlookConnected ? [
        "Try sending a test email",
        "Check your upcoming events"
      ] : [
        "Go to Settings to connect Outlook",
        "Check your OAuth configuration"
      ]
    };
  };

  const handleGeneralMessage = async (message: string, nlpResult: any, context: SkillExecutionContext): Promise<ChatResponse> => {
    // Check if it's an Outlook-related general message
    const messageLower = message.toLowerCase();
    
    if (messageLower.includes('outlook') || messageLower.includes('email') || messageLower.includes('calendar')) {
      return {
        text: `📧 I can help you with Outlook email and calendar management! 

Try commands like:
• "Send an email to..."
• "Show me my emails"  
• "Create a calendar event..."
• "Search for..."

Type "Outlook help" for more details.`,
        skillsExecuted: ["outlook_general"]
      };
    }

    // Fallback to general agent
    try {
      const response: string = await invoke("send_message_to_agent", { message });
      return {
        text: response,
        skillsExecuted: ["general_agent"]
      };
    } catch (error) {
      return {
        text: "I'm here to help with Outlook emails and calendar management. What would you like to do?",
        skillsExecuted: ["fallback"]
      };
    }
  };

  // Helper functions
  const extractEntityValue = (entities: Entity[], entityType: string): any => {
    const entity = entities.find(e => e.type === entityType);
    return entity ? entity.value : undefined;
  };

  const formatDateTime = (dateTimeStr: string): string => {
    return new Date(dateTimeStr).toLocaleString();
  };

  return (
    <div className="chat-container enhanced">
      {/* Connection Status */}
      <div className={`connection-status ${outlookConnected ? 'connected' : 'disconnected'}`}>
        <span className="status-indicator"></span>
        <span className="status-text">
          Outlook {outlookConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* Messages */}
      <div className="messages enhanced">
        {messages.map((message, index) => (
          <div key={message.id} className={`message ${message.sender} enhanced`}>
            <div className="message-content">
              {message.text}
            </div>
            <div className="message-meta">
              <span className="timestamp">
                {new Date(message.timestamp).toLocaleTimeString()}
              </span>
              {message.skillsUsed && (
                <span className="skills-used">
                  🛠️ {message.skillsUsed.join(', ')}
                </span>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message agent enhanced">
            <div className="message-content">
              <span className="typing-indicator">
                🤔 Processing your request...
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="input-container enhanced">
        <div className="quick-actions">
          <button 
            onClick={() => setInput("Show me my recent emails")}
            className="quick-action-btn"
            disabled={!outlookConnected}
          >
            📧 Recent Emails
          </button>
          <button 
            onClick={() => setInput("Show me my upcoming events")}
            className="quick-action-btn"
            disabled={!outlookConnected}
          >
            📅 Calendar Events
          </button>
          <button 
            onClick={() => setInput("Outlook help")}
            className="quick-action-btn"
          >
            ❓ Help
          </button>
        </div>
        <div className="input-row">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSend()}
            placeholder={
              outlookConnected 
                ? "Ask me to send emails, manage calendar, or search..."
                : "Connect Outlook in Settings to use email and calendar features..."
            }
            disabled={isLoading}
            className={`message-input ${!outlookConnected ? 'disabled' : ''}`}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim() || !outlookConnected}
            className="send-button"
          >
            {isLoading ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default EnhancedChat;