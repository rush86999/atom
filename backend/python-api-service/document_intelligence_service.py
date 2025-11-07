"""
ATOM Document Intelligence Service
AI-powered document analysis, categorization, and understanding
Following ATOM service patterns and conventions
"""

import os
import json
import asyncio
import aiohttp
import base64
import hashlib
import tempfile
import traceback
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import mimetypes
import io

# AI/ML Libraries
import numpy as np
try:
    import cv2  # OpenCV for image processing
except ImportError:
    cv2 = None

try:
    import pytesseract  # OCR
except ImportError:
    pytesseract = None

try:
    import pdfplumber  # PDF processing
except ImportError:
    pdfplumber = None

try:
    import docx  # Word document processing
except ImportError:
    docx = None

try:
    import openai  # OpenAI for advanced AI capabilities
except ImportError:
    openai = None

try:
    import transformers  # Hugging Face for NLP
except ImportError:
    transformers = None

try:
    from sentence_transformers import SentenceTransformer  # Semantic embeddings
except ImportError:
    SentenceTransformer = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer = KMeans = cosine_similarity = None

from loguru import logger

# Google Drive integration
from google_drive_service import GoogleDriveService

def create_google_drive_service():
    return GoogleDriveService()

@dataclass
class DocumentAnalysis:
    """Document analysis results"""
    file_id: str
    file_name: str
    mime_type: str
    size: int
    
    # Content analysis
    text_content: Optional[str] = None
    extracted_entities: List[Dict[str, Any]] = None
    keywords: List[str] = None
    categories: List[str] = None
    summary: Optional[str] = None
    sentiment: Optional[Dict[str, float]] = None
    
    # Document intelligence
    language: Optional[str] = None
    readability_score: Optional[float] = None
    complexity_score: Optional[float] = None
    importance_score: Optional[float] = None
    
    # Processing metadata
    processing_time: Optional[float] = None
    processing_method: Optional[str] = None
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    
    # Vector embeddings for search
    text_embedding: Optional[List[float]] = None
    metadata_embedding: Optional[List[float]] = None
    
    def __post_init__(self):
        if self.extracted_entities is None:
            self.extracted_entities = []
        if self.keywords is None:
            self.keywords = []
        if self.categories is None:
            self.categories = []

@dataclass
class DocumentInsights:
    """Advanced document insights and recommendations"""
    file_id: str
    related_documents: List[Dict[str, Any]] = None
    similar_documents: List[Dict[str, Any]] = None
    duplicate_documents: List[Dict[str, Any]] = None
    recommended_tags: List[str] = None
    recommended_workflows: List[Dict[str, Any]] = None
    compliance_issues: List[Dict[str, Any]] = None
    quality_issues: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.related_documents is None:
            self.related_documents = []
        if self.similar_documents is None:
            self.similar_documents = []
        if self.duplicate_documents is None:
            self.duplicate_documents = []
        if self.recommended_tags is None:
            self.recommended_tags = []
        if self.recommended_workflows is None:
            self.recommended_workflows = []
        if self.compliance_issues is None:
            self.compliance_issues = []
        if self.quality_issues is None:
            self.quality_issues = []

