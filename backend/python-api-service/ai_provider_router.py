"""
Intelligent AI Provider Router

This module implements intelligent routing logic to automatically select the best
AI provider based on task requirements, cost optimization, and performance.
"""

import re
from typing import Dict, List, Optional, Any
from enum import Enum

class TaskType(Enum):
    """Types of AI tasks with optimal provider mappings"""
    CHAT = "chat"
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    EMBEDDINGS = "embeddings"
    TRANSLATION = "translation"
    DOCUMENT_ANALYSIS = "document_analysis"
    LONG_CONTEXT = "long_context"
    CHINESE_LANGUAGE = "chinese_language"
    MULTILINGUAL = "multilingual"
    FUNCTION_CALLING = "function_calling"
    GENERAL = "general"

class ProviderPriority(Enum):
    """Provider priority levels based on cost and performance"""
    ULTRA_LOW_COST = 1    # 95%+ savings
    LOW_COST = 2          # 85-95% savings
    MEDIUM_COST = 3        # 70-85% savings
    HIGH_COST = 4          # 50-70% savings
    PREMIUM = 5           # <50% savings, premium features

class AIProviderRouter:
    """Intelligent router for optimal AI provider selection"""
    
    def __init__(self):
        self.available_providers = {
            "openai": {
                "name": "OpenAI",
                "priority": ProviderPriority.PREMIUM,
                "cost_savings": 0,
                "capabilities": ["chat", "embeddings", "moderation", "function_calling"],
                "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
                "specialization": "general_purpose",
                "reliability": 0.95
            },
            "deepseek": {
                "name": "DeepSeek AI", 
                "priority": ProviderPriority.ULTRA_LOW_COST,
                "cost_savings": 98,
                "capabilities": ["chat", "embeddings", "code_generation"],
                "models": ["deepseek-chat", "deepseek-coder"],
                "specialization": "code_generation",
                "reliability": 0.90
            },
            "anthropic": {
                "name": "Anthropic Claude",
                "priority": ProviderPriority.PREMIUM,
                "cost_savings": 0,
                "capabilities": ["chat", "reasoning", "long_context"],
                "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
                "specialization": "complex_reasoning",
                "reliability": 0.98
            },
            "google_gemini": {
                "name": "Google Gemini",
                "priority": ProviderPriority.ULTRA_LOW_COST,
                "cost_savings": 93,
                "capabilities": ["chat", "embeddings", "multimodal"],
                "models": ["gemini-2.0-flash", "gemini-2.0-pro", "text-embedding-004"],
                "specialization": "embeddings",
                "reliability": 0.92
            },
            "azure_openai": {
                "name": "Azure OpenAI",
                "priority": ProviderPriority.HIGH_COST,
                "cost_savings": -20,
                "capabilities": ["chat", "embeddings", "enterprise_security"],
                "models": ["gpt-4", "gpt-35-turbo"],
                "specialization": "enterprise",
                "reliability": 0.99
            },
            "glm_4_6": {
                "name": "GLM-4.6 (Zhipu AI)",
                "priority": ProviderPriority.LOW_COST,
                "cost_savings": 88,
                "capabilities": ["chat", "embeddings", "function_calling", "chinese_language", "multilingual"],
                "models": ["glm-4.6", "glm-4", "glm-4-air"],
                "specialization": "chinese_language",
                "reliability": 0.89
            },
            "kimi_k2": {
                "name": "Kimi K2 (Moonshot AI)",
                "priority": ProviderPriority.MEDIUM_COST,
                "cost_savings": 75,
                "capabilities": ["chat", "long_context", "reasoning", "document_analysis"],
                "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
                "specialization": "long_context",
                "reliability": 0.87
            }
        }
        
        # Task to provider mappings
        self.task_provider_mapping = {
            TaskType.CODE_GENERATION: ["deepseek", "glm_4_6", "openai"],
            TaskType.CHINESE_LANGUAGE: ["glm_4_6", "deepseek", "openai"],
            TaskType.LONG_CONTEXT: ["kimi_k2", "anthropic", "glm_4_6"],
            TaskType.DOCUMENT_ANALYSIS: ["kimi_k2", "anthropic", "glm_4_6"],
            TaskType.EMBEDDINGS: ["google_gemini", "glm_4_6", "deepseek"],
            TaskType.REASONING: ["anthropic", "kimi_k2", "openai"],
            TaskType.MULTILINGUAL: ["glm_4_6", "google_gemini", "openai"],
            TaskType.FUNCTION_CALLING: ["openai", "glm_4_6", "anthropic"],
            TaskType.TRANSLATION: ["glm_4_6", "deepseek", "google_gemini"],
            TaskType.GENERAL: ["deepseek", "google_gemini", "glm_4_6"]
        }
    
    def detect_task_type(self, prompt: str, context_length: int = 0, user_preferences: Dict = None) -> List[TaskType]:
        """
        Detect task type(s) from user prompt and context
        
        Args:
            prompt: User's input prompt
            context_length: Length of conversation context
            user_preferences: User's preferred settings
        
        Returns:
            List of detected task types ordered by relevance
        """
        task_indicators = {
            TaskType.CODE_GENERATION: [
                r'\b(code|coding|program|function|class|def\s+\w+|import\s+\w+)',
                r'(python|javascript|java|c\+\+|html|css)',
                r'(debug|fix|error|exception)',
                r'(algorithm|data\s+structure|variable|loop)'
            ],
            TaskType.CHINESE_LANGUAGE: [
                r'[\u4e00-\u9fff]',  # Chinese characters
                r'\b(chinese|mandarin|cantonese)\b',
                r'[你他是的我在有和这]'
            ],
            TaskType.LONG_CONTEXT: [
                r'(long.*context|document.*analysis)',
                r'(summarize|analyze.*long)',
                r'(context.*window|history)'
            ],
            TaskType.DOCUMENT_ANALYSIS: [
                r'(analyze|summarize|extract)',
                r'(document|pdf|article|paper)',
                r'(key.*point|insight|finding)'
            ],
            TaskType.EMBEDDINGS: [
                r'(embed|vector|similarity)',
                r'(search|recommend|classify)'
            ],
            TaskType.REASONING: [
                r'(why|how.*work|explain)',
                r'(reason|logic|problem.*solve)',
                r'(compare|contrast|evaluate)'
            ],
            TaskType.FUNCTION_CALLING: [
                r'(call.*function|execute.*command)',
                r'(calculate|compute|lookup)',
                r'(weather|news|stock.*price)'
            ],
            TaskType.TRANSLATION: [
                r'(translate|translation)',
                r'(in.*english|to.*chinese)',
                r'\b(en|zh|fr|es|de)\b'
            ]
        }
        
        detected_tasks = []
        prompt_lower = prompt.lower()
        
        # Check context length for long context tasks
        if context_length > 8000:
            detected_tasks.append(TaskType.LONG_CONTEXT)
        
        # Check each task type
        for task_type, patterns in task_indicators.items():
            for pattern in patterns:
                if re.search(pattern, prompt_lower, re.IGNORECASE):
                    detected_tasks.append(task_type)
                    break
        
        # Default to general if no specific tasks detected
        if not detected_tasks:
            detected_tasks.append(TaskType.GENERAL)
        
        return detected_tasks
    
    def rank_providers(self, task_types: List[TaskType], configured_providers: List[str], 
                     user_preferences: Dict = None) -> List[Dict[str, Any]]:
        """
        Rank providers based on task requirements and availability
        
        Args:
            task_types: List of detected task types
            configured_providers: List of providers user has configured
            user_preferences: User's provider preferences and constraints
        
        Returns:
            Ranked list of providers with scores
        """
        provider_scores = {}
        
        for provider_id in configured_providers:
            if provider_id not in self.available_providers:
                continue
                
            provider = self.available_providers[provider_id]
            score = 0
            reasons = []
            
            # Base score from cost optimization (lower cost = higher score)
            cost_score = (100 - provider["cost_savings"]) / 100
            score += cost_score * 0.3
            reasons.append(f"Cost: {provider['cost_savings']}% savings")
            
            # Reliability score
            score += provider["reliability"] * 0.2
            reasons.append(f"Reliability: {provider['reliability']:.0%}")
            
            # Task capability matching
            task_score = 0
            for task_type in task_types:
                if task_type.value in provider["capabilities"]:
                    task_score += 10
                elif task_type == TaskType.GENERAL:
                    task_score += 5
            
            score += task_score * 0.3
            reasons.append(f"Task Match: {task_score}")
            
            # Specialization bonus
            specialization_bonus = 0
            for task_type in task_types:
                preferred_providers = self.task_provider_mapping.get(task_type, [])
                if provider_id in preferred_providers[:2]:  # Top 2 preferred
                    specialization_bonus += 5
            
            score += specialization_bonus * 0.2
            reasons.append(f"Specialization: {specialization_bonus}")
            
            provider_scores[provider_id] = {
                "score": score,
                "reasons": reasons,
                "provider": provider
            }
        
        # Sort by score (descending)
        ranked_providers = sorted(
            provider_scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )
        
        return ranked_providers
    
    def select_optimal_provider(self, prompt: str, configured_providers: List[str], 
                            context_length: int = 0, user_preferences: Dict = None) -> Dict[str, Any]:
        """
        Select the optimal provider for a given request
        
        Args:
            prompt: User's input prompt
            configured_providers: List of providers user has configured
            context_length: Length of conversation context
            user_preferences: User's preferences
        
        Returns:
            Optimal provider with selection reasoning
        """
        if not configured_providers:
            return {
                "success": False,
                "error": "No providers configured",
                "suggestion": "Please configure at least one AI provider"
            }
        
        # Detect task types
        task_types = self.detect_task_type(prompt, context_length, user_preferences)
        
        # Rank providers
        ranked_providers = self.rank_providers(task_types, configured_providers, user_preferences)
        
        if not ranked_providers:
            return {
                "success": False,
                "error": "No suitable providers found",
                "suggestion": "Check your provider configurations"
            }
        
        # Select best provider
        best_provider_id, best_provider_data = ranked_providers[0]
        
        # Determine optimal model
        optimal_model = self._select_model(best_provider_data["provider"], task_types, context_length)
        
        return {
            "success": True,
            "provider_id": best_provider_id,
            "provider": best_provider_data["provider"],
            "model": optimal_model,
            "score": best_provider_data["score"],
            "reasons": best_provider_data["reasons"],
            "detected_tasks": [t.value for t in task_types],
            "selection_reasoning": f"Selected {best_provider_data['provider']['name']} for optimal balance of cost, capability, and reliability"
        }
    
    def _select_model(self, provider: Dict, task_types: List[TaskType], context_length: int) -> str:
        """Select the optimal model for a provider and task"""
        models = provider["models"]
        
        # Context length considerations
        if context_length > 100000:  # >100K tokens
            if provider["specialization"] == "long_context":
                # Look for largest context model
                large_context_models = [m for m in models if "128k" in m.lower() or "large" in m.lower()]
                if large_context_models:
                    return large_context_models[0]
        
        elif context_length > 30000:  # >30K tokens
            if provider["specialization"] == "long_context":
                medium_context_models = [m for m in models if "32k" in m.lower() or "medium" in m.lower()]
                if medium_context_models:
                    return medium_context_models[0]
        
        # Task-specific model selection
        if TaskType.CHINESE_LANGUAGE in task_types and provider["specialization"] == "chinese_language":
            # Look for best Chinese language model
            if "glm-4.6" in models:
                return "glm-4.6"
            elif any("glm-4" in m for m in models):
                chinese_models = [m for m in models if "glm-4" in m]
                return chinese_models[0]
        
        if TaskType.CODE_GENERATION in task_types and provider["specialization"] == "code_generation":
            # Look for code-specific models
            code_models = [m for m in models if "coder" in m.lower() or "code" in m.lower()]
            if code_models:
                return code_models[0]
        
        if TaskType.REASONING in task_types:
            # Look for best reasoning models
            reasoning_models = [m for m in models if any(x in m.lower() for x in ["opus", "4", "pro"])]
            if reasoning_models:
                return reasoning_models[0]
        
        # Default: return first (usually the best) model
        return models[0] if models else "default"
    
    def get_cost_optimization_report(self, configured_providers: List[str]) -> Dict[str, Any]:
        """
        Generate cost optimization report for configured providers
        
        Args:
            configured_providers: List of providers user has configured
        
        Returns:
            Cost optimization analysis and recommendations
        """
        analysis = {
            "configured_count": len(configured_providers),
            "providers": [],
            "total_potential_savings": 0,
            "recommendations": []
        }
        
        for provider_id in configured_providers:
            if provider_id in self.available_providers:
                provider = self.available_providers[provider_id]
                analysis["providers"].append({
                    "id": provider_id,
                    "name": provider["name"],
                    "cost_savings": provider["cost_savings"],
                    "specialization": provider["specialization"],
                    "reliability": provider["reliability"]
                })
                analysis["total_potential_savings"] = max(
                    analysis["total_potential_savings"],
                    provider["cost_savings"]
                )
        
        # Generate recommendations
        if len(configured_providers) < 3:
            analysis["recommendations"].append(
                "Configure additional providers for better cost optimization and fallback"
            )
        
        if not any(p in configured_providers for p in ["google_gemini", "deepseek"]):
            analysis["recommendations"].append(
                "Add Google Gemini (93% savings) or DeepSeek (98% savings) for maximum cost reduction"
            )
        
        if not "glm_4_6" in configured_providers:
            analysis["recommendations"].append(
                "Add GLM-4.6 for Chinese language optimization (88% savings)"
            )
        
        if not "kimi_k2" in configured_providers:
            analysis["recommendations"].append(
                "Add Kimi K2 for long-context document analysis (75% savings)"
            )
        
        return analysis


