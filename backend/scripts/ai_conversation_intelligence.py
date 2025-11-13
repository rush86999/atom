"""
AI-Powered Conversation Intelligence Module
Advanced NLU, sentiment analysis, and context-aware response generation
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from transformers import pipeline
    import spacy
    from sentence_transformers import SentenceTransformer
    from textblob import TextBlob
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    AI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"AI libraries not available: {e}")
    AI_AVAILABLE = False

class ConversationIntelligence:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.nlp = None
        self.sentiment_analyzer = None
        self.sentence_model = None

        if AI_AVAILABLE:
            self.initialize_ai_models()

    def initialize_ai_models(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
            self.sentiment_analyzer = SentimentIntensityAnalyzer()
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.logger.info("AI models initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize AI models: {e}")

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        if not AI_AVAILABLE:
            return {"compound": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0}

        try:
            vader_scores = self.sentiment_analyzer.polarity_scores(text)
            blob = TextBlob(text)
            blob_sentiment = blob.sentiment

            return {
                "vader_compound": vader_scores['compound'],
                "vader_positive": vader_scores['pos'],
                "vader_negative": vader_scores['neg'],
                "vader_neutral": vader_scores['neu'],
                "textblob_polarity": blob_sentiment.polarity,
                "textblob_subjectivity": blob_sentiment.subjectivity,
                "overall_sentiment": (vader_scores['compound'] + blob_sentiment.polarity) / 2
            }
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed: {e}")
            return {"error": str(e)}

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        if not AI_AVAILABLE or not self.nlp:
            return []

        try:
            doc = self.nlp(text)
            entities = []
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char
                })
            return entities
        except Exception as e:
            self.logger.error(f"Entity extraction failed: {e}")
            return []

    def generate_context_aware_response(self, message: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "sentiment": self.analyze_sentiment(message),
            "entities": self.extract_entities(message),
            "context_relevance": 0.0,
            "suggested_actions": []
        }

        if conversation_history:
            recent_messages = conversation_history[-3:]
            relevance_scores = []
            for prev_msg in recent_messages:
                if 'content' in prev_msg:
                    similarity = 0.8  # Placeholder for semantic similarity
                    relevance_scores.append(similarity)
            if relevance_scores:
                analysis["context_relevance"] = sum(relevance_scores) / len(relevance_scores)

        if analysis["sentiment"].get("overall_sentiment", 0) < -0.3:
            analysis["suggested_actions"].append("escalate_to_human")

        return analysis

conversation_intelligence = ConversationIntelligence()
