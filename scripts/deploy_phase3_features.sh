#!/bin/bash

# ATOM Chat Interface - Phase 3 Advanced Features Deployment
# This script deploys advanced AI-powered conversation intelligence,
# multi-modal experience enhancement, and voice integration optimization

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT_ROOT/backend"
LOG_DIR="$PROJECT_ROOT/logs"
CONFIG_DIR="$PROJECT_ROOT/config"
PHASE3_DIR="$PROJECT_ROOT/phase3_features"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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
    echo -e "${PURPLE}[PHASE 3]${NC} $1"
}

log_feature() {
    echo -e "${CYAN}[FEATURE]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_phase "Checking prerequisites for Phase 3 features..."

    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_success "Python $PYTHON_VERSION found"
    else
        log_error "Python 3 is required but not installed"
        exit 1
    fi

    # Check pip
    if command -v pip3 &> /dev/null; then
        log_success "pip3 found"
    else
        log_error "pip3 is required but not installed"
        exit 1
    fi

    # Check if backend directory exists
    if [ ! -d "$BACKEND_DIR" ]; then
        log_error "Backend directory not found: $BACKEND_DIR"
        exit 1
    fi

    # Check if chat interface is running
    if curl -s http://localhost:5059/health > /dev/null; then
        log_success "Chat Interface Server is running"
    else
        log_error "Chat Interface Server is not running on port 5059"
        exit 1
    fi

    # Check if WebSocket server is running
    if curl -s http://localhost:5060/health > /dev/null; then
        log_success "WebSocket Server is running"
    else
        log_error "WebSocket Server is not running on port 5060"
        exit 1
    fi

    # Create phase3 features directory
    mkdir -p "$PHASE3_DIR"
    log_success "Phase 3 features directory ready: $PHASE3_DIR"
}

# Install Phase 3 dependencies
install_phase3_dependencies() {
    log_phase "Installing Phase 3 advanced dependencies..."

    cd "$BACKEND_DIR"

    # Install AI and ML dependencies
    log_feature "Installing AI/ML libraries..."
    pip3 install transformers torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    pip3 install sentence-transformers spacy scikit-learn
    pip3 install nltk textblob vaderSentiment

    # Download spaCy model
    python3 -m spacy download en_core_web_sm

    # Install advanced file processing dependencies
    log_feature "Installing file processing libraries..."
    pip3 install PyPDF2 python-docx openpyxl pptx pdfplumber
    pip3 install Pillow opencv-python pytesseract

    # Install advanced voice processing dependencies
    log_feature "Installing voice processing libraries..."
    pip3 install speechrecognition pydub librosa soundfile
    pip3 install gtts pyttsx3 wave audioop

    # Install analytics and monitoring dependencies
    log_feature "Installing analytics libraries..."
    pip3 install prometheus-client matplotlib seaborn plotly
    pip3 install pandas numpy scipy

    log_success "Phase 3 dependencies installed successfully"
}

# Deploy AI Conversation Intelligence
deploy_ai_conversation_intelligence() {
    log_phase "Deploying AI-Powered Conversation Intelligence..."

    cd "$BACKEND_DIR"

    # Create AI intelligence module
    cat > "ai_conversation_intelligence.py" << 'EOF'
"""
AI-Powered Conversation Intelligence Module
Advanced NLU, sentiment analysis, and context-aware response generation
"""

import logging
from typing import Dict, List, Optional, Any
import json
from datetime import datetime

# Import AI/ML libraries
try:
    from transformers import pipeline, AutoTokenizer, AutoModel
    import torch
    import spacy
    from sentence_transformers import SentenceTransformer
    from textblob import TextBlob
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    AI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"AI libraries not available: {e}")
    AI_AVAILABLE = False

