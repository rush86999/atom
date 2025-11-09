"""
Kimi K2 Service Handler

This module provides integration with Moonshot AI's Kimi K2 model API.
Kimi K2 is a long-context reasoning model with up to 200K context window.
"""

import os
import httpx
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class KimiK2ServiceReal:
    """Real Kimi K2 service implementation using Moonshot AI API"""

    def __init__(self):
        self.api_key = os.getenv("KIMI_K2_API_KEY", "")
        self.base_url = "https://api.moonshot.cn/v1"
        self.default_model = "moonshot-v1-8k"
        self.timeout = 60

    def test_connection(self) -> Dict[str, Any]:
        """Test Kimi K2 API connection"""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "message": "Kimi K2 API key not configured"
                }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Test with a minimal request
            test_payload = {
                "model": self.default_model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5
            }
            
            with httpx.Client(timeout=10) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=test_payload
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": "Kimi K2 API connection successful",
                        "details": {"model": self.default_model, "provider": "Moonshot AI"}
                    }
                else:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("error", {}).get("message", error_detail)
                    except:
                        pass
                    
                    return {
                        "success": False,
                        "message": f"Kimi K2 API test failed: {error_detail}",
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "message": f"Kimi K2 connection test error: {str(e)}"
            }

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create chat completion using Kimi K2"""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Kimi K2 API key not configured"
                }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model or self.default_model,
                "messages": messages,
                "temperature": temperature,
                "stream": stream
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            # Add any additional parameters
            payload.update(kwargs)
            
            with httpx.Client(timeout=self.timeout) as client:
                if stream:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        stream=True
                    )
                    return {
                        "success": True,
                        "stream": True,
                        "response": response
                    }
                else:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return {
                            "success": True,
                            "content": result["choices"][0]["message"]["content"],
                            "usage": result.get("usage", {}),
                            "model": result.get("model", model or self.default_model),
                            "finish_reason": result["choices"][0].get("finish_reason")
                        }
                    else:
                        error_detail = response.text
                        try:
                            error_json = response.json()
                            error_detail = error_json.get("error", {}).get("message", error_detail)
                        except:
                            pass
                        
                        return {
                            "success": False,
                            "error": f"Kimi K2 API error: {error_detail}",
                            "status_code": response.status_code
                        }
                        
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Kimi K2 API request timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Kimi K2 service error: {str(e)}"
            }

    def long_context_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.3,  # Lower temperature for long context reasoning
        **kwargs
    ) -> Dict[str, Any]:
        """Chat completion optimized for long context reasoning"""
        # Use the 128K model for long context by default
        long_context_model = model or "moonshot-v1-128k"
        
        return self.chat_completion(
            messages=messages,
            model=long_context_model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )

    def get_models(self) -> Dict[str, Any]:
        """Get list of available Kimi K2 models"""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Kimi K2 API key not configured"
                }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            with httpx.Client(timeout=10) as client:
                response = client.get(
                    f"{self.base_url}/models",
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "models": result.get("data", [])
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get Kimi K2 models: HTTP {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Kimi K2 models list error: {str(e)}"
            }

    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """Get information about a specific Kimi K2 model"""
        available_models = {
            "moonshot-v1-8k": {
                "name": "Kimi K2 - 8K",
                "description": "Standard version with 8K context window",
                "context_length": 8000,
                "input_cost": 0.012,  # per 1K tokens (estimated)
                "output_cost": 0.036,  # per 1K tokens (estimated)
                "capabilities": ["chat", "reasoning"]
            },
            "moonshot-v1-32k": {
                "name": "Kimi K2 - 32K",
                "description": "Extended context with 32K context window",
                "context_length": 32000,
                "input_cost": 0.024,
                "output_cost": 0.072,
                "capabilities": ["chat", "reasoning", "long_context"]
            },
            "moonshot-v1-128k": {
                "name": "Kimi K2 - 128K",
                "description": "Long context version with 128K context window",
                "context_length": 128000,
                "input_cost": 0.096,
                "output_cost": 0.288,
                "capabilities": ["chat", "reasoning", "long_context", "document_analysis"]
            }
        }
        
        model_name = model_name or self.default_model
        if model_name in available_models:
            return {
                "success": True,
                "model_info": available_models[model_name]
            }
        else:
            return {
                "success": False,
                "error": f"Model {model_name} not found in Kimi K2 model list"
            }

    def analyze_document(
        self,
        document_text: str,
        question: str = "Please analyze this document and provide key insights.",
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze a document using the long context model"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant specialized in document analysis. Provide comprehensive and insightful analysis of the given text."
                },
                {
                    "role": "user",
                    "content": f"Document:\n\n{document_text}\n\n{question}"
                }
            ]
            
            # Use 128K model for document analysis
            analysis_model = model or "moonshot-v1-128k"
            
            result = self.chat_completion(
                messages=messages,
                model=analysis_model,
                max_tokens=2000,
                temperature=0.3
            )
            
            if result.get("success"):
                result["analysis_type"] = "document_analysis"
                result["document_length"] = len(document_text)
                result["context_used"] = len(document_text) + len(question)
                
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Document analysis error: {str(e)}"
            }

    def reasoning_chat(
        self,
        problem: str,
        context: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Chat completion optimized for complex reasoning tasks"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant specialized in complex reasoning and problem-solving. Think step by step and provide detailed, logical explanations for your answers."
                },
                {
                    "role": "user",
                    "content": f"Problem: {problem}"
                }
            ]
            
            if context:
                messages.insert(1, {
                    "role": "system",
                    "content": f"Context: {context}"
                })
            
            # Use 32K model for reasoning tasks
            reasoning_model = model or "moonshot-v1-32k"
            
            result = self.chat_completion(
                messages=messages,
                model=reasoning_model,
                max_tokens=3000,
                temperature=0.2  # Very low temperature for consistent reasoning
            )
            
            if result.get("success"):
                result["reasoning_type"] = "complex_problem_solving"
                
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Reasoning chat error: {str(e)}"
            }


# Global instance for easy access
kimi_k2_service_real = KimiK2ServiceReal()


def get_kimi_k2_service_real() -> KimiK2ServiceReal:
    """Get the global Kimi K2 service instance"""
    return kimi_k2_service_real


# Example usage and testing
if __name__ == "__main__":
    # Test the service
    service = KimiK2ServiceReal()
    
    # Test connection
    print("Testing Kimi K2 connection...")
    result = service.test_connection()
    print(f"Connection test: {result}")
    
    if result.get("success"):
        # Test chat completion
        print("\nTesting chat completion...")
        messages = [
            {"role": "user", "content": "你好，请简单介绍一下你的能力。"}
        ]
        
        chat_result = service.chat_completion(messages, max_tokens=100)
        if chat_result.get("success"):
            print(f"Chat response: {chat_result.get('content')}")
            print(f"Usage: {chat_result.get('usage')}")
        else:
            print(f"Chat error: {chat_result.get('error')}")
        
        # Test long context
        print("\nTesting long context capabilities...")
        long_text = "这是一个很长的文本..." * 1000  # Simulate long text
        long_context_result = service.long_context_chat(
            messages=[
                {"role": "user", "content": f"请分析这段文字：{long_text[:5000]}..."}
            ],
            model="moonshot-v1-128k",
            max_tokens=200
        )
        
        if long_context_result.get("success"):
            print(f"Long context response: {long_context_result.get('content')[:100]}...")
        else:
            print(f"Long context error: {long_context_result.get('error')}")
        
        # Test reasoning
        print("\nTesting reasoning capabilities...")
        reasoning_result = service.reasoning_chat(
            problem="如果一个房间里有3只猫，每只猫抓了2只老鼠，请问总共有多少只老鼠被抓？请详细解释你的推理过程。"
        )
        
        if reasoning_result.get("success"):
            print(f"Reasoning response: {reasoning_result.get('content')}")
        else:
            print(f"Reasoning error: {reasoning_result.get('error')}")
    
    print("\nKimi K2 service test completed")