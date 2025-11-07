"""
ATOM Document Intelligence Test Suite
Comprehensive testing for AI-powered document analysis
Following ATOM testing patterns and conventions
"""

import os
import sys
import pytest
import asyncio
import tempfile
import json
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import base64

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_intelligence_service import (
    DocumentIntelligenceService, 
    DocumentAnalysis, 
    DocumentInsights,
    create_document_intelligence_service
)

class TestDocumentIntelligenceService:
    """Test Document Intelligence Service functionality"""
    
    @pytest.fixture
    def document_service(self):
        """Create document intelligence service for testing"""
        return DocumentIntelligenceService()
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client for testing"""
        mock_client = Mock()
        
        # Mock chat completion responses
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="This document discusses important business strategies and financial planning."))
        ]
        mock_client.chat.completions.create.return_value = mock_response
        
        return mock_client
    
    def test_service_creation(self, document_service):
        """Test document intelligence service creation"""
        assert document_service is not None
        assert isinstance(document_service, DocumentIntelligenceService)
        assert document_service.google_drive_service is not None
    
    def test_service_capabilities(self, document_service):
        """Test service capabilities detection"""
        capabilities = document_service.get_service_capabilities()
        
        assert "service" in capabilities
        assert "capabilities" in capabilities
        assert "supported_formats" in capabilities
        assert "ai_models" in capabilities
        
        # Check basic capabilities
        service_caps = capabilities["capabilities"]
        assert service_caps["text_extraction"] is True
        assert service_caps["batch_processing"] is True
        assert service_caps["document_insights"] is True
        assert service_caps["workflow_recommendations"] is True
        assert service_caps["compliance_checking"] is True
    
    def test_text_extraction_from_text(self, document_service):
        """Test text extraction from text files"""
        content = b"This is a test document with some text content."
        metadata = {'name': 'test.txt', 'mimeType': 'text/plain'}
        
        result = asyncio.run(document_service._extract_text_content(content, metadata))
        
        assert result == "This is a test document with some text content."
    
    def test_text_extraction_from_pdf(self, document_service):
        """Test PDF text extraction"""
        # Mock PDF content (would be actual PDF bytes in real scenario)
        content = b"PDF content placeholder"
        metadata = {'name': 'test.pdf', 'mimeType': 'application/pdf'}
        
        with patch.object(document_service, '_extract_from_pdf') as mock_extract:
            mock_extract.return_value = "PDF extracted text"
            
            result = asyncio.run(document_service._extract_text_content(content, metadata))
            assert result == "PDF extracted text"
            mock_extract.assert_called_once_with(content)
    
    def test_text_extraction_from_word(self, document_service):
        """Test Word document text extraction"""
        content = b"Word content placeholder"
        metadata = {'name': 'test.docx', 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        
        with patch.object(document_service, '_extract_from_word') as mock_extract:
            mock_extract.return_value = "Word extracted text"
            
            result = asyncio.run(document_service._extract_text_content(content, metadata))
            assert result == "Word extracted text"
            mock_extract.assert_called_once_with(content)
    
    def test_keyword_extraction(self, document_service):
        """Test keyword extraction from text"""
        text = "This is a business report about financial planning and strategic marketing initiatives. The report discusses quarterly performance metrics and future growth projections."
        
        keywords = document_service._extract_keywords(text, max_keywords=10)
        
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        # Should contain relevant business terms
        assert any("business" in keyword.lower() for keyword in keywords)
        assert any("financial" in keyword.lower() for keyword in keywords)
    
    def test_document_categorization(self, document_service):
        """Test document categorization"""
        # Financial document
        financial_text = "Invoice #1234 for services rendered. Payment due in 30 days. Amount: $5,000.00"
        metadata = {'name': 'invoice_1234.pdf', 'mimeType': 'application/pdf'}
        
        categories = document_service._categorize_document(financial_text, metadata)
        
        assert isinstance(categories, list)
        assert len(categories) > 0
        assert 'Financial' in categories
        
        # Legal document
        legal_text = "Contract agreement between Company A and Company B. Terms and conditions apply. This agreement shall be governed by the laws of State X."
        metadata = {'name': 'service_agreement.docx', 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        
        categories = document_service._categorize_document(legal_text, metadata)
        assert 'Legal' in categories
        
        # Meeting notes
        meeting_text = "Meeting notes from the quarterly review session. Attendees: John, Sarah, Mike. Discussion topics: budget, timeline, resources."
        metadata = {'name': 'meeting_notes.txt', 'mimeType': 'text/plain'}
        
        categories = document_service._categorize_document(meeting_text, metadata)
        assert 'Meetings' in categories
    
    def test_language_detection(self, document_service):
        """Test language detection"""
        # English text
        english_text = "This is an English document with standard content."
        lang = document_service._detect_language(english_text)
        assert lang == 'en'
        
        # Spanish text
        spanish_text = "Este es un documento en español con contenido estándar."
        lang = document_service._detect_language(spanish_text)
        assert lang in ['es', 'en']  # Should detect Spanish or default to English
        
        # Empty text
        lang = document_service._detect_language("")
        assert lang is None
    
    def test_readability_calculation(self, document_service):
        """Test readability score calculation"""
        # Simple, readable text
        simple_text = "The cat sat on the mat. It was happy. The mat was soft."
        readability = document_service._calculate_readability(simple_text)
        assert 0.0 <= readability <= 1.0
        
        # Complex text
        complex_text = "The aforementioned establishment's comprehensive strategic initiatives, implemented pursuant to the statutory regulatory framework, necessitated meticulous operational optimization."
        readability = document_service._calculate_readability(complex_text)
        assert 0.0 <= readability <= 1.0
        # Complex text should have lower readability
        assert readability < 0.6
    
    def test_complexity_calculation(self, document_service):
        """Test complexity score calculation"""
        # Simple text
        simple_text = "The cat sat. It was happy."
        complexity = document_service._calculate_complexity(simple_text)
        assert 0.0 <= complexity <= 1.0
        
        # Complex text with unique words
        complex_text = "The comprehensive strategic implementation necessitated meticulous operational optimization and procedural standardization across all organizational divisions."
        complexity = document_service._calculate_complexity(complex_text)
        assert 0.0 <= complexity <= 1.0
        # Complex text should have higher complexity
        assert complexity > 0.5
    
    def test_importance_calculation(self, document_service):
        """Test importance score calculation"""
        text = "This is a business document with important information."
        
        # Regular document
        metadata = {'name': 'notes.txt', 'size': 1000, 'createdTime': '2024-01-01T10:00:00Z'}
        importance = document_service._calculate_importance(text, metadata)
        assert 0.0 <= importance <= 1.0
        
        # Important document (urgent keyword)
        metadata = {'name': 'URGENT_contract_final.pdf', 'size': 50000, 'createdTime': '2024-01-15T10:00:00Z'}
        importance = document_service._calculate_importance(text, metadata)
        assert 0.0 <= importance <= 1.0
        # Should have higher importance due to keyword and size
        assert importance > 0.5
    
    def test_workflow_recommendations(self, document_service):
        """Test workflow recommendations based on document analysis"""
        # Financial document
        financial_analysis = DocumentAnalysis(
            file_id="test1",
            file_name="invoice.pdf",
            mime_type="application/pdf",
            size=10000,
            categories=["Financial"]
        )
        
        workflows = document_service._recommend_workflows(financial_analysis)
        
        assert isinstance(workflows, list)
        assert len(workflows) > 0
        
        # Should include financial workflows
        workflow_names = [w.get('name', '') for w in workflows]
        assert any('Invoice' in name for name in workflow_names)
        assert any('Payment' in name for name in workflow_names)
        
        # Legal document
        legal_analysis = DocumentAnalysis(
            file_id="test2",
            file_name="contract.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size=20000,
            categories=["Legal"]
        )
        
        workflows = document_service._recommend_workflows(legal_analysis)
        workflow_names = [w.get('name', '') for w in workflows]
        assert any('Legal' in name for name in workflow_names)
        assert any('Contract' in name for name in workflow_names)
    
    def test_compliance_checking(self, document_service):
        """Test compliance issue checking"""
        # Document with sensitive information
        sensitive_text = "Customer SSN: 123-45-6789. Credit Card: 4567-8901-2345-6789. Contact: customer@example.com"
        analysis = DocumentAnalysis(
            file_id="test",
            file_name="customer_data.txt",
            mime_type="text/plain",
            size=1000,
            text_content=sensitive_text,
            categories=["General"]
        )
        
        issues = document_service._check_compliance(analysis)
        
        assert isinstance(issues, list)
        assert len(issues) > 0
        
        # Should detect sensitive data
        issue_types = [issue.get('type', '') for issue in issues]
        assert 'sensitive_data' in issue_types
        
        # Check specific sensitive data types
        sensitive_issues = [issue for issue in issues if issue.get('type') == 'sensitive_data']
        assert len(sensitive_issues) > 0
        
        patterns_found = [issue.get('pattern', '') for issue in sensitive_issues]
        assert any('ssn' in pattern or 'credit_card' in pattern or 'email' in pattern for pattern in patterns_found)
    
    def test_quality_checking(self, document_service):
        """Test document quality checking"""
        # Document with readability issues
        poor_text = "Thedocumntcntnainsverylongwordswithoutspacesandbadreadability."
        analysis = DocumentAnalysis(
            file_id="test",
            file_name="poor_quality.txt",
            mime_type="text/plain",
            size=1000,
            text_content=poor_text,
            readability_score=0.3,  # Low readability
            complexity_score=0.8   # High complexity
        )
        
        issues = document_service._check_quality(analysis)
        
        assert isinstance(issues, list)
        
        # Should flag readability issues
        issue_types = [issue.get('type', '') for issue in issues]
        assert 'readability' in issue_types
    
    @pytest.mark.asyncio
    async def test_analyze_document_basic(self, document_service):
        """Test basic document analysis"""
        # Mock Google Drive service
        mock_file_content = b"This is a test document with business content about financial planning and strategic initiatives."
        mock_metadata = {
            'name': 'test_document.txt',
            'mimeType': 'text/plain',
            'size': len(mock_file_content)
        }
        
        with patch.object(document_service, '_get_file_metadata', return_value=mock_metadata), \
             patch.object(document_service, '_download_file', return_value=(mock_file_content, '/tmp/test.txt')):
            
            result = await document_service.analyze_document("test_file_id", "mock_token")
            
            assert isinstance(result, DocumentAnalysis)
            assert result.file_id == "test_file_id"
            assert result.file_name == "test_document.txt"
            assert result.mime_type == "text/plain"
            assert result.size == len(mock_file_content)
            assert result.text_content is not None
            assert len(result.text_content) > 0
            assert result.categories is not None
            assert len(result.categories) > 0
            assert result.keywords is not None
            assert len(result.keywords) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_document_with_ai(self, document_service, mock_openai_client):
        """Test document analysis with AI features"""
        # Mock OpenAI client
        with patch('document_intelligence_service.openai', Mock(return_value=mock_openai_client)):
            
            # Mock file content and metadata
            mock_file_content = b"This is a comprehensive business report discussing financial metrics, strategic planning, and market analysis."
            mock_metadata = {
                'name': 'business_report.pdf',
                'mimeType': 'application/pdf',
                'size': len(mock_file_content)
            }
            
            with patch.object(document_service, '_get_file_metadata', return_value=mock_metadata), \
                 patch.object(document_service, '_download_file', return_value=(mock_file_content, '/tmp/test.pdf')), \
                 patch.object(document_service, '_extract_from_pdf', return_value=mock_file_content.decode('utf-8')):
                
                result = await document_service.analyze_document("test_file_id", "mock_token")
                
                assert isinstance(result, DocumentAnalysis)
                assert result.summary is not None
                assert result.sentiment is not None
                assert result.extracted_entities is not None
                assert result.processing_method == "ai_enhanced"
                assert result.confidence_score > 0.5
    
    @pytest.mark.asyncio
    async def test_get_document_insights(self, document_service):
        """Test getting document insights"""
        # Mock basic analysis
        mock_analysis = DocumentAnalysis(
            file_id="test",
            file_name="test.pdf",
            mime_type="application/pdf",
            size=10000,
            text_content="Test document content",
            categories=["Reports"],
            keywords=["test", "document", "content"]
        )
        
        with patch.object(document_service, 'analyze_document', return_value=mock_analysis), \
             patch.object(document_service, '_find_similar_documents', return_value=[]), \
             patch.object(document_service, '_find_duplicate_documents', return_value=[]):
            
            result = await document_service.get_document_insights("test", "mock_token")
            
            assert isinstance(result, DocumentInsights)
            assert result.file_id == "test"
            assert result.recommended_tags is not None
            assert len(result.recommended_tags) > 0
            assert result.recommended_workflows is not None
            assert len(result.recommended_workflows) > 0
            assert result.compliance_issues is not None
            assert result.quality_issues is not None
    
    @pytest.mark.asyncio
    async def test_batch_analyze_documents(self, document_service):
        """Test batch document analysis"""
        # Create mock analyses
        mock_analyses = [
            DocumentAnalysis(
                file_id=f"test_{i}",
                file_name=f"test_{i}.txt",
                mime_type="text/plain",
                size=1000,
                text_content=f"Test document {i} content",
                categories=["General"]
            )
            for i in range(3)
        ]
        
        with patch.object(document_service, 'analyze_document', side_effect=mock_analyses):
            results = await document_service.batch_analyze_documents(
                ["test_0", "test_1", "test_2"], 
                "mock_token", 
                max_concurrent=2
            )
            
            assert isinstance(results, list)
            assert len(results) == 3
            assert all(isinstance(result, DocumentAnalysis) for result in results)
    
    @pytest.mark.asyncio
    async def test_analyze_document_insufficient_content(self, document_service):
        """Test analysis with insufficient content"""
        # Mock file with minimal content
        mock_file_content = b"Hi"
        mock_metadata = {
            'name': 'minimal.txt',
            'mimeType': 'text/plain',
            'size': 2
        }
        
        with patch.object(document_service, '_get_file_metadata', return_value=mock_metadata), \
             patch.object(document_service, '_download_file', return_value=(mock_file_content, '/tmp/minimal.txt')):
            
            result = await document_service.analyze_document("minimal_file", "mock_token")
            
            assert isinstance(result, DocumentAnalysis)
            assert result.file_id == "minimal_file"
            assert result.confidence_score == 0.0
            assert result.error_message == "Insufficient text content for analysis"
    
    @pytest.mark.asyncio
    async def test_analyze_document_error_handling(self, document_service):
        """Test error handling in document analysis"""
        # Mock error in file download
        with patch.object(document_service, '_download_file', side_effect=Exception("Download failed")):
            result = await document_service.analyze_document("error_file", "mock_token")
            
            assert isinstance(result, DocumentAnalysis)
            assert result.file_id == "error_file"
            assert result.confidence_score == 0.0
            assert result.error_message is not None
            assert "Download failed" in result.error_message

class TestDocumentIntelligenceRoutes:
    """Test Document Intelligence API Routes"""
    
    @pytest.fixture
    def client(self):
        """Create test Flask client"""
        from flask import Flask
        app = Flask(__name__)
        app.testing = True
        
        from document_intelligence_routes import register_document_intelligence_routes
        register_document_intelligence_routes(app)
        
        return app.test_client()
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/api/document-intelligence/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert 'data' in data
        assert data['data']['service'] == 'document_intelligence'
    
    def test_capabilities(self, client):
        """Test capabilities endpoint"""
        response = client.get('/api/document-intelligence/capabilities')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert 'data' in data
        assert 'service' in data['data']
        assert 'capabilities' in data['data']
        assert 'supported_formats' in data['data']
    
    def test_analyze_document_missing_params(self, client):
        """Test analyze document with missing parameters"""
        response = client.post('/api/document-intelligence/analyze')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['ok'] is False
        assert 'error' in data
    
    def test_analyze_document_missing_file_id(self, client):
        """Test analyze document with missing file_id"""
        response = client.post('/api/document-intelligence/analyze',
                             json={'access_token': 'test_token'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['ok'] is False
        assert 'file_id parameter is required' in data['error']
    
    @patch('document_intelligence_service.DocumentIntelligenceService.analyze_document')
    def test_analyze_document_success(self, mock_analyze, client):
        """Test successful document analysis"""
        # Mock analysis result
        mock_analysis = DocumentAnalysis(
            file_id="test",
            file_name="test.pdf",
            mime_type="application/pdf",
            size=10000,
            text_content="Test content",
            categories=["Reports"],
            keywords=["test", "content"],
            processing_time=2.5,
            confidence_score=0.8
        )
        mock_analyze.return_value = asyncio.run(asyncio.coroutine(lambda: mock_analysis)())
        
        response = client.post('/api/document-intelligence/analyze',
                             json={'file_id': 'test', 'access_token': 'test_token'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert 'data' in data
        
        result = data['data']
        assert result['file_id'] == "test"
        assert result['file_name'] == "test.pdf"
        assert result['categories'] == ["Reports"]
        assert result['keywords'] == ["test", "content"]
        assert result['processing_time'] == 2.5
        assert result['confidence_score'] == 0.8
    
    def test_batch_analyze_documents_missing_params(self, client):
        """Test batch analyze with missing parameters"""
        response = client.post('/api/document-intelligence/analyze/batch')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['ok'] is False
        assert 'error' in data
    
    def test_batch_analyze_too_many_files(self, client):
        """Test batch analyze with too many files"""
        file_ids = [f"file_{i}" for i in range(51)]  # 51 files (limit is 50)
        
        response = client.post('/api/document-intelligence/analyze/batch',
                             json={'file_ids': file_ids, 'access_token': 'test_token'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['ok'] is False
        assert 'Maximum 50 files per batch' in data['error']
    
    @patch('document_intelligence_service.DocumentIntelligenceService.get_document_insights')
    def test_get_document_insights_success(self, mock_insights, client):
        """Test successful document insights"""
        # Mock insights result
        mock_insight = DocumentInsights(
            file_id="test",
            related_documents=[],
            similar_documents=[],
            recommended_tags=["Reports", "Test"],
            recommended_workflows=[
                {"name": "Create Summary", "description": "Generate document summary"}
            ]
        )
        mock_insights.return_value = asyncio.run(asyncio.coroutine(lambda: mock_insight)())
        
        response = client.get('/api/document-intelligence/insights?file_id=test&access_token=test_token')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert 'data' in data
        
        result = data['data']
        assert result['file_id'] == "test"
        assert result['recommended_tags'] == ["Reports", "Test"]
        assert len(result['recommended_workflows']) > 0
    
    def test_get_document_insights_missing_params(self, client):
        """Test get insights with missing parameters"""
        response = client.get('/api/document-intelligence/insights')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['ok'] is False
        assert 'file_id parameter is required' in data['error']

# Performance and stress tests
class TestDocumentIntelligencePerformance:
    """Performance tests for document intelligence"""
    
    @pytest.mark.asyncio
    async def test_concurrent_document_analysis(self):
        """Test concurrent document analysis"""
        service = DocumentIntelligenceService()
        
        # Create mock documents
        mock_documents = [
            {
                'file_content': f"This is test document {i} with business content for analysis.",
                'metadata': {'name': f'test_{i}.txt', 'mimeType': 'text/plain', 'size': 100}
            }
            for i in range(10)
        ]
        
        async def mock_analyze(file_id, token):
            # Simulate analysis work
            await asyncio.sleep(0.1)
            return DocumentAnalysis(
                file_id=file_id,
                file_name=f"doc_{file_id}.txt",
                mime_type="text/plain",
                size=100,
                text_content=mock_documents[int(file_id.split('_')[1])]['file_content'],
                categories=["General"],
                keywords=["test", "document"],
                processing_time=0.1,
                confidence_score=0.8
            )
        
        with patch.object(service, 'analyze_document', side_effect=mock_analyze):
            file_ids = [f"file_{i}" for i in range(10)]
            results = await service.batch_analyze_documents(file_ids, "test_token", max_concurrent=5)
            
            assert len(results) == 10
            assert all(isinstance(result, DocumentAnalysis) for result in results)
    
    @pytest.mark.asyncio
    async def test_large_document_processing(self):
        """Test processing of large documents"""
        service = DocumentIntelligenceService()
        
        # Create large text content (simulating large document)
        large_content = "This is a business document. " * 1000  # About 25KB
        mock_metadata = {
            'name': 'large_document.txt',
            'mimeType': 'text/plain',
            'size': len(large_content.encode('utf-8'))
        }
        
        with patch.object(service, '_get_file_metadata', return_value=mock_metadata), \
             patch.object(service, '_download_file', return_value=(large_content.encode('utf-8'), '/tmp/large.txt')):
            
            result = await service.analyze_document("large_doc", "test_token")
            
            assert isinstance(result, DocumentAnalysis)
            assert result.file_id == "large_doc"
            assert result.size > 20000  # Should be large
            assert result.text_content is not None
            assert len(result.text_content) > 20000
            assert result.processing_time is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])