class DocumentIntelligenceService:
    """Advanced document intelligence and analysis service"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        # Initialize Google Drive service (optional)
        try:
            self.google_drive_service = create_google_drive_service()
        except:
            self.google_drive_service = None
            logger.warning("Google Drive service not available for Document Intelligence")
        
        # AI models and tools
        self.sentence_model = None
        self.tfidf_vectorizer = None
        self.kmeans_classifier = None
        
        # Processing capabilities
        self.ocr_available = pytesseract is not None
        self.pdf_processing_available = pdfplumber is not None
        self.word_processing_available = docx is not None
        self.openai_available = openai is not None and self.openai_api_key
        self.transformers_available = transformers is not None
        
        # Initialize AI models
        self._initialize_ai_models()
        
        logger.info(f"Document Intelligence Service initialized with capabilities: "
                   f"OCR={self.ocr_available}, PDF={self.pdf_processing_available}, "
                   f"Word={self.word_processing_available}, OpenAI={self.openai_available}")
    
    def _initialize_ai_models(self):
        """Initialize AI models and tools"""
        try:
            # Initialize sentence transformer for embeddings
            if SentenceTransformer:
                self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Sentence transformer model loaded")
            
            # Initialize text vectorizer
            if TfidfVectorizer:
                self.tfidf_vectorizer = TfidfVectorizer(
                    max_features=5000,
                    stop_words='english',
                    ngram_range=(1, 2)
                )
                logger.info("TF-IDF vectorizer initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize AI models: {e}")
    
    async def analyze_document(self, file_id: str, access_token: str) -> DocumentAnalysis:
        """Comprehensive document analysis"""
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting document analysis for {file_id}")
            
            # Get file metadata from Google Drive
            file_metadata = await self._get_file_metadata(file_id, access_token)
            
            # Download file content
            file_content, file_path = await self._download_file(file_id, access_token)
            
            # Extract text content based on file type
            text_content = await self._extract_text_content(file_content, file_metadata)
            
            if not text_content or len(text_content.strip()) < 10:
                return DocumentAnalysis(
                    file_id=file_id,
                    file_name=file_metadata.get('name', ''),
                    mime_type=file_metadata.get('mimeType', ''),
                    size=file_metadata.get('size', 0),
                    processing_time=(datetime.utcnow() - start_time).total_seconds(),
                    processing_method="basic",
                    confidence_score=0.0,
                    error_message="Insufficient text content for analysis"
                )
            
            # Perform AI analysis
            analysis = await self._perform_ai_analysis(
                text_content, file_metadata, start_time
            )
            
            # Set basic file info
            analysis.file_id = file_id
            analysis.file_name = file_metadata.get('name', '')
            analysis.mime_type = file_metadata.get('mimeType', '')
            analysis.size = file_metadata.get('size', 0)
            analysis.text_content = text_content
            
            logger.info(f"Document analysis completed for {file_id} in {analysis.processing_time:.2f}s")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze document {file_id}: {e}")
            logger.error(traceback.format_exc())
            
            return DocumentAnalysis(
                file_id=file_id,
                file_name='',
                mime_type='',
                size=0,
                processing_time=(datetime.utcnow() - start_time).total_seconds(),
                processing_method="error",
                confidence_score=0.0,
                error_message=str(e)
            )
    
    async def _get_file_metadata(self, file_id: str, access_token: str) -> Dict[str, Any]:
        """Get file metadata from Google Drive"""
        try:
            metadata = await self.google_drive_service.get_file_metadata(file_id, access_token)
            return metadata
        except Exception as e:
            logger.error(f"Failed to get file metadata for {file_id}: {e}")
            return {}
    
    async def _download_file(self, file_id: str, access_token: str) -> Tuple[bytes, str]:
        """Download file from Google Drive"""
        try:
            file_content = await self.google_drive_service.download_file(file_id, access_token)
            
            # Create temporary file
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, f"document_{file_id}")
            
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            return file_content, file_path
            
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise
    
    async def _extract_text_content(self, file_content: bytes, file_metadata: Dict[str, Any]) -> str:
        """Extract text content from file based on type"""
        mime_type = file_metadata.get('mimeType', '')
        file_name = file_metadata.get('name', '')
        
        try:
            # Text files
            if mime_type.startswith('text/') or file_name.endswith(('.txt', '.md', '.csv')):
                return file_content.decode('utf-8', errors='ignore')
            
            # PDF files
            elif mime_type == 'application/pdf' or file_name.endswith('.pdf'):
                return await self._extract_from_pdf(file_content)
            
            # Word documents
            elif mime_type in [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword'
            ] or file_name.endswith(('.docx', '.doc')):
                return await self._extract_from_word(file_content)
            
            # Image files (OCR)
            elif mime_type.startswith('image/') or file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                return await self._extract_from_image(file_content)
            
            # Default: try to decode as text
            else:
                return file_content.decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.error(f"Failed to extract text from {file_name}: {e}")
            return ""
    
    async def _extract_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF"""
        if not self.pdf_processing_available:
            logger.warning("PDF processing not available")
            return ""
        
        try:
            with io.BytesIO(file_content) as pdf_file:
                with pdfplumber.open(pdf_file) as pdf:
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                    return text
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return ""
    
    async def _extract_from_word(self, file_content: bytes) -> str:
        """Extract text from Word document"""
        if not self.word_processing_available:
            logger.warning("Word processing not available")
            return ""
        
        try:
            with io.BytesIO(file_content) as docx_file:
                doc = docx.Document(docx_file)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text
        except Exception as e:
            logger.error(f"Failed to extract text from Word document: {e}")
            return ""
    
    async def _extract_from_image(self, file_content: bytes) -> str:
        """Extract text from image using OCR"""
        if not self.ocr_available:
            logger.warning("OCR not available")
            return ""
        
        try:
            # Convert bytes to image
            image_array = np.frombuffer(file_content, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if image is None:
                logger.warning("Failed to decode image")
                return ""
            
            # Perform OCR
            text = pytesseract.image_to_string(image)
            return text
            
        except Exception as e:
            logger.error(f"Failed to extract text from image: {e}")
            return ""
    
    async def _perform_ai_analysis(self, text_content: str, file_metadata: Dict[str, Any], start_time: datetime) -> DocumentAnalysis:
        """Perform AI-powered analysis on text content"""
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Basic text analysis
        keywords = self._extract_keywords(text_content)
        categories = self._categorize_document(text_content, file_metadata)
        language = self._detect_language(text_content)
        
        # Advanced AI analysis
        summary = None
        sentiment = None
        entities = []
        
        if self.openai_available:
            try:
                summary, sentiment, entities = await self._openai_analysis(text_content)
            except Exception as e:
                logger.error(f"OpenAI analysis failed: {e}")
        
        # Generate embeddings for search
        text_embedding = None
        if self.sentence_model:
            try:
                text_embedding = self.sentence_model.encode(text_content).tolist()
            except Exception as e:
                logger.error(f"Failed to generate embeddings: {e}")
        
        # Calculate document scores
        readability_score = self._calculate_readability(text_content)
        complexity_score = self._calculate_complexity(text_content)
        importance_score = self._calculate_importance(text_content, file_metadata)
        
        return DocumentAnalysis(
            text_content=text_content,
            extracted_entities=entities,
            keywords=keywords,
            categories=categories,
            summary=summary,
            sentiment=sentiment,
            language=language,
            readability_score=readability_score,
            complexity_score=complexity_score,
            importance_score=importance_score,
            processing_time=processing_time,
            processing_method="ai_enhanced",
            confidence_score=0.8,
            text_embedding=text_embedding,
            metadata_embedding=None
        )
    
    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text"""
        try:
            if self.tfidf_vectorizer:
                # Fit and transform
                tfidf_matrix = self.tfidf_vectorizer.fit_transform([text])
                feature_names = self.tfidf_vectorizer.get_feature_names_out()
                tfidf_scores = tfidf_matrix.toarray()[0]
                
                # Get top keywords
                top_indices = tfidf_scores.argsort()[-max_keywords:][::-1]
                keywords = [feature_names[i] for i in top_indices if tfidf_scores[i] > 0]
                
                return keywords[:max_keywords]
            else:
                # Simple keyword extraction
                words = text.lower().split()
                # Remove common words and get most frequent
                common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'}
                filtered_words = [word for word in words if len(word) > 2 and word not in common_words]
                
                # Count frequency
                word_freq = {}
                for word in filtered_words:
                    word_freq[word] = word_freq.get(word, 0) + 1
                
                # Get top keywords
                sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
                return [word for word, freq in sorted_words[:max_keywords]]
                
        except Exception as e:
            logger.error(f"Failed to extract keywords: {e}")
            return []
    
    def _categorize_document(self, text: str, file_metadata: Dict[str, Any]) -> List[str]:
        """Categorize document based on content and metadata"""
        categories = []
        
        try:
            text_lower = text.lower()
            file_name = file_metadata.get('name', '').lower()
            
            # Business categories
            if any(term in text_lower for term in ['invoice', 'bill', 'payment', 'receipt', 'transaction']):
                categories.append('Financial')
            if any(term in text_lower for term in ['contract', 'agreement', 'legal', 'terms']):
                categories.append('Legal')
            if any(term in text_lower for term in ['report', 'analysis', 'metrics', 'kpi']):
                categories.append('Reports')
            if any(term in text_lower for term in ['meeting', 'notes', 'minutes', 'discussion']):
                categories.append('Meetings')
            if any(term in text_lower for term in ['proposal', 'quote', 'estimate', 'bid']):
                categories.append('Sales')
            if any(term in text_lower for term in ['manual', 'guide', 'instructions', 'documentation']):
                categories.append('Documentation')
            if any(term in text_lower for term in ['resume', 'cv', 'application', 'candidate']):
                categories.append('HR')
            if any(term in text_lower for term in ['research', 'study', 'analysis', 'data']):
                categories.append('Research')
            
            # File name based categorization
            if 'invoice' in file_name or 'bill' in file_name:
                if 'Financial' not in categories:
                    categories.append('Financial')
            if 'contract' in file_name or 'agreement' in file_name:
                if 'Legal' not in categories:
                    categories.append('Legal')
            if 'report' in file_name:
                if 'Reports' not in categories:
                    categories.append('Reports')
            
            # Default category
            if not categories:
                categories.append('General')
                
        except Exception as e:
            logger.error(f"Failed to categorize document: {e}")
            categories.append('General')
        
        return categories
    
    def _detect_language(self, text: str) -> Optional[str]:
        """Detect document language"""
        try:
            # Simple language detection based on common words
            common_words = {
                'en': ['the', 'and', 'is', 'in', 'to', 'of', 'a', 'that', 'it', 'with'],
                'es': ['el', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no'],
                'fr': ['le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir'],
                'de': ['der', 'die', 'und', 'in', 'den', 'von', 'zu', 'das', 'mit', 'sich'],
                'it': ['il', 'di', 'che', 'e', 'la', 'un', 'a', 'per', 'non', 'si']
            }
            
            text_lower = text.lower()[:1000]  # Check first 1000 chars
            
            scores = {}
            for lang, words in common_words.items():
                score = sum(1 for word in words if word in text_lower)
                scores[lang] = score
            
            if scores:
                detected_lang = max(scores, key=scores.get)
                if scores[detected_lang] > 2:  # Threshold
                    return detected_lang
            
            return 'en'  # Default to English
            
        except Exception as e:
            logger.error(f"Failed to detect language: {e}")
            return None
    
    async def _openai_analysis(self, text: str) -> Tuple[Optional[str], Optional[Dict[str, float]], List[Dict[str, Any]]]:
        """Perform advanced analysis using OpenAI"""
        if not self.openai_available:
            return None, None, []
        
        try:
            # Limit text length for API
            max_length = 8000
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            # OpenAI client
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            # Generate summary
            summary_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Summarize the following document in 2-3 sentences."},
                    {"role": "user", "content": text}
                ],
                max_tokens=150,
                temperature=0.3
            )
            summary = summary_response.choices[0].message.content
            
            # Analyze sentiment
            sentiment_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Analyze the sentiment of the following document. Return a JSON object with 'positive', 'negative', and 'neutral' scores (0-1)."},
                    {"role": "user", "content": text}
                ],
                max_tokens=100,
                temperature=0.1
            )
            sentiment_text = sentiment_response.choices[0].message.content
            try:
                sentiment = json.loads(sentiment_text)
            except:
                sentiment = {"positive": 0.5, "negative": 0.5, "neutral": 0.0}
            
            # Extract entities
            entities_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract key entities (people, organizations, locations, dates) from the following document. Return as JSON array of objects with 'type' and 'name' fields."},
                    {"role": "user", "content": text}
                ],
                max_tokens=300,
                temperature=0.1
            )
            entities_text = entities_response.choices[0].message.content
            try:
                entities = json.loads(entities_text)
                if not isinstance(entities, list):
                    entities = []
            except:
                entities = []
            
            return summary, sentiment, entities
            
        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}")
            return None, None, []
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score (0-1, higher is more readable)"""
        try:
            # Simple readability based on sentence and word length
            sentences = text.split('.')
            words = text.split()
            
            if len(words) == 0:
                return 0.0
            
            avg_words_per_sentence = len(words) / len(sentences)
            
            # Optimal is 15-20 words per sentence
            if 10 <= avg_words_per_sentence <= 25:
                readability = 0.8
            elif 5 <= avg_words_per_sentence <= 35:
                readability = 0.6
            else:
                readability = 0.4
            
            # Adjust for very short or very long words
            avg_word_length = sum(len(word) for word in words) / len(words)
            if avg_word_length > 8:
                readability *= 0.8
            
            return min(1.0, max(0.0, readability))
            
        except Exception as e:
            logger.error(f"Failed to calculate readability: {e}")
            return 0.5
    
    def _calculate_complexity(self, text: str) -> float:
        """Calculate complexity score (0-1, higher is more complex)"""
        try:
            # Simple complexity based on unique words and average word length
            words = text.lower().split()
            unique_words = set(words)
            
            if len(words) == 0:
                return 0.0
            
            # Unique word ratio
            unique_ratio = len(unique_words) / len(words)
            
            # Average word length
            avg_word_length = sum(len(word) for word in words) / len(words)
            
            # Combine factors
            complexity = (unique_ratio * 0.6 + min(1.0, avg_word_length / 10) * 0.4)
            
            return min(1.0, max(0.0, complexity))
            
        except Exception as e:
            logger.error(f"Failed to calculate complexity: {e}")
            return 0.5
    
    def _calculate_importance(self, text: str, file_metadata: Dict[str, Any]) -> float:
        """Calculate importance score (0-1, higher is more important)"""
        try:
            score = 0.5  # Base score
            
            # File size factor
            file_size = file_metadata.get('size', 0)
            if file_size > 1000000:  # > 1MB
                score += 0.1
            elif file_size > 100000:  # > 100KB
                score += 0.05
            
            # Text length factor
            text_length = len(text)
            if text_length > 5000:
                score += 0.1
            elif text_length > 1000:
                score += 0.05
            
            # Category importance
            categories = self._categorize_document(text, file_metadata)
            important_categories = ['Financial', 'Legal', 'Contracts']
            if any(cat in categories for cat in important_categories):
                score += 0.1
            
            # Recency (if available)
            created_time = file_metadata.get('createdTime')
            if created_time:
                try:
                    created_dt = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                    days_old = (datetime.utcnow() - created_dt).days
                    if days_old < 7:
                        score += 0.1
                    elif days_old < 30:
                        score += 0.05
                except:
                    pass
            
            # File name importance indicators
            file_name = file_metadata.get('name', '').lower()
            important_terms = ['urgent', 'important', 'critical', 'final', 'contract', 'invoice', 'agreement']
            if any(term in file_name for term in important_terms):
                score += 0.1
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Failed to calculate importance: {e}")
            return 0.5
    
    async def get_document_insights(self, file_id: str, access_token: str) -> DocumentInsights:
        """Get advanced insights for a document"""
        try:
            # Get document analysis
            analysis = await self.analyze_document(file_id, access_token)
            
            # Generate insights
            insights = DocumentInsights(file_id=file_id)
            
            # Find similar documents (if embeddings available)
            if analysis.text_embedding:
                insights.similar_documents = await self._find_similar_documents(file_id, analysis.text_embedding, access_token)
            
            # Find duplicate documents
            insights.duplicate_documents = await self._find_duplicate_documents(file_id, analysis.text_content, access_token)
            
            # Generate recommendations
            insights.recommended_tags = analysis.categories + analysis.keywords[:5]
            insights.recommended_workflows = self._recommend_workflows(analysis)
            
            # Check for compliance issues
            insights.compliance_issues = await self._check_compliance(analysis)
            
            # Check for quality issues
            insights.quality_issues = self._check_quality(analysis)
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to get document insights for {file_id}: {e}")
            return DocumentInsights(file_id=file_id)
    
    async def _find_similar_documents(self, file_id: str, embedding: List[float], access_token: str) -> List[Dict[str, Any]]:
        """Find similar documents using semantic search"""
        # This would require a vector database
        # For now, return empty list
        return []
    
    async def _find_duplicate_documents(self, file_id: str, content: str, access_token: str) -> List[Dict[str, Any]]:
        """Find potential duplicate documents"""
        # This would require storing document hashes
        # For now, return empty list
        return []
    
    def _recommend_workflows(self, analysis: DocumentAnalysis) -> List[Dict[str, Any]]:
        """Recommend workflows based on document analysis"""
        workflows = []
        
        try:
            categories = analysis.categories or []
            
            # Financial workflows
            if 'Financial' in categories:
                workflows.extend([
                    {"name": "Create Invoice", "description": "Generate invoice from document"},
                    {"name": "Process Payment", "description": "Create payment request"},
                    {"name": "Tax Reporting", "description": "Add to tax report"}
                ])
            
            # Legal workflows
            if 'Legal' in categories:
                workflows.extend([
                    {"name": "Legal Review", "description": "Send for legal review"},
                    {"name": "Contract Management", "description": "Add to contract tracking"},
                    {"name": "Compliance Check", "description": "Run compliance verification"}
                ])
            
            # Meeting workflows
            if 'Meetings' in categories:
                workflows.extend([
                    {"name": "Schedule Follow-up", "description": "Create follow-up tasks"},
                    {"name": "Share with Team", "description": "Distribute to attendees"},
                    {"name": "Action Items", "description": "Extract action items"}
                ])
            
        except Exception as e:
            logger.error(f"Failed to recommend workflows: {e}")
        
        return workflows
    
    def _check_compliance(self, analysis: DocumentAnalysis) -> List[Dict[str, Any]]:
        """Check for compliance issues"""
        issues = []
        
        try:
            text_content = analysis.text_content or ""
            
            # Check for sensitive information patterns
            sensitive_patterns = {
                'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
                'credit_card': r'\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b',
                'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            }
            
            import re
            for pattern_type, pattern in sensitive_patterns.items():
                matches = re.findall(pattern, text_content)
                if matches:
                    issues.append({
                        "type": "sensitive_data",
                        "pattern": pattern_type,
                        "count": len(matches),
                        "severity": "high"
                    })
            
            # Check for missing required clauses (for legal documents)
            if 'Legal' in (analysis.categories or []):
                legal_terms = ['indemnification', 'liability', 'termination', 'governing law']
                missing_terms = [term for term in legal_terms if term.lower() not in text_content.lower()]
                if missing_terms:
                    issues.append({
                        "type": "missing_clause",
                        "missing_terms": missing_terms,
                        "severity": "medium"
                    })
            
        except Exception as e:
            logger.error(f"Failed to check compliance: {e}")
        
        return issues
    
    def _check_quality(self, analysis: DocumentAnalysis) -> List[Dict[str, Any]]:
        """Check for document quality issues"""
        issues = []
        
        try:
            # Check readability
            if analysis.readability_score and analysis.readability_score < 0.4:
                issues.append({
                    "type": "readability",
                    "score": analysis.readability_score,
                    "recommendation": "Consider simplifying sentences",
                    "severity": "medium"
                })
            
            # Check complexity
            if analysis.complexity_score and analysis.complexity_score > 0.8:
                issues.append({
                    "type": "complexity",
                    "score": analysis.complexity_score,
                    "recommendation": "Document may be too complex",
                    "severity": "low"
                })
            
            # Check content length
            content_length = len(analysis.text_content or "")
            if content_length < 50:
                issues.append({
                    "type": "content_length",
                    "length": content_length,
                    "recommendation": "Document appears to have minimal content",
                    "severity": "low"
                })
            
        except Exception as e:
            logger.error(f"Failed to check quality: {e}")
        
        return issues
    
    async def batch_analyze_documents(self, file_ids: List[str], access_token: str, max_concurrent: int = 5) -> List[DocumentAnalysis]:
        """Analyze multiple documents concurrently"""
        try:
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def analyze_single(file_id: str) -> DocumentAnalysis:
                async with semaphore:
                    return await self.analyze_document(file_id, access_token)
            
            # Create tasks
            tasks = [analyze_single(file_id) for file_id in file_ids]
            
            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            analyses = []
            for result in results:
                if isinstance(result, DocumentAnalysis):
                    analyses.append(result)
                else:
                    logger.error(f"Batch analysis error: {result}")
            
            logger.info(f"Batch analysis completed: {len(analyses)} out of {len(file_ids)} documents")
            return analyses
            
        except Exception as e:
            logger.error(f"Failed to perform batch analysis: {e}")
            return []
    
    def get_service_capabilities(self) -> Dict[str, Any]:
        """Get service capabilities and status"""
        return {
            "service": "document_intelligence",
            "capabilities": {
                "text_extraction": True,
                "ocr_processing": self.ocr_available,
                "pdf_processing": self.pdf_processing_available,
                "word_processing": self.word_processing_available,
                "ai_analysis": self.openai_available,
                "semantic_embeddings": self.sentence_model is not None,
                "batch_processing": True,
                "document_insights": True,
                "workflow_recommendations": True,
                "compliance_checking": True
            },
            "supported_formats": [
                "text/*", "application/pdf", 
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "image/*"
            ],
            "ai_models": {
                "sentence_transformer": self.sentence_model is not None,
                "openai_gpt": self.openai_available,
                "tfidf_vectorizer": self.tfidf_vectorizer is not None
            }
        }

# Factory function
def create_document_intelligence_service(openai_api_key: Optional[str] = None) -> DocumentIntelligenceService:
    """Create document intelligence service instance"""
    return DocumentIntelligenceService(openai_api_key)