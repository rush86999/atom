"""
GLM-4.6 Service Handler

This module provides integration with Zhipu AI's GLM-4.6 model API.
GLM-4.6 is an advanced Chinese language model with strong multilingual capabilities.
"""

import os
import httpx
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class GLM46ServiceReal:
    """Real GLM-4.6 service implementation using Zhipu AI API"""

    def __init__(self):
        self.api_key = os.getenv("GLM_4_6_API_KEY", "")
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
        self.default_model = "glm-4.6"
        self.timeout = 60

    def test_connection(self) -> Dict[str, Any]:
        """Test GLM-4.6 API connection"""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "message": "GLM-4.6 API key not configured"
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
                        "message": "GLM-4.6 API connection successful",
                        "details": {"model": self.default_model, "provider": "Zhipu AI"}
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
                        "message": f"GLM-4.6 API test failed: {error_detail}",
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "message": f"GLM-4.6 connection test error: {str(e)}"
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
        """Create chat completion using GLM-4.6"""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "GLM-4.6 API key not configured"
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
                            "error": f"GLM-4.6 API error: {error_detail}",
                            "status_code": response.status_code
                        }
                        
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "GLM-4.6 API request timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"GLM-4.6 service error: {str(e)}"
            }

    def embedding(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create embeddings using GLM-4.6"""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "GLM-4.6 API key not configured"
                }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model or "embedding-2",  # GLM embedding model
                "input": texts
            }
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "embeddings": result["data"],
                        "usage": result.get("usage", {}),
                        "model": result.get("model", model or "embedding-2")
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
                        "error": f"GLM-4.6 embedding API error: {error_detail}",
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"GLM-4.6 embedding error: {str(e)}"
            }

    def get_models(self) -> Dict[str, Any]:
        """Get list of available GLM models"""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "GLM-4.6 API key not configured"
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
                        "error": f"Failed to get GLM models: HTTP {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"GLM models list error: {str(e)}"
            }

    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """Get information about a specific GLM model"""
        available_models = {
            "glm-4.6": {
                "name": "GLM-4.6",
                "description": "Advanced Chinese language model with strong reasoning capabilities",
                "context_length": 128000,
                "input_cost": 0.005,  # per 1K tokens (estimated)
                "output_cost": 0.015,  # per 1K tokens (estimated)
                "capabilities": ["chat", "reasoning", "function_calling", "multilingual"]
            },
            "glm-4": {
                "name": "GLM-4",
                "description": "General purpose language model",
                "context_length": 128000,
                "input_cost": 0.003,
                "output_cost": 0.009,
                "capabilities": ["chat", "reasoning"]
            },
            "glm-4-air": {
                "name": "GLM-4-Air",
                "description": "Lightweight version for faster inference",
                "context_length": 128000,
                "input_cost": 0.001,
                "output_cost": 0.003,
                "capabilities": ["chat"]
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
                "error": f"Model {model_name} not found in GLM model list"
            }


# Global instance for easy access
glm_46_service_real = GLM46ServiceReal()


def get_glm_46_service_real() -> GLM46ServiceReal:
    """Get the global GLM-4.6 service instance"""
    return glm_46_service_real


# Example usage and testing
if __name__ == "__main__":
    # Test the service
    service = GLM46ServiceReal()
    
    # Test connection
    print("Testing GLM-4.6 connection...")
    result = service.test_connection()
    print(f"Connection test: {result}")
    
    if result.get("success"):
        # Test chat completion
        print("\nTesting chat completion...")
        messages = [
            {"role": "user", "content": "你好，请介绍一下你自己。"}
        ]
        
        chat_result = service.chat_completion(messages, max_tokens=100)
        if chat_result.get("success"):
            print(f"Chat response: {chat_result.get('content')}")
            print(f"Usage: {chat_result.get('usage')}")
        else:
            print(f"Chat error: {chat_result.get('error')}")
        
        # Test embedding
        print("\nTesting embedding...")
        texts = ["Hello world", "你好世界"]
        
        embed_result = service.embedding(texts)
        if embed_result.get("success"):
            embeddings = embed_result.get("embeddings", [])
            print(f"Generated {len(embeddings)} embeddings")
            print(f"First embedding dimension: {len(embeddings[0].get('embedding', [])) if embeddings else 0}")
        else:
            print(f"Embedding error: {embed_result.get('error')}")
    
    print("\nGLM-4.6 service test completed")