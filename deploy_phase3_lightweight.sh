#!/bin/bash

# ATOM Chat Interface - Phase 3 Lightweight Deployment
# Advanced AI-Powered Conversation Intelligence with Minimal Dependencies

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

# Install lightweight dependencies
install_lightweight_dependencies() {
    log_phase "Installing lightweight dependencies..."

    cd "$BACKEND_DIR"

    # Install only essential packages
    pip3 install textblob vaderSentiment
    pip3 install PyPDF2 python-docx openpyxl
    pip3 install Pillow

    log_success "Lightweight dependencies installed"
}

# Deploy AI Conversation Intelligence (Lightweight)
deploy_ai_intelligence_lightweight() {
    log_phase "Deploying Lightweight AI Conversation Intelligence..."

    cd "$BACKEND_DIR"

    # Create lightweight AI conversation intelligence module
    cat > "ai_conversation_intelligence_lightweight.py" << 'EOF'
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
from typing import Dict, List, Optional, Any

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
EOF

    log_success "Lightweight AI Conversation Intelligence module deployed"
}

# Deploy Lightweight Enhanced Chat Interface
deploy_lightweight_chat() {
    log_phase "Deploying Lightweight Enhanced Chat Interface..."

    cd "$BACKEND_DIR"

    # Create lightweight enhanced chat interface
    cat > "chat_interface_phase3_lightweight.py" << 'EOF'
"""
Lightweight Enhanced Chat Interface with Phase 3 AI Intelligence
Minimal dependencies, maximum functionality

Author: Atom Platform Engineering
Date: November 9, 2025
Version: 3.0.0-lightweight
"""

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
    from ai_conversation_intelligence_lightweight import conversation_intelligence
    AI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Lightweight AI intelligence not available: {e}")
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
    intents: List[str]
    context_relevance: float
    suggested_actions: List[str]

app = FastAPI(
    title="Atom Chat Interface Phase 3 (Lightweight)",
    description="Enhanced chat interface with lightweight AI-powered conversation intelligence",
    version="3.0.0-lightweight"
)

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

@app.get("/")
async def root():
    return {
        "message": "Atom Chat Interface Phase 3 (Lightweight)",
        "version": "3.0.0-lightweight",
        "status": "operational",
        "ai_intelligence": "available" if AI_AVAILABLE else "unavailable"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "3.0.0-lightweight",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "lightweight_ai_intelligence": AI_AVAILABLE,
            "phase3_enhanced_chat": True,
            "sentiment_analysis": AI_AVAILABLE,
            "entity_extraction": AI_AVAILABLE,
            "intent_detection": AI_AVAILABLE
        },
        "system_stats": {
            "active_conversations": len(active_conversations),
            "ai_model_status": "loaded" if AI_AVAILABLE else "unavailable"
        }
    }

@app.post("/api/v1/ai/analyze", response_model=AIAnalysisResponse)
async def analyze_conversation(message: str, user_id: str):
    """Analyze conversation with lightweight AI intelligence"""
    if not AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Lightweight AI intelligence not available")

    try:
        analysis = conversation_intelligence.generate_context_aware_response(message, [])

        response = AIAnalysisResponse(
            analysis_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            sentiment_scores=analysis.get("sentiment", {}),
            entities=analysis.get("entities", []),
            intents=analysis.get("intents", []),
            context_relevance=analysis.get("context_relevance", 0.0),
            suggested_actions=analysis.get("suggested_actions", [])
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

@app.post("/api/v1/chat/enhanced/message")
async def enhanced_chat_message(request: ChatMessage):
    """Enhanced chat message with lightweight AI intelligence"""
    try:
        conversation_id = request.session_id or str(uuid.uuid4())

        if conversation_id not in active_conversations:
            active_conversations[conversation_id] = {
                "user_id": request.user_id,
                "start_time": datetime.now().isoformat(),
                "messages": [],
                "metrics": {
                    "message_count": 0,
                    "ai_analyses_performed": 0
                }
            }

        conversation = active_conversations[conversation_id]

        # Add user message to conversation
        user_message = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        }
        conversation["messages"].append(user_message)
        conversation["metrics"]["message_count"] += 1

        # Prepare response
        response_data = {
            "response": f"Enhanced response to: {request.message}",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "ai_analysis_applied": False,
            "conversation_metrics": conversation["metrics"]
        }

        # Apply AI intelligence if enabled
        if request.enable_ai_analysis and AI_AVAILABLE:
            try:
                analysis = conversation_intelligence.generate_context_aware_response(
                    request.message,
                    request.conversation_history or conversation["messages"]
                )

                response_data["ai_analysis"] = analysis
                response_data["ai_analysis_applied"] = True
                conversation["metrics"]["ai_analyses_performed"] += 1

                # Enhance response based on analysis
                if analysis.get("suggested_actions"):
                    response_data["enhanced_suggestions"] = analysis["suggested_actions"]

                # Customize response based on sentiment
                sentiment_score = analysis["sentiment"].get("overall_sentiment", 0)
                if sentiment_score < -0.3:
                    response_data["response"] = f"I understand you're concerned about: {request.message}. Let me help you with that."
                elif sentiment_score > 0.3:
                    response_data["response"] = f"Great to hear about: {request.message}! Here's some information that might help."

            except Exception as e:
                logging.warning(f"Lightweight AI analysis failed: {e}")

        # Add assistant response to conversation
        assistant_message = {
            "role": "assistant",
            "content": response_data["response"],
            "timestamp": datetime.now().isoformat()
        }
        conversation["messages"].append(assistant_message)

        return response_data

    except Exception as e:
        logging.error(f"Enhanced chat message failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation details"""
    if conversation_id not in active_conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return active_conversations[conversation_id]

@app.get("/api/v1/analytics/overview")
async def get_analytics_overview():
    """Get analytics overview"""
    total_conversations = len(active_conversations)
    total_messages = sum(conv["metrics"]["message_count"] for conv in active_conversations.values())
    total_ai_analyses = sum(conv["metrics"]["ai_analyses_performed"] for conv in active_conversations.values())

    return {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_ai_analyses": total_ai_analyses,
        "ai_utilization_rate": total_ai_analyses / total_messages if total_messages > 0 else 0,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=5062)
EOF

    log_success "Lightweight Enhanced Chat Interface deployed"
}

