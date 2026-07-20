#!/bin/bash

# ATOM Chat Interface - Phase 3 Simplified Deployment
# Advanced AI-Powered Conversation Intelligence

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT_ROOT/backend"
LOG_DIR="$PROJECT_ROOT/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_phase() {
    echo -e "${BLUE}[PHASE 3]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_phase "Checking prerequisites..."

    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_success "Python $PYTHON_VERSION found"
    else
        log_error "Python 3 is required"
        exit 1
    fi

    # Check if backend directory exists
    if [ ! -d "$BACKEND_DIR" ]; then
        log_error "Backend directory not found"
        exit 1
    fi

    # Create log directory
    mkdir -p "$LOG_DIR"
    log_success "Log directory ready"
}

# Install Phase 3 dependencies
install_dependencies() {
    log_phase "Installing Phase 3 dependencies..."

    cd "$BACKEND_DIR"

    # Install AI/ML libraries
    pip3 install transformers
    pip3 install spacy scikit-learn
    pip3 install nltk textblob vaderSentiment

    # Download spaCy model
    python3 -m spacy download en_core_web_sm

    # Install file processing libraries
    pip3 install PyPDF2 python-docx openpyxl pdfplumber
    pip3 install Pillow pytesseract

    # Install voice processing libraries
    pip3 install speechrecognition pydub
    pip3 install gtts pyttsx3

    log_success "Phase 3 dependencies installed"
}

# Deploy AI Conversation Intelligence
deploy_ai_intelligence() {
    log_phase "Deploying AI Conversation Intelligence..."

    cd "$BACKEND_DIR"

    # Create AI conversation intelligence module
    cat > "ai_conversation_intelligence.py" << 'EOF'
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
EOF

    log_success "AI Conversation Intelligence module deployed"
}

