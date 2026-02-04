import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/use-toast';
import { ConversationBubble } from '@/components/ui/conversation-bubble';
import { ConversationalOrchestration } from '../../../src/orchestration/ConversationalOrchestration';

interface ConversationMessage {
  id: string;
  text: string;
  sender: 'user' | 'agent';
  timestamp: Date;
  workflowId?: string;
}

interface OrchestrationInterfaceProps {
  userContext?: {
    businessType?: string;
    companySize?: 'solo' | 'small' | 'medium' | 'large';
    goals?: string[];
  };
}

export default function OrchestrationInterface({ userContext = {} }: OrchestrationInterfaceProps) {
  const [conversations, setConversations] = useState<ConversationMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeWorkflows, setActiveWorkflows] = useState<Map<string, any>>(new Map());
+
+  const orchestration = new ConversationalOrchestration();
+  const { toast } = useToast();

+  // Welcome message
+  useEffect(() => {
+    if (conversations.length === 0) {
+      setConversations([{
+        id: 'welcome',
+        text: "Hi! 🎉 I'm your AI business team coordinator. Just tell me what challenge you're facing - like 'I need help planning retirement' or 'customers stop buying after first visit' - and I'll automatically organize the perfect AI team to solve it. No technical knowledge required!",
+        sender: 'agent',
+        timestamp: new Date()
+      }]);
+    }
+  }, []);

+  // Quick action suggestions
+  const quickActions = [
+    { text: "Plan my retirement while growing my business", emoji: "🏦", type: "financial" },
+    { text: "Customers never buy a second time", emoji: "🔄", type: "retention" },
+    { text: "Spending 6 hours/month on receipts", emoji: "🧾", type: "automation" },
+    { text: "Marketing is inconsistent and takes too much time", emoji: "📱", type: "marketing" }
+  ];

+  const handleSendMessage = async () => {
+    if (!inputMessage.trim()) return;

+    const userMessage: ConversationMessage = {
+      id: Date.now().toString(),
+      text: inputMessage,
+      sender: 'user',
+      timestamp: new Date()
+    };

+    setConversations(prev => [...prev, userMessage]);
+    setInputMessage('');
+    setIsProcessing(true);

+    try {
+      const response = await orchestration.processUserMessage(
+        'current-user',
+        inputMessage,
+        {
+          companySize: userContext.companySize || 'solo',
+          industry: userContext.businessType || 'unknown',
+          goals: userContext.goals || ['time-saving', 'automation']
+        }
+      );

+      const agentMessage: ConversationMessage = {
+        id: (Date.now() + 1).toString(),
+        text: response.response,
+        sender: 'agent',
+        timestamp: new Date(),
+        workflowId: response.workflowId
+      };

+      setConversations(prev => [...prev, agentMessage]);

+      if (response.workflowId) {
+        toast({
+          title: "🚀 Automation Setup Complete!",
+          description: "Your AI business team is now working for you. Check back anytime for updates!",
+        });
+      }

+    } catch (error) {
+      const errorMessage: ConversationMessage = {
+        id: (Date.now() + 2).toString(),
+        text: "I'm having trouble processing that. Could you try rephrasing or ask about something specific like 'help with customer follow-ups' or 'retirement planning'?",
+        sender: 'agent',
+        timestamp: new Date()
+      };
+      setConversations(prev => [...prev, errorMessage]);
+    } finally {
+      setIsProcessing(false);
+    }
+  };

+  return (
+    <div className="max-w-4xl mx-auto p-4 space-y-6">
+      {/* Quick Action Cards */}
+      <Card className="bg-gradient-to-r from