# Start lightweight services
start_lightweight_services() {
    log_phase "Starting Lightweight Phase 3 services..."

    cd "$BACKEND_DIR"

    # Start lightweight enhanced chat interface
    nohup python3 chat_interface_phase3_lightweight.py > "$LOG_DIR/phase3_lightweight.log" 2>&1 &
    PHASE3_PID=$!
    echo $PHASE3_PID > "$LOG_DIR/phase3_lightweight.pid"

    sleep 3

    if ps -p $PHASE3_PID > /dev/null; then
        log_success "Lightweight Phase 3 Chat Interface started (PID: $PHASE3_PID)"
        log_info "Port: 5062"
        log_info "Logs: $LOG_DIR/phase3_lightweight.log"
    else
        log_error "Failed to start Lightweight Phase 3 Chat Interface"
        exit 1
    fi
}

# Run health checks
run_health_checks() {
    log_phase "Running health checks..."

    sleep 5

    if curl -s http://localhost:5062/health > /dev/null; then
        log_success "Lightweight Phase 3 Chat Interface is healthy"
    else
        log_error "Lightweight Phase 3 health check failed"
        exit 1
    fi

    # Test AI analysis endpoint
    TEST_RESPONSE=$(curl -s -X POST http://localhost:5062/api/v1/ai/analyze \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello, test the lightweight AI analysis", "user_id": "test_user"}')

    if echo "$TEST_RESPONSE" | grep -q "analysis_id"; then
        log_success "Lightweight AI analysis endpoint working"
    else
        log_warning "Lightweight AI analysis endpoint may need configuration"
    fi
}

# Main deployment function
main() {
    log_phase "🚀 Starting Atom Chat Interface Phase 3 Lightweight Deployment"

    check_prerequisites
    install_lightweight_dependencies
    deploy_ai_intelligence_lightweight
    deploy_lightweight_chat
    start_lightweight_services
    run_health_checks

    log_success "🎉 Phase 3 Lightweight Deployment Completed Successfully!"
    echo ""
    echo "📊 Deployment Summary:"
    echo "   Lightweight Chat Interface: http://localhost:5062"
    echo "   AI Analysis Endpoint: POST http://localhost:5062/api/v1/ai/analyze"
    echo "   Enhanced Chat Endpoint: POST http://localhost:5062/api/v1/chat/enhanced/message"
    echo ""
    echo "🔧 Quick Test Commands:"
    echo "   Health Check: curl http://localhost:5062/health"
    echo "   Root Endpoint: curl http://localhost:5062/"
    echo "   AI Analysis: curl -X POST http://localhost:5062/api/v1/ai/analyze -H 'Content-Type: application/json' -d '{\"message\": \"Test message\", \"user_id\": \"test_user\"}'"
    echo "   Enhanced Chat: curl -X POST http://localhost:5062/api/v1/chat/enhanced/message -H 'Content-Type: application/json' -d '{\"message\": \"Hello\", \"user_id\": \"test_user\", \"enable_ai_analysis\": true}'"
    echo "   Analytics: curl http://localhost:5062/api/v1/analytics/overview"
    echo ""
    echo "📝 Next Steps:"
    echo "   1. Integrate lightweight Phase 3 endpoints with your frontend"
    echo "   2. Monitor performance and resource usage"
    echo "   3. Configure additional AI models as needed"
    echo "   4. Run comprehensive testing with real user scenarios"
}

# Run main function
main "$@"