# Global router instance
ai_router = AIProviderRouter()


def get_ai_router() -> AIProviderRouter:
    """Get the global AI router instance"""
    return ai_router


# Example usage and testing
if __name__ == "__main__":
    router = AIProviderRouter()
    
    # Test scenarios
    test_scenarios = [
        {
            "prompt": "Write a Python function to sort a list of numbers",
            "configured_providers": ["deepseek", "glm_4_6", "openai"],
            "context_length": 100
        },
        {
            "prompt": "你好，请用中文回答我的问题",
            "configured_providers": ["glm_4_6", "deepseek", "google_gemini"],
            "context_length": 500
        },
        {
            "prompt": "Analyze this long document and provide key insights",
            "configured_providers": ["kimi_k2", "anthropic", "glm_4_6"],
            "context_length": 50000
        },
        {
            "prompt": "Create embeddings for this text",
            "configured_providers": ["google_gemini", "deepseek", "glm_4_6"],
            "context_length": 200
        }
    ]
    
    print("🚀 AI Provider Routing Test Scenarios")
    print("=" * 60)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n🧪 Test Scenario {i}:")
        print(f"Prompt: {scenario['prompt'][:50]}...")
        print(f"Configured Providers: {scenario['configured_providers']}")
        print(f"Context Length: {scenario['context_length']}")
        
        result = router.select_optimal_provider(
            prompt=scenario["prompt"],
            configured_providers=scenario["configured_providers"],
            context_length=scenario["context_length"]
        )
        
        if result["success"]:
            print(f"✅ Selected: {result['provider']['name']} ({result['provider_id']})")
            print(f"🤖 Model: {result['model']}")
            print(f"📊 Score: {result['score']:.2f}")
            print(f"🎯 Tasks: {', '.join(result['detected_tasks'])}")
            print(f"💡 Reasoning: {result['selection_reasoning']}")
        else:
            print(f"❌ Error: {result['error']}")
        
        print("-" * 40)
    
    # Test cost optimization report
    configured = ["openai", "deepseek", "google_gemini", "glm_4_6", "kimi_k2"]
    cost_report = router.get_cost_optimization_report(configured)
    
    print(f"\n💰 Cost Optimization Report:")
    print(f"Configured Providers: {cost_report['configured_count']}")
    print(f"Max Potential Savings: {cost_report['total_potential_savings']}%")
    print(f"Recommendations:")
    for rec in cost_report["recommendations"]:
        print(f"  • {rec}")
    
    print("\n🎯 AI Provider Router Test Complete!")