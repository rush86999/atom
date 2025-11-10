
# Intelligent Routing API Integration Guide

## Overview
The intelligent routing system automatically selects the optimal AI provider based on:
- Task type detection (code, Chinese language, long context, etc.)
- Cost optimization (up to 98% savings)
- User's configured providers
- Context length requirements
- Provider specializations

## API Endpoints

### 1. Task Analysis
POST /api/v1/intelligent/analyze-task
Analyze task type without provider selection

Request:
{
    "prompt": "User input text",
    "context_length": 1000
}

Response:
{
    "success": true,
    "task_analysis": {
        "detected_tasks": ["code_generation", "reasoning"],
        "primary_task": "code_generation",
        "task_count": 2
    }
}

### 2. Intelligent Provider Selection
POST /api/v1/intelligent/select-provider
Select optimal provider with full routing analysis

Request:
{
    "user_id": "user123",
    "prompt": "Write a Python function",
    "context_length": 500,
    "user_preferences": {
        "cost_priority": "high"
    }
}

Response:
{
    "success": true,
    "selected_provider": {
        "id": "deepseek",
        "name": "DeepSeek AI",
        "model": "deepseek-coder",
        "configured": true,
        "cost_savings": 98,
        "score": 4.5
    },
    "routing_analysis": {
        "detected_tasks": ["code_generation"],
        "selection_reasoning": "Selected for optimal cost-effectiveness"
    }
}

### 3. Cost Analysis
GET /api/v1/intelligent/cost-analysis/{user_id}
Get cost optimization recommendations

Response:
{
    "success": true,
    "cost_analysis": {
        "configured_count": 3,
        "total_potential_savings": 98,
        "recommendations": [
            "Add DeepSeek AI for 98% cost savings",
            "Add GLM-4.6 for Chinese language optimization"
        ]
    }
}

## Frontend Integration

### React Component Example
```jsx
import { useState, useEffect } from 'react';

function IntelligentAIAgent({ userId }) {
    const [routing, setRouting] = useState(null);
    const [loading, setLoading] = useState(false);
    
    const processInput = async (prompt) => {
        setLoading(true);
        
        try {
            const response = await fetch('/api/v1/intelligent/select-provider', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    prompt: prompt,
                    context_length: getConversationLength()
                })
            });
            
            const result = await response.json();
            if (result.success) {
                setRouting(result.selected_provider);
                // Use selected provider for AI request
                await makeAIRequest(prompt, result.selected_provider);
            }
        } catch (error) {
            console.error('Routing failed:', error);
        } finally {
            setLoading(false);
        }
    };
    
    return (
        <div className="intelligent-ai-agent">
            {routing && (
                <div className="routing-info">
                    <span>Using: {routing.name}</span>
                    <span>Model: {routing.model}</span>
                    <span>Savings: {routing.cost_savings}%</span>
                </div>
            )}
            {/* Your AI chat interface */}
        </div>
    );
}
```

## Provider Specializations

### GLM-4.6 (Zhipu AI)
- **Best for**: Chinese language, multilingual tasks
- **Cost savings**: 85-90%
- **Specialization**: Chinese language optimization

### Kimi K2 (Moonshot AI)  
- **Best for**: Long context, document analysis
- **Cost savings**: 70-80%
- **Specialization**: 200K context window

### DeepSeek AI
- **Best for**: Code generation, general tasks
- **Cost savings**: 96-98%
- **Specialization**: Code optimization

### Google Gemini
- **Best for**: Embeddings, multimodal tasks
- **Cost savings**: 93%
- **Specialization**: Vector embeddings

## Usage Tips

1. **Configure Multiple Providers**: Add 3+ providers for optimal routing
2. **Trust the Routing**: System automatically selects best provider
3. **Monitor Savings**: Track cost optimization over time
4. **Check Recommendations**: Review cost analysis suggestions
5. **Update Preferences**: Adjust user preferences as needed

## Benefits

- **Maximum Cost Savings**: Up to 98% reduction in AI costs
- **Optimal Performance**: Best provider for each task type
- **Automatic Fallback**: Multiple providers ensure reliability
- **Smart Routing**: Context-aware provider selection
- **User Control**: Override routing when needed
