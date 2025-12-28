import React, { useState, useEffect } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuCheckboxItem,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/components/ui/use-toast";
import {
  Mail,
  MessageSquare,
  Phone,
  Search,
  Filter,
  Plus,
  Trash2,
  Reply,
  CheckCircle,
  Clock,
  Paperclip,
  Download,
  MoreVertical,
  Loader2,
  X,
  ChevronDown,
  Copy,
  Send,
} from "lucide-react";

export interface Message {
  id: string;
  platform: "email" | "slack" | "teams" | "discord" | "whatsapp" | "sms";
  from: string;
  to?: string;
  subject: string;
  preview: string;
  content: string;
  timestamp: Date;
  unread: boolean;
  priority: "high" | "normal" | "low";
  attachments?: string[];
  threadId?: string;
  isReply?: boolean;
  status: "sent" | "received" | "draft" | "failed";
  color?: string;
}

export interface Conversation {
  id: string;
  title: string;
  participants: string[];
  messages: Message[];
  unreadCount: number;
  lastMessage: Date;
  platform: string;
  tags?: string[];
  priority: "high" | "normal" | "low";
}

export interface QuickReplyTemplate {
  id: string;
  name: string;
  content: string;
  category: string;
  platform: string[];
}

export interface CommunicationView {
  type: "inbox" | "thread" | "compose";
  filter: {
    platform?: string[];
    priority?: string[];
    unread?: boolean;
    search?: string;
  };
  sort: {
    field: "timestamp" | "priority" | "from";
    direction: "asc" | "desc";
  };
}

export interface CommunicationHubProps {
  onMessageSend?: (
    message: Omit<Message, "id" | "timestamp" | "status">,
  ) => void;
  onMessageUpdate?: (messageId: string, updates: Partial<Message>) => void;
  onMessageDelete?: (messageId: string) => void;
  onConversationCreate?: (conversation: Conversation) => void;
  initialMessages?: Message[];
  initialConversations?: Conversation[];
  initialTemplates?: QuickReplyTemplate[];
  showNavigation?: boolean;
  compactView?: boolean;
  isComposeOpen?: boolean;
  onComposeChange?: (isOpen: boolean) => void;
  currentUser?: string;
}