class ConversationIntelligence:
    """Advanced AI-powered conversation intelligence"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.nlp = None
        self.sentiment_analyzer = None
        self.sentence_model = None
        self.intent_classifier = None

        if AI_AVAILABLE:
            self.initialize_ai_models()

    def initialize_ai_models(self):
        """Initialize AI models for conversation intelligence"""
        try:
            # Load spaCy model for NLP
            self.nlp = spacy.load("en_core_web_sm")

            # Initialize sentiment analyzer
            self.sentiment_analyzer = SentimentIntensityAnalyzer()

            # Load sentence transformer for semantic similarity
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

            # Initialize intent classifier
            self.intent_classifier = pipeline(
                "text-classification",
                model="joeddav/distilbert-base-uncased-go-emotions-student",
                return_all_scores=True
            )

            self.logger.info("AI conversation intelligence models initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize AI models: {e}")

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text with multiple methods"""
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

    def classify_intent(self, text: str) -> List[Dict[str, Any]]:
        """Classify user intent from text"""
        if not AI_AVAILABLE or not self.intent_classifier:
            return [{"label": "neutral", "score": 1.0}]

        try:
            results = self.intent_classifier(text)
            # Return top 3 intents
            top_intents = sorted(results[0], key=lambda x: x['score'], reverse=True)[:3]
            return top_intents

        except Exception as e:
            self.logger.error(f"Intent classification failed: {e}")
            return [{"label": "error", "score": 1.0}]

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        """Extract named entities from text"""
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

    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        if not AI_AVAILABLE or not self.sentence_model:
            return 0.0

        try:
            embeddings = self.sentence_model.encode([text1, text2])
            similarity = torch.nn.functional.cosine_similarity(
                torch.tensor(embeddings[0]).unsqueeze(0),
                torch.tensor(embeddings[1]).unsqueeze(0)
            )
            return similarity.item()

        except Exception as e:
            self.logger.error(f"Semantic similarity calculation failed: {e}")
            return 0.0

    def generate_context_aware_response(self, message: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Generate context-aware response using conversation history"""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "sentiment": self.analyze_sentiment(message),
            "intent": self.classify_intent(message),
            "entities": self.extract_entities(message),
            "context_relevance": 0.0,
            "suggested_actions": []
        }

        # Calculate context relevance with previous messages
        if conversation_history:
            recent_messages = conversation_history[-3:]  # Last 3 messages
            relevance_scores = []

            for prev_msg in recent_messages:
                if 'content' in prev_msg:
                    similarity = self.calculate_semantic_similarity(message, prev_msg['content'])
                    relevance_scores.append(similarity)

            if relevance_scores:
                analysis["context_relevance"] = sum(relevance_scores) / len(relevance_scores)

        # Generate suggested actions based on analysis
        if analysis["sentiment"].get("overall_sentiment", 0) < -0.3:
            analysis["suggested_actions"].append("escalate_to_human")
            analysis["suggested_actions"].append("offer_apology")

        if any(entity["label"] in ["PERSON", "ORG"] for entity in analysis["entities"]):
            analysis["suggested_actions"].append("personalize_response")

        return analysis

# Global instance
conversation_intelligence = ConversationIntelligence()
EOF

    log_success "AI Conversation Intelligence module deployed"
}

# Deploy Multi-Modal Enhancement
deploy_multi_modal_enhancement() {
    log_phase "Deploying Multi-Modal Experience Enhancement..."

    cd "$BACKEND_DIR"

    # Create multi-modal enhancement module
    cat > "multi_modal_enhancement.py" << 'EOF'
"""
Multi-Modal Experience Enhancement Module
Advanced file processing, image analysis, and rich media responses
"""

import logging
import os
from typing import Dict, List, Optional, Any
import json
from pathlib import Path

# Import file processing libraries
try:
    from PyPDF2 import PdfReader
    import docx
    from openpyxl import load_workbook
    import pptx
    import pdfplumber
    from PIL import Image, ImageEnhance, ImageFilter
    import cv2
    import pytesseract
    FILE_PROCESSING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"File processing libraries not available: {e}")
    FILE_PROCESSING_AVAILABLE = False

class MultiModalEnhancement:
    """Advanced multi-modal chat experience enhancement"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supported_formats = {
            'documents': ['.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.csv'],
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'],
            'audio': ['.mp3', '.wav', '.ogg', '.m4a'],
            'video': ['.mp4', '.avi', '.mov', '.wmv']
        }

    def process_document(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """Process various document types and extract content"""
        if not FILE_PROCESSING_AVAILABLE:
            return {"error": "File processing libraries not available"}

        try:
            result = {
                "file_type": file_type,
                "file_size": os.path.getsize(file_path),
                "content": "",
                "metadata": {},
                "summary": "",
                "pages": 0,
                "word_count": 0
            }

            if file_type == '.pdf':
                # Process PDF files
                with pdfplumber.open(file_path) as pdf:
                    result["pages"] = len(pdf.pages)
                    content = []
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            content.append(page_text)

                    result["content"] = "\n".join(content)
                    result["word_count"] = len(result["content"].split())

                    # Extract metadata
                    with open(file_path, 'rb') as f:
                        pdf_reader = PdfReader(f)
                        if pdf_reader.metadata:
                            result["metadata"] = dict(pdf_reader.metadata)

            elif file_type == '.docx':
                # Process Word documents
                doc = docx.Document(file_path)
                content = []
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content.append(paragraph.text)

                result["content"] = "\n".join(content)
                result["word_count"] = len(result["content"].split())
                result["pages"] = len([p for p in doc.paragraphs if p.text.strip()])

            elif file_type == '.xlsx':
                # Process Excel files
                workbook = load_workbook(file_path)
                content = []
                for sheet_name in workbook.sheetnames:
                    sheet = workbook[sheet_name]
                    sheet_data = []
                    for row in sheet.iter_rows(values_only=True):
                        row_data = [str(cell) if cell is not None else "" for cell in row]
                        sheet_data.append("\t".join(row_data))
                    content.append(f"Sheet: {sheet_name}\n" + "\n".join(sheet_data))

                result["content"] = "\n\n".join(content)
                result["sheets"] = len(workbook.sheetnames)

            elif file_type == '.pptx':
                # Process PowerPoint files
                presentation = pptx.Presentation(file_path)
                content = []
                for i, slide in enumerate(presentation.slides):
                    slide_content = []
                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text.strip():
                            slide_content.append(shape.text)
                    if slide_content:
                        content.append(f"Slide {i+1}:\n" + "\n".join(slide_content))

                result["content"] = "\n\n".join(content)
                result["slides"] = len(presentation.slides)

            else:
                # Process text files
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    result["content"] = f.read()
                    result["word_count"] = len(result["content"].split())

            # Generate summary
            if result["content"]:
                words = result["content"].split()
                if len(words) > 100:
                    result["summary"] = " ".join(words[:100]) + "..."
                else:
                    result["summary"] = result["content"]

            return result

        except Exception as e:
            self.logger.error(f"Document processing failed: {e}")
            return {"error": str(e)}

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Analyze image content and extract information"""
        if not FILE_PROCESSING_AVAILABLE:
            return {"error": "Image processing libraries not available"}

        try:
            result = {
                "image_path": image_path,
                "file_size": os.path.getsize(image_path),
                "dimensions": "",
                "format": "",
                "text_content": "",
                "objects_detected": [],
                "color_analysis": {},
                "enhancement_suggestions": []
            }

            # Open and analyze image
            with Image.open(image_path) as img:
                result["dimensions"] = f"{img.width}x{img.height}"
                result["format"] = img.format

                # Basic color analysis
                img_rgb = img.convert('RGB')
                pixels = list(img_rgb.getdata())
                total_pixels = len(pixels)

                if total_pixels > 0:
                    # Calculate average color
                    avg_color = [sum(c[i] for c in pixels) // total_pixels for i in range(3)]
                    result["color_analysis"]["average_color"] = f"rgb({avg_color[0]}, {avg_color[1]}, {avg_color[2]})"

                # Text extraction using OCR
                try:
                    extracted_text = pytesseract.image_to_string(img)
                    if extracted_text.strip():
                        result["text_content"] = extracted_text.strip()
                except Exception as ocr_error:
                    self.logger
