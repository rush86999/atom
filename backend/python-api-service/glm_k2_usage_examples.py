"""
GLM-4.6 and Kimi K2 Usage Examples

This file demonstrates how to use the newly added GLM-4.6 and Kimi K2 providers
in the ATOM BYOK system.
"""

from glm_46_handler_real import GLM46ServiceReal, get_glm_46_service_real
from kimi_k2_handler_real import KimiK2ServiceReal, get_kimi_k2_service_real
from user_api_key_service import get_user_api_key_service


def example_glm_46_usage():
    """Example usage of GLM-4.6 service"""
    print("🚀 GLM-4.6 (Zhipu AI) Usage Example")
    print("=" * 50)
    
    # Get service instance
    glm_service = get_glm_46_service_real()
    
    # Test connection (if API key is configured)
    print("1. Testing GLM-4.6 connection...")
    test_result = glm_service.test_connection()
    if test_result.get("success"):
        print(f"✅ Connection successful: {test_result.get('message')}")
    else:
        print(f"❌ Connection failed: {test_result.get('message')}")
        return
    
    # Example chat completion
    print("\n2. Chat completion example...")
    messages = [
        {"role": "system", "content": "你是一个有帮助的AI助手。"},
        {"role": "user", "content": "请用中文介绍一下你自己。"}
    ]
    
    chat_result = glm_service.chat_completion(
        messages=messages,
        model="glm-4.6",
        max_tokens=150,
        temperature=0.7
    )
    
    if chat_result.get("success"):
        print(f"✅ Chat response: {chat_result.get('content')}")
        print(f"📊 Usage: {chat_result.get('usage')}")
        print(f"📝 Model: {chat_result.get('model')}")
    else:
        print(f"❌ Chat failed: {chat_result.get('error')}")
    
    # Example embedding
    print("\n3. Embedding example...")
    texts = ["你好世界", "Hello world", "人工智能"]
    
    embed_result = glm_service.embedding(
        texts=texts,
        model="embedding-2"
    )
    
    if embed_result.get("success"):
        embeddings = embed_result.get("embeddings", [])
        print(f"✅ Generated {len(embeddings)} embeddings")
        if embeddings:
            print(f"📏 First embedding dimension: {len(embeddings[0].get('embedding', []))}")
        print(f"📊 Usage: {embed_result.get('usage')}")
    else:
        print(f"❌ Embedding failed: {embed_result.get('error')}")
    
    # Get model information
    print("\n4. Model information...")
    model_info = glm_service.get_model_info("glm-4.6")
    if model_info.get("success"):
        info = model_info.get("model_info", {})
        print(f"✅ Model: {info.get('name')}")
        print(f"📝 Description: {info.get('description')}")
        print(f"📏 Context Length: {info.get('context_length')}")
        print(f"💰 Input Cost: ${info.get('input_cost', 0)}/1K tokens")
        print(f"💰 Output Cost: ${info.get('output_cost', 0)}/1K tokens")
        print(f"🎯 Capabilities: {', '.join(info.get('capabilities', []))}")