const CommunicationHub: React.FC<CommunicationHubProps> = ({
  onMessageSend,
  onMessageUpdate,
  onMessageDelete,
  onConversationCreate,
  initialMessages = [],
  initialConversations = [],
  initialTemplates = [],
  showNavigation = true,
  compactView = false,
  isComposeOpen: externalIsComposeOpen,
  onComposeChange,
  currentUser = "User",
}) => {
  const [internalIsComposeOpen, setInternalIsComposeOpen] = useState(false);

  const isComposeOpen = externalIsComposeOpen !== undefined ? externalIsComposeOpen : internalIsComposeOpen;
  const setIsComposeOpen = (open: boolean) => {
    if (onComposeChange) {
      onComposeChange(open);
    } else {
      setInternalIsComposeOpen(open);
    }
  };
  const [isMessageOpen, setIsMessageOpen] = useState(false);

  const { toast } = useToast();

  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [conversations, setConversations] = useState<Conversation[]>(initialConversations);
  const [templates, setTemplates] = useState<QuickReplyTemplate[]>(initialTemplates);
  const [loading, setLoading] = useState(true);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [view, setView] = useState<CommunicationView>({
    type: "inbox",
    filter: {},
    sort: { field: "timestamp", direction: "desc" },
  });

  // Mock data for demonstration
  useEffect(() => {
    const mockMessages: Message[] = [
      {
        id: "1",
        platform: "email",
        from: "team@company.com",
        to: "user@example.com",
        subject: "Weekly Team Update",
        preview: "Here are the updates from this week...",
        content:
          "Dear Team,\n\nHere are the key updates from this week:\n- Project Alpha: 75% complete\n- New feature deployment scheduled\n- Team meeting on Friday\n\nBest regards,\nTeam Lead",
        timestamp: new Date(2025, 9, 20, 14, 30),
        unread: true,
        priority: "normal",
        status: "received",
        color: "#3182CE",
      },
      {
        id: "2",
        platform: "slack",
        from: "john.doe",
        subject: "Design Review",
        preview: "Can we schedule a design review for tomorrow?",
        content:
          "Hey team, can we schedule a design review for tomorrow at 2 PM? I have the latest mockups ready.",
        timestamp: new Date(2025, 9, 20, 12, 15),
        unread: false,
        priority: "high",
        status: "received",
        color: "#4A154B",
      },
      {
        id: "3",
        platform: "teams",
        from: "sarah.wilson",
        subject: "Budget Meeting",
        preview: "Reminder about the budget meeting today",
        content:
          "Just a reminder about our budget meeting today at 3 PM. Please bring your department reports.",
        timestamp: new Date(2025, 9, 20, 9, 0),
        unread: false,
        priority: "normal",
        status: "received",
        color: "#6264A7",
      },
    ];

    const mockConversations: Conversation[] = [
      {
        id: "conv-1",
        title: "Weekly Team Updates",
        participants: ["team@company.com", "user@example.com"],
        messages: mockMessages.filter((msg) => msg.platform === "email"),
        unreadCount: 1,
        lastMessage: new Date(2025, 9, 20, 14, 30),
        platform: "email",
        tags: ["work", "updates"],
        priority: "normal",
      },
      {
        id: "conv-2",
        title: "Design Review Discussion",
        participants: ["john.doe", "user@example.com", "sarah.wilson"],
        messages: mockMessages.filter((msg) => msg.platform === "slack"),
        unreadCount: 0,
        lastMessage: new Date(2025, 9, 20, 12, 15),
        platform: "slack",
        tags: ["design", "review"],
        priority: "high",

      },
    ];

    const mockTemplates: QuickReplyTemplate[] = [
      {
        id: "temp-1",
        name: "Meeting Confirmation",
        content:
          "Thank you for scheduling the meeting. I have added it to my calendar.",
        category: "meetings",
        platform: ["email", "slack"],
      },
      {
        id: "temp-2",
        name: "Quick Follow-up",
        content:
          "Just following up on our previous conversation. Let me know if you need anything else.",
        category: "follow-up",
        platform: ["email", "slack", "teams"],
      },
      {
        id: "temp-3",
        name: "Availability Check",
        content: "What time works best for you this week?",
        category: "scheduling",
        platform: ["email", "slack"],
      },
    ];

    setMessages(mockMessages);
    setConversations(mockConversations);
    setTemplates(mockTemplates);
    setLoading(false);
  }, []);

  const handleSendMessage = async (
    messageData: Omit<Message, "id" | "timestamp" | "status">,
  ) => {
    try {
      const newMessage = {
        ...messageData,
        timestamp: new Date().toISOString(),
        status: "sent"
      };

      // Ingest into memory (this simulates sending for now)
      const res = await fetch(`/api/atom/communication/memory/ingest?app_id=${messageData.platform}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newMessage,
          sender: messageData.from,
          recipient: messageData.to,
          direction: 'outbound',
          app_type: messageData.platform
        })
      });

      if (res.ok) {
        const savedMessage: Message = {
          ...messageData,
          id: Date.now().toString(),
          timestamp: new Date(),
          status: "sent",
        };
        setMessages((prev) => [...prev, savedMessage]);
        onMessageSend?.(messageData);
        toast({
          title: "Message sent",
          description: "Your message has been processed and saved.",
        });
      } else {
        throw new Error('Failed to ingest sent message');
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      toast({
        title: "Error",
        description: "Failed to process message.",
        variant: "error"
      });
    }
  };

  const handleUpdateMessage = (
    messageId: string,
    updates: Partial<Message>,
  ) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId ? { ...message, ...updates } : message,
      ),
    );
    onMessageUpdate?.(messageId, updates);
    toast({
      title: "Message updated",
      description: "Message status has been updated.",
    });
  };

  const handleDeleteMessage = (messageId: string) => {
    setMessages((prev) => prev.filter((message) => message.id !== messageId));
    onMessageDelete?.(messageId);
    toast({
      title: "Message deleted",
      description: "Message has been removed.",
    });
  };

  const handleMarkAsRead = (messageId: string) => {
    handleUpdateMessage(messageId, { unread: false });
  };

  const handleMarkAllAsRead = () => {
    setMessages((prev) => prev.map((msg) => ({ ...msg, unread: false })));
    toast({
      title: "All messages marked as read",
    });
  };

  const getPlatformColor = (platform: string) => {
    switch (platform) {
      case "email":
        return "text-blue-600 bg-blue-100 dark:bg-blue-900 dark:text-blue-300";
      case "slack":
        return "text-purple-600 bg-purple-100 dark:bg-purple-900 dark:text-purple-300";
      case "teams":
        return "text-indigo-600 bg-indigo-100 dark:bg-indigo-900 dark:text-indigo-300";
      case "discord":
        return "text-indigo-500 bg-indigo-50 dark:bg-indigo-950 dark:text-indigo-400";
      case "whatsapp":
        return "text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-300";
      case "sms":
        return "text-cyan-600 bg-cyan-100 dark:bg-cyan-900 dark:text-cyan-300";
      default:
        return "text-gray-600 bg-gray-100 dark:bg-gray-800 dark:text-gray-300";
    }
  };

  const getPlatformIcon = (platform: string) => {
    const iconClass = "w-4 h-4";
    switch (platform) {
      case "email":
        return <Mail className={iconClass} />;
      case "slack":
      case "teams":
      case "discord":
        return <MessageSquare className={iconClass} />;
      case "whatsapp":
      case "sms":
        return <Phone className={iconClass} />;
      default:
        return <MessageSquare className={iconClass} />;
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const getFilteredMessages = () => {
    let filtered = [...messages];

    // Apply search filter
    if (searchQuery) {
      filtered = filtered.filter(
        (message) =>
          message.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
          message.preview.toLowerCase().includes(searchQuery.toLowerCase()) ||
          message.from.toLowerCase().includes(searchQuery.toLowerCase()),
      );
    }

    // Apply platform filters
    if (view.filter.platform?.length) {
      filtered = filtered.filter((message) =>
        view.filter.platform?.includes(message.platform),
      );
    }

    // Apply priority filters
    if (view.filter.priority?.length) {
      filtered = filtered.filter((message) =>
        view.filter.priority?.includes(message.priority),
      );
    }

    // Apply unread filter
    if (view.filter.unread) {
      filtered = filtered.filter((message) => message.unread);
    }

    // Apply sorting
    filtered.sort((a, b) => {
      const direction = view.sort.direction === "asc" ? 1 : -1;
      switch (view.sort.field) {
        case "timestamp":
          return (a.timestamp.getTime() - b.timestamp.getTime()) * direction;
        case "priority":
          const priorityOrder = { high: 3, normal: 2, low: 1 };
          return (
            (priorityOrder[a.priority] - priorityOrder[b.priority]) * direction
          );
        case "from":
          return a.from.localeCompare(b.from) * direction;
        default:
          return 0;
      }
    });

    return filtered;
  };

  const MessageComposer: React.FC<{
    onSubmit: (data: Omit<Message, "id" | "timestamp" | "status">) => void;
    onCancel: () => void;
    replyTo?: Message;
  }> = ({ onSubmit, onCancel, replyTo }) => {
    const [formData, setFormData] = useState({
      platform: replyTo?.platform || "email",
      to: replyTo?.from || "",
      subject: replyTo ? `Re: ${replyTo.subject}` : "",
      content: replyTo
        ? `\n\nOn ${replyTo.timestamp.toLocaleString()}, ${replyTo.from} wrote:\n> ${replyTo.content.split("\n").join("\n> ")}`
        : "",
      priority: "normal" as "high" | "normal" | "low",
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        platform: formData.platform as any,
        from: currentUser, // Current user
        to: formData.to,
        subject: formData.subject,
        preview:
          formData.content.slice(0, 100) +
          (formData.content.length > 100 ? "..." : ""),
        content: formData.content,
        unread: false,
        priority: formData.priority,
        isReply: !!replyTo,
        threadId: replyTo?.threadId || Date.now().toString(),
      });
      onCancel();
    };

    const applyTemplate = (template: QuickReplyTemplate) => {
      setFormData((prev) => ({
        ...prev,
        content: template.content + (prev.content ? `\n\n${prev.content}` : ""),
      }));
    };

    return (
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Platform</Label>
            <Select
              value={formData.platform}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, platform: value as any }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select platform" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="slack">Slack</SelectItem>
                <SelectItem value="teams">Microsoft Teams</SelectItem>
                <SelectItem value="discord">Discord</SelectItem>
                <SelectItem value="whatsapp">WhatsApp</SelectItem>
                <SelectItem value="sms">SMS</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Priority</Label>
            <Select
              value={formData.priority}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, priority: value as any }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="high">High</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <Label>To</Label>
          <Input
            value={formData.to}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, to: e.target.value }))
            }
            placeholder="Recipient email or username"
            required
          />
        </div>

        <div className="space-y-2">
          <Label>Subject</Label>
          <Input
            value={formData.subject}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, subject: e.target.value }))
            }
            placeholder="Message subject"
            required
          />
        </div>

        <div className="space-y-2">
          <Label>Message</Label>
          <Textarea
            value={formData.content}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, content: e.target.value }))
            }
            placeholder="Type your message here..."
            className="min-h-[200px]"
            required
          />
        </div>

        {/* Quick Reply Templates */}
        {templates.length > 0 && (
          <div className="space-y-2">
            <Label>Quick Reply Templates</Label>
            <div className="grid grid-cols-2 gap-2">
              {templates
                .filter((template) =>
                  template.platform.includes(formData.platform),
                )
                .slice(0, 4)
                .map((template) => (
                  <Button
                    key={template.id}
                    size="sm"
                    variant="outline"
                    onClick={() => applyTemplate(template)}
                    type="button"
                    className="justify-start"
                  >
                    <Copy className="w-3 h-3 mr-2" />
                    {template.name}
                  </Button>
                ))}
            </div>
          </div>
        )}

        <div className="flex justify-end space-x-3 pt-4">
          <Button variant="outline" onClick={onCancel} type="button">
            Cancel
          </Button>
          <Button type="submit">
            <Send className="w-4 h-4 mr-2" />
            Send Message
          </Button>
        </div>
      </form>
    );
  };

  const MessageViewer: React.FC<{
    message: Message;
    onClose: () => void;
  }> = ({ message, onClose }) => {
    return (
      <Dialog open={true} onOpenChange={(open) => !open && onClose()}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <div className="flex items-center space-x-2">
              <Badge className={getPlatformColor(message.platform)}>
                {message.platform.toUpperCase()}
              </Badge>
              <DialogTitle>{message.subject}</DialogTitle>
            </div>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-bold">{message.from}</p>
                <p className="text-sm text-gray-500">
                  {formatDate(message.timestamp)} at{" "}
                  {formatTime(message.timestamp)}
                </p>
              </div>
            </div>

            <div className="p-4 border rounded-md bg-gray-50 dark:bg-gray-900 whitespace-pre-wrap text-sm">
              {message.content}
            </div>

            {message.attachments && message.attachments.length > 0 && (
              <div className="space-y-2">
                <p className="font-bold text-sm">Attachments:</p>
                {message.attachments.map((attachment, index) => (
                  <div key={index} className="flex items-center justify-between p-2 border rounded text-sm">
                    <div className="flex items-center">
                      <Paperclip className="w-4 h-4 mr-2 text-gray-500" />
                      <span>{attachment}</span>
                    </div>
                    <Button size="sm" variant="ghost">
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2 sm:gap-0">
            <div className="flex space-x-2 w-full justify-end">
              <Button
                onClick={() => {
                  setSelectedMessage(message);
                  setIsComposeOpen(true);
                  onClose();
                }}
              >
                <Reply className="w-4 h-4 mr-2" />
                Reply
              </Button>
              <Button
                variant="outline"
                onClick={() => handleMarkAsRead(message.id)}
              >
                Mark as Read
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  handleDeleteMessage(message.id);
                  onClose();
                }}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-12 h-12 animate-spin text-blue-500 mb-4" />
        <p className="text-gray-600">Loading messages...</p>
      </div>
    );
  }

  const filteredMessages = getFilteredMessages();

  return (
    <div className={`space-y-6 ${compactView ? "p-2" : "p-6"}`}>
      {/* Header */}
      {showNavigation && (
        <div className="flex justify-between items-center">
          <h1 className={`font-bold ${compactView ? "text-xl" : "text-2xl"}`}>
            Communication Hub
          </h1>
          <Button
            onClick={() => setIsComposeOpen(true)}
            size={compactView ? "sm" : "default"}
          >
            <Plus className="w-4 h-4 mr-2" />
            New Message
          </Button>
        </div>
      )}

      {/* Search and Filters */}
      {showNavigation && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-500" />
                <Input
                  placeholder="Search messages..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-8"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2 top-2.5 text-gray-500 hover:text-gray-700"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant={view.filter.unread ? "default" : "outline"}
                  onClick={() =>
                    setView((prev) => ({
                      ...prev,
                      filter: { ...prev.filter, unread: !prev.filter.unread },
                    }))
                  }
                >
                  Unread Only
                </Button>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" variant="outline">
                      Platform: {view.filter.platform?.length || "All"} <ChevronDown className="ml-2 h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    {[
                      "email",
                      "slack",
                      "teams",
                      "discord",
                      "whatsapp",
                      "sms",
                    ].map((platform) => (
                      <DropdownMenuCheckboxItem
                        key={platform}
                        checked={view.filter.platform?.includes(platform)}
                        onCheckedChange={(checked) => {
                          const newPlatforms = checked
                            ? [...(view.filter.platform || []), platform]
                            : (view.filter.platform || []).filter(
                              (p) => p !== platform,
                            );
                          setView((prev) => ({
                            ...prev,
                            filter: {
                              ...prev.filter,
                              platform: newPlatforms,
                            },
                          }));
                        }}
                      >
                        {platform.charAt(0).toUpperCase() + platform.slice(1)}
                      </DropdownMenuCheckboxItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleMarkAllAsRead}
                >
                  Mark All Read
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Messages List */}
      <Card>
        <CardHeader className={compactView ? "p-4" : "p-6"}>
          <CardTitle className={compactView ? "text-lg" : "text-xl"}>
            Messages ({filteredMessages.length})
          </CardTitle>
        </CardHeader>
        <CardContent className={compactView ? "p-4 pt-0" : "p-6 pt-0"}>
          <div className="space-y-2">
            {filteredMessages.map((message) => (
              <div
                key={message.id}
                className={`p-3 border rounded-md cursor-pointer transition-colors ${message.unread ? "bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800" : "bg-white dark:bg-gray-950 hover:bg-gray-50 dark:hover:bg-gray-900"
                  }`}
                onClick={() => {
                  setSelectedMessage(message);
                  if (message.unread) {
                    handleMarkAsRead(message.id);
                  }
                }}
              >
                <div className="flex items-start space-x-3">
                  <div className={`p-2 rounded-full ${getPlatformColor(message.platform)} bg-opacity-20`}>
                    {getPlatformIcon(message.platform)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start mb-1">
                      <p className={`font-bold truncate ${compactView ? "text-sm" : "text-base"}`}>
                        {message.from}
                      </p>
                      <div className="flex items-center space-x-2 flex-shrink-0">
                        {message.unread && (
                          <Badge className="bg-blue-500 hover:bg-blue-600">New</Badge>
                        )}
                        <Badge
                          variant={message.priority === "high" ? "destructive" : "secondary"}
                          className={message.priority === "normal" ? "bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-300" : ""}
                        >
                          {message.priority}
                        </Badge>
                        <span className="text-xs text-gray-500">
                          {formatTime(message.timestamp)}
                        </span>
                      </div>
                    </div>
                    <p className={`font-semibold truncate mb-1 ${compactView ? "text-xs" : "text-sm"}`}>
                      {message.subject}
                    </p>
                    <p className={`text-gray-600 dark:text-gray-400 truncate ${compactView ? "text-xs" : "text-sm"}`}>
                      {message.preview}
                    </p>
                  </div>
                </div>
              </div>
            ))}
            {filteredMessages.length === 0 && (
              <div className="text-center py-8">
                <p className="text-gray-500 mb-4">No messages found</p>
                <Button
                  variant="outline"
                  onClick={() => setIsComposeOpen(true)}
                >
                  Compose New Message
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Recent Conversations */}
      {conversations.length > 0 && (
        <Card>
          <CardHeader className={compactView ? "p-4" : "p-6"}>
            <CardTitle className={compactView ? "text-lg" : "text-xl"}>
              Recent Conversations
            </CardTitle>
          </CardHeader>
          <CardContent className={compactView ? "p-4 pt-0" : "p-6 pt-0"}>
            <div className="space-y-2">
              {conversations
                .sort(
                  (a, b) => b.lastMessage.getTime() - a.lastMessage.getTime(),
                )
                .slice(0, compactView ? 3 : 5)
                .map((conversation) => (
                  <div
                    key={conversation.id}
                    className="p-2 border rounded-md cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
                    onClick={() => setSelectedConversation(conversation)}
                  >
                    <div className="flex items-center space-x-3">
                      <Avatar className="h-8 w-8">
                        <AvatarFallback className={getPlatformColor(conversation.platform)}>
                          {conversation.title.substring(0, 2).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-center mb-1">
                          <p className={`font-bold truncate ${compactView ? "text-sm" : "text-base"}`}>
                            {conversation.title}
                          </p>
                          {conversation.unreadCount > 0 && (
                            <Badge className="bg-blue-500 hover:bg-blue-600">
                              {conversation.unreadCount}
                            </Badge>
                          )}
                        </div>
                        <p className={`text-gray-600 dark:text-gray-400 truncate ${compactView ? "text-xs" : "text-sm"}`}>
                          {conversation.participants.join(", ")}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Last: {formatDate(conversation.lastMessage)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Compose Modal */}
      <Dialog open={isComposeOpen} onOpenChange={setIsComposeOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {selectedMessage
                ? `Reply to ${selectedMessage.from}`
                : "Compose New Message"}
            </DialogTitle>
          </DialogHeader>
          <MessageComposer
            onSubmit={(data) => {
              handleSendMessage(data);
              setIsComposeOpen(false);
            }}
            onCancel={() => setIsComposeOpen(false)}
            replyTo={selectedMessage || undefined}
          />
        </DialogContent>
      </Dialog>

      {/* Message Viewer Modal */}
      {selectedMessage && (
        <MessageViewer
          message={selectedMessage}
          onClose={() => {
            setSelectedMessage(null);
          }}
        />
      )}
    </div>
  );
};

export default CommunicationHub;