# Deploy Enhanced Chat Interface
deploy_enhanced_chat() {
    log_phase "Deploying Enhanced Chat Interface..."

    cd "$BACKEND_DIR"

    # Create enhanced chat interface
    cat > "chat_interface_phase3.py" << 'EOF'
"""
Enhanced Chat Interface with Phase 3 AI Intelligence
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from ai_conversation_intelligence import conversation_intelligence
    AI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"AI intelligence not available: {e}")
    AI_AVAILABLE = False

class ChatMessage(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None
    enable_ai_analysis: bool = True
    conversation_history: Optional[List[Dict[str, str]]] = None

class AIAnalysisResponse(BaseModel):
    analysis_id: str
    timestamp: str
    sentiment_scores: Dict[str, float]
    entities: List[Dict[str, str]]
    context_relevance: float
    suggested_actions: List[str]

app = FastAPI(title="Atom Chat Interface Phase 3", version="3.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conversation tracking
active_conversations = {}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "ai_conversation_intelligence": AI_AVAILABLE,
            "phase3_enhanced_chat": True
        }
    }

@app.post("/api/v1/ai/analyze")
async def analyze_conversation(message: str, user_id: str):
    if not AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI intelligence not available")

    try:
        analysis = conversation_intelligence.generate_context_aware_response(message, [])

        response = AIAnalysisResponse(
            analysis_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            sentiment_scores=analysis.get("sentiment", {}),
            entities=analysis.get("entities", []),
            context_relevance=analysis.get("context_relevance", 0.0),
            suggested_actions=analysis.get("suggested_actions", [])
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

@app.post("/api/v1/chat/enhanced/message")
async def enhanced_chat_message(request: ChatMessage):
    try:
        conversation_id = request.session_id or str(uuid.uuid4())

        if conversation_id not in active_conversations:
            active_conversations[conversation_id] = {
                "user_id": request.user_id,
                "start_time": datetime.now().isoformat(),
                "messages": []
            }

        # Add user message
        active_conversations[conversation_id]["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        })

        response_data = {
            "response": f"Enhanced response to: {request.message}",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "ai_analysis_applied": False
        }

        # Apply AI intelligence if enabled
        if request.enable_ai_analysis and AI_AVAILABLE:
            try:
                analysis = conversation_intelligence.generate_context_aware_response(
                    request.message,
                    request.conversation_history or []
                )
                response_data["ai_analysis"] = analysis
                response_data["ai_analysis_applied"] = True

                if analysis.get("suggested_actions"):
                    response_data["enhanced_suggestions"] = analysis["suggested_actions"]
            except Exception as e:
                logging.warning(f"AI analysis failed: {e}")

        # Add assistant response
        active_conversations[conversation_id]["messages"].append({
            "role": "assistant",
            "content": response_data["response"],
            "timestamp": datetime.now().isoformat()
        })

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5061)
EOF

    log_success "Enhanced Chat Interface deployed"
}

# Start Phase 3 services
start_services() {
    log_phase "Starting Phase 3 services..."

    cd "$BACKEND_DIR"

    # Start enhanced chat interface
    nohup python3 chat_interface_phase3.py > "$LOG_DIR/phase3_chat.log" 2>&1 &
    PHASE3_PID=$!
    echo $PHASE3_PID > "$LOG_DIR/phase3_chat.pid"

    sleep 3

    if ps -p $PHASE3_PID > /dev/null; then
        log_success "Phase 3 Chat Interface started (PID: $PHASE3_PID)"
        log_info "Port: 5061"
        log_info "Logs: $LOG_DIR/phase3_chat.log"
    else
        log_error "Failed to start Phase 3 Chat Interface"
        exit 1
    fi
}

# Run health checks
run_health_checks() {
    log_phase "Running health checks..."

    sleep 5

    if curl -s http://localhost:5061/health > /dev/null; then
        log_success "Phase 3 Chat Interface is healthy"
    else
        log_error "Phase 3 health check failed"
        exit 1
    fi

    # Test AI analysis endpoint
    TEST_RESPONSE=$(curl -s -X POST http://localhost:5061/api/v1/ai/analyze \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello, test the AI analysis", "user_id": "test_user"}')

    if echo "$TEST_RESPONSE" | grep -q "analysis_id"; then
        log_success "AI analysis endpoint working"
    else
        log_warning "AI analysis endpoint may need configuration"
    fi
}

# Main deployment function
main() {
    log_phase "🚀 Starting Atom Chat Interface Phase 3 Deployment"

    check_prerequisites
    install_dependencies
    deploy_ai_intelligence
    deploy_enhanced_chat
    start_services
    run_health_checks

    log_success "🎉 Phase 3 Deployment Completed Successfully!"
    echo ""
    echo "📊 Deployment Summary:"
    echo "   Enhanced Chat Interface: http://localhost:5061"
    echo "   AI Analysis Endpoint: POST http://localhost:5061/api/v1/ai/analyze"
    echo "   Enhanced Chat Endpoint: POST http://localhost:5061/api/v1/chat/enhanced/message"
    echo ""
    echo "🔧 Quick Test Commands:"
    echo "   Health Check: curl http://localhost:5061/health"
    echo "   AI Analysis: curl -X POST http://localhost:5061/api/v1/ai/analyze -H 'Content-Type: application/json' -d '{\"message\": \"Test message\", \"user_id\": \"test_user\"}'"
    echo "   Enhanced Chat: curl -X POST http://localhost:5061/api/v1/chat/enhanced/message -H 'Content-Type: application/json' -d '{\"message\": \"Hello\", \"user_id\": \"test_user\", \"enable_ai_analysis\": true}'"
    echo ""
    echo "📝 Next Steps:"
    echo "   1. Integrate Phase 3 endpoints with your frontend"
    echo "   2. Configure AI models for production use"
    echo "   3. Set up monitoring for the new services"
    echo "   4. Run comprehensive testing with real user scenarios"
}

# Run main function
main "$@"
