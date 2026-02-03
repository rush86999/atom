"""
Lightweight AI-Powered Conversation Intelligence Module
Basic sentiment analysis and entity extraction without heavy dependencies

Author: Atom Platform Engineering
Date: November 9, 2025
Version: 3.0.0-lightweight
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from textblob import TextBlob
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    AI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Lightweight AI libraries not available: {e}")
    AI_AVAILABLE = False

class LightweightConversationIntelligence:
    """Lightweight AI-powered conversation intelligence"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sentiment_analyzer = None

        if AI_AVAILABLE:
            self.initialize_ai_models()

    def initialize_ai_models(self):
        """Initialize lightweight AI models"""
        try:
            self.sentiment_analyzer = SentimentIntensityAnalyzer()
            self.logger.info("Lightweight AI models initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize lightweight AI models: {e}")

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text using multiple methods"""
        if not AI_AVAILABLE:
            return {"compound": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0}

        try:
            # VADER sentiment analysis
            vader_scores = self.sentiment_analyzer.polarity_scores(text)

            # TextBlob sentiment analysis
            blob = TextBlob(text)
            blob_sentiment = blob.sentiment

            # Combined sentiment score
            combined_score = {
                "vader_compound": vader_scores['compound'],
                "vader_positive": vader_scores['pos'],
                "vader_negative": vader_scores['neg'],
                "vader_neutral": vader_scores['neu'],
                "textblob_polarity": blob_sentiment.polarity,
                "textblob_subjectivity": blob_sentiment.subjectivity,
                "overall_sentiment": (vader_scores['compound'] + blob_sentiment.polarity) / 2
            }

            return combined_score

        except Exception as e:
            self.logger.error(f"Sentiment analysis failed: {e}")
            return {"error": str(e)}

    def extract_basic_entities(self, text: str) -> List[Dict[str, str]]:
        """Extract basic entities using regex patterns"""
        entities = []

        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        for email in emails:
            entities.append({
                "text": email,
                "label": "EMAIL",
                "type": "contact"
            })

        # URL pattern
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        for url in urls:
            entities.append({
                "text": url,
                "label": "URL",
                "type": "web"
            })

        # Phone number pattern (basic)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, text)
        for phone in phones:
            entities.append({
                "text": phone,
                "label": "PHONE",
                "type": "contact"
            })

        # Money pattern
        money_pattern = r'\$\d+(?:\.\d{2})?'
        money_amounts = re.findall(money_pattern, text)
        for money in money_amounts:
            entities.append({
                "text": money,
                "label": "MONEY",
                "type": "financial"
            })

        return entities

    def detect_intent_patterns(self, text: str) -> List[str]:
        """Detect intent patterns using keyword matching"""
        text_lower = text.lower()
        intents = []

        # Question intent
        if any(word in text_lower for word in ['what', 'when', 'where', 'why', 'how', 'who', '?']):
            intents.append("question")

        # Help intent
        if any(word in text_lower for word in ['help', 'assist', 'support', 'problem', 'issue']):
            intents.append("help_request")

        # Complaint intent
        if any(word in text_lower for word in ['complaint', 'angry', 'frustrated', 'upset', 'disappointed']):
            intents.append("complaint")

        # Positive feedback intent
        if any(word in text_lower for word in ['thank', 'great', 'awesome', 'amazing', 'love', 'perfect']):
            intents.append("positive_feedback")

        # Information request intent
        if any(word in text_lower for word in ['info', 'information', 'details', 'specs', 'specifications']):
            intents.append("information_request")

        return intents

    def generate_context_aware_response(self, message: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Generate context-aware response using lightweight analysis"""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "sentiment": self.analyze_sentiment(message),
            "entities": self.extract_basic_entities(message),
            "intents": self.detect_intent_patterns(message),
            "context_relevance": 0.0,
            "suggested_actions": []
        }

        # Calculate basic context relevance
        if conversation_history:
            recent_messages = conversation_history[-3:]  # Last 3 messages
            analysis["context_relevance"] = min(len(recent_messages) * 0.3, 1.0)

        # Generate suggested actions based on analysis
        sentiment_score = analysis["sentiment"].get("overall_sentiment", 0)

        if sentiment_score < -0.3:
            analysis["suggested_actions"].append("escalate_to_human")
            analysis["suggested_actions"].append("offer_apology")

        if "complaint" in analysis["intents"]:
            analysis["suggested_actions"].append("acknowledge_issue")
            analysis["suggested_actions"].append("provide_solution_options")

        if "help_request" in analysis["intents"]:
            analysis["suggested_actions"].append("provide_help_resources")
            analysis["suggested_actions"].append("offer_guided_assistance")

        if analysis["entities"]:
            analysis["suggested_actions"].append("use_extracted_entities")

        return analysis

# Global instance
conversation_intelligence = LightweightConversationIntelligence()