def example_kimi_k2_usage():
    """Example usage of Kimi K2 service"""
    print("\n\n🚀 Kimi K2 (Moonshot AI) Usage Example")
    print("=" * 50)
    
    # Get service instance
    kimi_service = get_kimi_k2_service_real()
    
    # Test connection (if API key is configured)
    print("1. Testing Kimi K2 connection...")
    test_result = kimi_service.test_connection()
    if test_result.get("success"):
        print(f"✅ Connection successful: {test_result.get('message')}")
    else:
        print(f"❌ Connection failed: {test_result.get('message')}")
        return
    
    # Example chat completion
    print("\n2. Standard chat completion example...")
    messages = [
        {"role": "user", "content": "你好，请简单介绍一下你的能力。"}
    ]
    
    chat_result = kimi_service.chat_completion(
        messages=messages,
        model="moonshot-v1-8k",
        max_tokens=150,
        temperature=0.7
    )
    
    if chat_result.get("success"):
        print(f"✅ Chat response: {chat_result.get('content')}")
        print(f"📊 Usage: {chat_result.get('usage')}")
        print(f"📝 Model: {chat_result.get('model')}")
    else:
        print(f"❌ Chat failed: {chat_result.get('error')}")
    
    # Example long context chat
    print("\n3. Long context chat example...")
    long_messages = [
        {"role": "system", "content": "你是一个专门处理长文档的AI助手。"},
        {"role": "user", "content": "我有一个很长的文档需要分析..."}
    ]
    
    long_context_result = kimi_service.long_context_chat(
        messages=long_messages,
        model="moonshot-v1-128k",
        max_tokens=200,
        temperature=0.3
    )
    
    if long_context_result.get("success"):
        print(f"✅ Long context response: {long_context_result.get('content')[:100]}...")
        print(f"📊 Usage: {long_context_result.get('usage')}")
        print(f"📝 Model: {long_context_result.get('model')}")
    else:
        print(f"❌ Long context chat failed: {long_context_result.get('error')}")
    
    # Example document analysis
    print("\n4. Document analysis example...")
    document_text = """
    人工智能（Artificial Intelligence，AI）是一门新的技术科学。
    它是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的技术科学。
    该领域的研究包括机器人、语言识别、图像识别、自然语言处理和专家系统等。
    """
    
    doc_analysis_result = kimi_service.analyze_document(
        document_text=document_text,
        question="请分析这段关于人工智能的文本，提取关键信息。",
        model="moonshot-v1-128k"
    )
    
    if doc_analysis_result.get("success"):
        print(f"✅ Document analysis: {doc_analysis_result.get('content')[:200]}...")
        print(f"📏 Document length: {doc_analysis_result.get('document_length')} characters")
        print(f"📊 Usage: {doc_analysis_result.get('usage')}")
    else:
        print(f"❌ Document analysis failed: {doc_analysis_result.get('error')}")
    
    # Example reasoning chat
    print("\n5. Complex reasoning example...")
    reasoning_result = kimi_service.reasoning_chat(
        problem="如果一个房间里有3只猫，每只猫抓了2只老鼠，请问总共抓了多少只老鼠？请详细解释你的推理过程。",
        context="这是一个简单的数学逻辑问题。",
        model="moonshot-v1-32k"
    )
    
    if reasoning_result.get("success"):
        print(f"✅ Reasoning response: {reasoning_result.get('content')}")
        print(f"🧠 Type: {reasoning_result.get('reasoning_type')}")
    else:
        print(f"❌ Reasoning failed: {reasoning_result.get('error')}")
    
    # Get model information
    print("\n6. Model information...")
    models_to_check = ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]
    for model in models_to_check:
        model_info = kimi_service.get_model_info(model)
        if model_info.get("success"):
            info = model_info.get("model_info", {})
            print(f"✅ {info.get('name')}:")
            print(f"   📝 Context: {info.get('context_length')} tokens")
            print(f"   💰 Cost: ${info.get('input_cost', 0)}/1K in, ${info.get('output_cost', 0)}/1K out")
            print(f"   🎯 {', '.join(info.get('capabilities', []))}")


def example_byok_integration():
    """Example usage with BYOK system"""
    print("\n\n🔐 BYOK System Integration Example")
    print("=" * 50)
    
    # Get user API key service
    user_api_service = get_user_api_key_service()
    
    # Example user ID
    test_user_id = "example_user_123"
    
    # Show available providers
    print("1. Available providers in BYOK system:")
    from user_api_key_routes import AVAILABLE_AI_PROVIDERS
    
    for provider_key, provider_config in AVAILABLE_AI_PROVIDERS.items():
        print(f"   📋 {provider_config['name']}")
        print(f"      🎯 {', '.join(provider_config['capabilities'])}")
        print(f"      💰 Cost: {provider_config.get('cost_savings', 'Varies')}")
    
    # Example: Test configured keys (if any)
    print(f"\n2. Testing configured services for user {test_user_id}:")
    configured_services = user_api_service.list_user_services(test_user_id)
    
    if configured_services:
        for service in configured_services:
            test_result = user_api_service.test_api_key(test_user_id, service)
            print(f"   🔑 {service}: {'✅ Working' if test_result.get('success') else '❌ Failed'}")
    else:
        print("   📝 No services configured yet")
    
    print("\n3. To configure new providers:")
    print("   🌐 Web: Navigate to /settings and click 'AI Providers' tab")
    print("   🖥️  Desktop: Open Settings > AI Provider Settings")
    print("   🔑 Add your GLM-4.6 or Kimi K2 API keys")
    print("   ✅ Test connection to verify they work")


if __name__ == "__main__":
    print("🎯 GLM-4.6 and Kimi K2 Usage Examples")
    print("=" * 60)
    
    # Run examples
    try:
        example_glm_46_usage()
        example_kimi_k2_usage()
        example_byok_integration()
        
        print("\n\n🎉 Examples completed successfully!")
        print("\n📖 For more information:")
        print("   📄 Check GLM_K2_INTEGRATION_SUMMARY.md")
        print("   📖 Read BYOK_USER_GUIDE.md")
        print("   🔧 See handler source code for advanced usage")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("\n💡 Note: These examples require API keys to be configured")
        print("   Set GLM_4_6_API_KEY and KIMI_K2_API_KEY environment variables")
        print("   Or configure them through the BYOK system settings")