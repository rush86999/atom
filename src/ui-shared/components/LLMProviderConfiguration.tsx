import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Key, Settings, Zap, Shield, ExternalLink, CheckCircle, AlertCircle,
  ExternalLink as ArrowForwardIcon, Save, MessageSquare, DollarSign, Clock
} from "lucide-react";

interface LLMProvider {
  id: string;
  name: string;
  displayName: string;
  description: string;
  endpoint: string;
  models: string[];
  features: string[];
  cost: {
    input: number;
    output: number;
    currency: string;
  };
  apiKeyPattern: RegExp;
  exampleKey: string;
  docsUrl: string;
  isLocal?: boolean;
}

const PROVIDERS: LLMProvider[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    displayName: 'OpenAI GPT',
    description: 'Latest GPT models for complex reasoning and creative tasks',
    endpoint: 'https://api.openai.com/v1',
    models: ['gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
    features: ['Complex Reasoning', 'Code Generation', 'Creative Writing', 'Analysis'],
    cost: { input: 0.03, output: 0.06, currency: 'USD' },
    apiKeyPattern: /^sk-[a-zA-Z0-9]{32,}$/,
    exampleKey: 'sk-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789',
    docsUrl: 'https://platform.openai.com/api-keys'
  },
  {
    id: 'claude',
    name: 'Anthropic Claude',
    displayName: 'Claude-3',
    description: 'Advanced reasoning and analysis with large context windows',
    endpoint: 'https://api.anthropic.com/v1/messages',
    models: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'],
    features: ['Document Analysis', 'Long Context', 'Creative Tasks', 'Advanced Reasoning'],
    cost: { input: 0.008, output: 0.024, currency: 'USD' },
    apiKeyPattern: /^sk-ant-[a-zA-Z0-9]{92}$/,
    exampleKey: 'sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfGhIjKlMnOpQrStUvWxYz0123456',
    docsUrl: 'https://console.anthropic.com/settings/keys'
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    displayName: 'Gemini Pro',
    description: 'Multimodal capabilities and Google integration',
    endpoint: 'https://generativelanguage.googleapis.com/v1beta',
    models: ['gemini-pro', 'gemini-pro-vision'],
    features: ['Multimodal', 'Fast Response', 'Large Context', 'Google Integration'],
    cost: { input: 0.0005, output: 0.0015, currency: 'USD' },
    apiKeyPattern: /^AIzaSy[a-zA-Z0-9_-]{34,}$/,
    exampleKey: 'AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz012345678',
    docsUrl: 'https://makersuite.google.com/app/apikey'
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    displayName: 'OpenRouter',
    description: 'Access to 100+ models including Llama, Mistral, Claude, and more',
    endpoint: 'https://openrouter.ai/api/v1',
    models: ['meta-llama/llama-2-70b', 'mistral/mixtral-8x7b', 'anthropic/claude-3-sonnet'],
    features: ['Model Switching', 'Universal Access', 'Cost Optimization'],
    cost: { input: 0.0005, output:
