from celery import shared_task
import logging
from typing import Dict, Any, List, Optional
import os
import openai
import json

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def generate_text_with_ai(self, prompt: str, model: str = "gpt-4", temperature: float = 0.7, max_tokens: int = 1000) -> Dict[str, Any]:
    """
    Generate text using AI models
    """
    try:
        logger.info(f"Generating text with AI model: {model}")

        # Get OpenAI API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        # Initialize OpenAI client
        client = openai.OpenAI(api_key=api_key)

        # Make API call
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        result = {
            "text": response.choices[0].message.content,
            "model": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            "finish_reason": response.choices[0].finish_reason
        }

        logger.info(f"AI text generation completed successfully")
        return result

    except Exception as e:
        logger.error(f"Error generating text with AI: {e}")
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def analyze_sentiment(self, text: str) -> Dict[str, Any]:
    """
    Analyze sentiment of text using AI
    """
    try:
        logger.info(f"Analyzing sentiment for text: {text[:100]}...")

        prompt = f"""
        Analyze the sentiment of the following text and provide a JSON response with:
        - sentiment: positive, negative, or neutral
        - confidence: float between 0 and 1
        - key_phrases: list of key phrases that influenced the sentiment

        Text: {text}

        Respond with JSON only.
        """

        result = generate_text_with_ai(prompt, model="gpt-3.5-turbo", temperature=0.1, max_tokens=200)

        try:
            sentiment_data = json.loads(result["text"])
            return sentiment_data
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "sentiment": "neutral",
                "confidence": 0.5,
                "key_phrases": []
            }

    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def summarize_text(self, text: str, max_length: int = 200) -> Dict[str, Any]:
    """
    Summarize text using AI
    """
    try:
        logger.info(f"Summarizing text of length: {len(text)}")

        prompt = f"""
        Please provide a concise summary of the following text.
        The summary should be no more than {max_length} words.

        Text: {text}

        Summary:
        """

        result = generate_text_with_ai(prompt, model="gpt-3.5-turbo", temperature=0.3, max_tokens=300)

        return {
            "summary": result["text"].strip(),
            "original_length": len(text),
            "summary_length": len(result["text"]),
            "compression_ratio": len(result["text"]) / len(text) if len(text) > 0 else 0
        }

    except Exception as e:
        logger.error(f"Error summarizing text: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def extract_keywords(self, text: str, max_keywords: int = 10) -> Dict[str, Any]:
    """
    Extract keywords from text using AI
    """
    try:
        logger.info(f"Extracting keywords from text")

        prompt = f"""
        Extract the top {max_keywords} most important keywords from the following text.
        Return the keywords as a JSON array of strings.

        Text: {text}

        Keywords:
        """

        result = generate_text_with_ai(prompt, model="gpt-3.5-turbo", temperature=0.1, max_tokens=100)

        try:
            keywords = json.loads(result["text"])
            return {
                "keywords": keywords,
                "count": len(keywords),
                "text_length": len(text)
            }
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            keywords = result["text"].strip().split('\n')
            keywords = [k.strip('- ').strip() for k in keywords if k.strip()]
            return {
                "keywords": keywords[:max_keywords],
                "count": len(keywords[:max_keywords]),
                "text_length": len(text)
            }

    except Exception as e:
        logger.error(f"Error extracting keywords: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def classify_text(self, text: str, categories: List[str]) -> Dict[str, Any]:
    """
    Classify text into predefined categories using AI
    """
    try:
        logger.info(f"Classifying text into {len(categories)} categories")

        categories_str = ', '.join(categories)
        prompt = f"""
        Classify the following text into one of these categories: {categories_str}

        Return a JSON object with:
        - category: the most appropriate category
        - confidence: confidence score between 0 and 1
        - explanation: brief explanation of why this category was chosen

        Text: {text}

        Classification:
        """

        result = generate_text_with_ai(prompt, model="gpt-3.5-turbo", temperature=0.1, max_tokens=150)

        try:
            classification = json.loads(result["text"])
            return classification
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "category": categories[0] if categories else "unknown",
                "confidence": 0.5,
                "explanation": "Automatic classification"
            }

    except Exception as e:
        logger.error(f"Error classifying text: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def translate_text(self, text: str, target_language: str, source_language: Optional[str] = None) -> Dict[str, Any]:
    """
    Translate text to target language using AI
    """
    try:
        logger.info(f"Translating text to {target_language}")

        source_info = f"from {source_language} " if source_language else ""
        prompt = f"""
        Translate the following text {source_info}to {target_language}.
        Provide only the translated text without any additional commentary.

        Text: {text}

        Translation:
        """

        result = generate_text_with_ai(prompt, model="gpt-3.5-turbo", temperature=0.1, max_tokens=len(text) * 2)

        return {
            "translated_text": result["text"].strip(),
            "target_language": target_language,
            "source_language": source_language or "auto",
            "original_length": len(text),
            "translated_length": len(result["text"])
        }

    except Exception as e:
        logger.error(f"Error translating text: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def generate_embeddings(self, text: str, model: str = "text-embedding-ada-002") -> Dict[str, Any]:
    """
    Generate embeddings for text using OpenAI
    """
    try:
        logger.info(f"Generating embeddings for text")

        # Get OpenAI API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        # Initialize OpenAI client
        client = openai.OpenAI(api_key=api_key)

        # Generate embeddings
        response = client.embeddings.create(
            input=text,
            model=model
        )

        return {
            "embeddings": response.data[0].embedding,
            "model": model,
            "text_length": len(text),
            "embedding_dimensions": len(response.data[0].embedding)
        }

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise self.retry(exc=e, countdown=30)
