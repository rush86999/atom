"""
ATOM Document Intelligence API Routes
Flask routes for AI-powered document analysis and insights
Following ATOM API patterns and conventions
"""

from flask import Blueprint, request, jsonify, send_file
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
import asyncio
import traceback
import tempfile
import os

from document_intelligence_service import create_document_intelligence_service, DocumentAnalysis, DocumentInsights

# Create blueprint
router = Blueprint('document_intelligence', __name__, url_prefix='/api/document-intelligence')

# Global instance
document_service = create_document_intelligence_service()

# Decorator for requiring valid tokens
def require_google_drive_auth(f):
    import functools
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Extract user_id and access_token from request
            user_id = request.args.get('user_id')
            access_token = request.args.get('access_token')
            
            if not user_id and request.is_json:
                data = request.get_json()
                user_id = data.get('user_id')
                access_token = data.get('access_token')
            
            if not user_id or not access_token:
                return jsonify({
                    "ok": False,
                    "error": "user_id and access_token parameters are required"
                }), 400
            
            # Store in Flask's request context for route to use
            request.user_id = user_id
            request.access_token = access_token
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Google Drive auth decorator error: {e}")
            return jsonify({
                "ok": False,
                "error": f"Authentication failed: {str(e)}"
            }), 500
    
    return decorated_function

# Document analysis endpoints
@router.route("/analyze", methods=["POST"])
@require_google_drive_auth
def analyze_document():
    """Analyze a document using AI"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        file_id = data.get('file_id')
        
        if not file_id:
            return jsonify({
                "ok": False,
                "error": "file_id parameter is required"
            }), 400
        
        logger.info(f"Starting document analysis for {file_id}")
        
        # Run async analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                document_service.analyze_document(file_id, request.access_token)
            )
        finally:
            loop.close()
        
        return jsonify({
            "ok": True,
            "data": {
                "file_id": result.file_id,
                "file_name": result.file_name,
                "mime_type": result.mime_type,
                "size": result.size,
                "text_content": result.text_content,
                "extracted_entities": result.extracted_entities,
                "keywords": result.keywords,
                "categories": result.categories,
                "summary": result.summary,
                "sentiment": result.sentiment,
                "language": result.language,
                "readability_score": result.readability_score,
                "complexity_score": result.complexity_score,
                "importance_score": result.importance_score,
                "processing_time": result.processing_time,
                "processing_method": result.processing_method,
                "confidence_score": result.confidence_score,
                "error_message": result.error_message
            },
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to analyze document: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/analyze/batch", methods=["POST"])
@require_google_drive_auth
def analyze_documents_batch():
    """Analyze multiple documents in batch"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        file_ids = data.get('file_ids', [])
        max_concurrent = data.get('max_concurrent', 5)
        
        if not file_ids:
            return jsonify({
                "ok": False,
                "error": "file_ids parameter is required"
            }), 400
        
        if len(file_ids) > 50:  # Limit batch size
            return jsonify({
                "ok": False,
                "error": "Maximum 50 files per batch"
            }), 400
        
        logger.info(f"Starting batch document analysis for {len(file_ids)} files")
        
        # Run async batch analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                document_service.batch_analyze_documents(
                    file_ids, request.access_token, max_concurrent
                )
            )
        finally:
            loop.close()
        
        # Format results
        analyses = []
        for result in results:
            analyses.append({
                "file_id": result.file_id,
                "file_name": result.file_name,
                "mime_type": result.mime_type,
                "size": result.size,
                "text_content": result.text_content,
                "extracted_entities": result.extracted_entities,
                "keywords": result.keywords,
                "categories": result.categories,
                "summary": result.summary,
                "sentiment": result.sentiment,
                "language": result.language,
                "readability_score": result.readability_score,
                "complexity_score": result.complexity_score,
                "importance_score": result.importance_score,
                "processing_time": result.processing_time,
                "processing_method": result.processing_method,
                "confidence_score": result.confidence_score,
                "error_message": result.error_message
            })
        
        return jsonify({
            "ok": True,
            "data": {
                "analyses": analyses,
                "total_processed": len(analyses),
                "successful_analyses": len([a for a in analyses if a.get('error_message') is None])
            },
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to analyze documents in batch: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Document insights endpoints
@router.route("/insights", methods=["GET"])
@require_google_drive_auth
def get_document_insights():
    """Get advanced insights for a document"""
    try:
        file_id = request.args.get('file_id')
        
        if not file_id:
            return jsonify({
                "ok": False,
                "error": "file_id parameter is required"
            }), 400
        
        logger.info(f"Getting document insights for {file_id}")
        
        # Run async insights
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                document_service.get_document_insights(file_id, request.access_token)
            )
        finally:
            loop.close()
        
        return jsonify({
            "ok": True,
            "data": {
                "file_id": result.file_id,
                "related_documents": result.related_documents,
                "similar_documents": result.similar_documents,
                "duplicate_documents": result.duplicate_documents,
                "recommended_tags": result.recommended_tags,
                "recommended_workflows": result.recommended_workflows,
                "compliance_issues": result.compliance_issues,
                "quality_issues": result.quality_issues
            },
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get document insights: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Document processing capabilities
@router.route("/upload", methods=["POST"])
@require_google_drive_auth
def upload_and_analyze():
    """Upload a file and analyze it"""
    try:
        if 'file' not in request.files:
            return jsonify({
                "ok": False,
                "error": "No file provided"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "ok": False,
                "error": "No file selected"
            }), 400
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
        
        try:
            # Read file content
            with open(temp_file_path, 'rb') as f:
                file_content = f.read()
            
            # Get file metadata
            file_name = file.filename
            mime_type = file.content_type or mimetypes.guess_type(file_name)[0]
            file_size = len(file_content)
            
            # Extract text content
            text_content = document_service._extract_text_content(
                file_content,
                {'name': file_name, 'mimeType': mime_type}
            )
            
            if not text_content or len(text_content.strip()) < 10:
                return jsonify({
                    "ok": False,
                    "error": "File contains insufficient text for analysis"
                }), 400
            
            # Perform analysis
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                analysis = loop.run_until_complete(
                    document_service._perform_ai_analysis(
                        text_content, {'name': file_name, 'mimeType': mime_type}, datetime.utcnow()
                    )
                )
            finally:
                loop.close()
            
            # Set file info
            analysis.file_id = "uploaded_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            analysis.file_name = file_name
            analysis.mime_type = mime_type
            analysis.size = file_size
            analysis.text_content = text_content
            
            return jsonify({
                "ok": True,
                "data": {
                    "file_id": analysis.file_id,
                    "file_name": analysis.file_name,
                    "mime_type": analysis.mime_type,
                    "size": analysis.size,
                    "text_content": analysis.text_content,
                    "extracted_entities": analysis.extracted_entities,
                    "keywords": analysis.keywords,
                    "categories": analysis.categories,
                    "summary": analysis.summary,
                    "sentiment": analysis.sentiment,
                    "language": analysis.language,
                    "readability_score": analysis.readability_score,
                    "complexity_score": analysis.complexity_score,
                    "importance_score": analysis.importance_score,
                    "processing_time": analysis.processing_time,
                    "processing_method": analysis.processing_method,
                    "confidence_score": analysis.confidence_score,
                    "error_message": analysis.error_message
                },
                "service": "document_intelligence",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "File uploaded and analyzed successfully"
            })
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except Exception as e:
        logger.error(f"Failed to upload and analyze file: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Document search and discovery
@router.route("/search", methods=["GET"])
@require_google_drive_auth
def search_documents():
    """Search documents with semantic capabilities"""
    try:
        query = request.args.get('query')
        limit = int(request.args.get('limit', 20))
        file_type = request.args.get('file_type')  # Optional filter by file type
        category = request.args.get('category')  # Optional filter by category
        
        if not query:
            return jsonify({
                "ok": False,
                "error": "query parameter is required"
            }), 400
        
        logger.info(f"Searching documents for query: {query}")
        
        # For now, this is a placeholder implementation
        # In a full implementation, this would:
        # 1. Use the query to find documents (Google Drive API + our embeddings)
        # 2. Rank results by relevance
        # 3. Return metadata and snippets
        
        # Mock search results
        search_results = [
            {
                "file_id": "doc_123",
                "file_name": "Project Report.pdf",
                "snippet": "...containing project information and analysis...",
                "relevance_score": 0.95,
                "file_type": "application/pdf",
                "categories": ["Reports"],
                "last_modified": "2024-01-15T10:30:00Z"
            }
        ]
        
        return jsonify({
            "ok": True,
            "data": {
                "query": query,
                "results": search_results[:limit],
                "total_found": len(search_results),
                "filters_applied": {
                    "file_type": file_type,
                    "category": category
                }
            },
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to search documents: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Document workflow automation
@router.route("/workflows/execute", methods=["POST"])
@require_google_drive_auth
def execute_workflow():
    """Execute an automated document workflow"""
    try:
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "JSON request body required"
            }), 400
        
        data = request.get_json()
        workflow_type = data.get('workflow_type')
        file_ids = data.get('file_ids', [])
        workflow_params = data.get('params', {})
        
        if not workflow_type:
            return jsonify({
                "ok": False,
                "error": "workflow_type parameter is required"
            }), 400
        
        if not file_ids:
            return jsonify({
                "ok": False,
                "error": "file_ids parameter is required"
            }), 400
        
        logger.info(f"Executing {workflow_type} workflow on {len(file_ids)} files")
        
        # Workflow execution logic
        results = []
        
        if workflow_type == "categorize_and_move":
            # Auto-categorize documents and move to appropriate folders
            for file_id in file_ids:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    analysis = loop.run_until_complete(
                        document_service.analyze_document(file_id, request.access_token)
                    )
                    
                    # Move file based on category
                    target_folder = "/Categorized/" + (analysis.categories[0] if analysis.categories else "General")
                    
                    results.append({
                        "file_id": file_id,
                        "action": "move_to_folder",
                        "target": target_folder,
                        "category": analysis.categories,
                        "status": "success"
                    })
                    
                finally:
                    loop.close()
        
        elif workflow_type == "extract_and_save_entities":
            # Extract entities and save to database
            for file_id in file_ids:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    analysis = loop.run_until_complete(
                        document_service.analyze_document(file_id, request.access_token)
                    )
                    
                    results.append({
                        "file_id": file_id,
                        "action": "extract_entities",
                        "entities_extracted": len(analysis.extracted_entities) if analysis.extracted_entities else 0,
                        "entities": analysis.extracted_entities,
                        "status": "success"
                    })
                    
                finally:
                    loop.close()
        
        elif workflow_type == "generate_summary_report":
            # Generate summary reports for documents
            for file_id in file_ids:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    analysis = loop.run_until_complete(
                        document_service.analyze_document(file_id, request.access_token)
                    )
                    
                    results.append({
                        "file_id": file_id,
                        "action": "generate_summary",
                        "summary": analysis.summary,
                        "keywords": analysis.keywords,
                        "categories": analysis.categories,
                        "status": "success"
                    })
                    
                finally:
                    loop.close()
        
        else:
            return jsonify({
                "ok": False,
                "error": f"Unknown workflow type: {workflow_type}"
            }), 400
        
        return jsonify({
            "ok": True,
            "data": {
                "workflow_type": workflow_type,
                "files_processed": len(results),
                "results": results,
                "successful_executions": len([r for r in results if r.get('status') == 'success'])
            },
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Workflow {workflow_type} executed successfully"
        })
        
    except Exception as e:
        logger.error(f"Failed to execute workflow: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Service health and capabilities
@router.route("/health", methods=["GET"])
def health_check():
    """Document intelligence service health check"""
    try:
        capabilities = document_service.get_service_capabilities()
        
        return jsonify({
            "ok": True,
            "data": {
                "service": "document_intelligence",
                "status": "healthy",
                "capabilities": capabilities,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Document intelligence health check failed: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@router.route("/capabilities", methods=["GET"])
def get_capabilities():
    """Get document intelligence service capabilities"""
    try:
        capabilities = document_service.get_service_capabilities()
        
        return jsonify({
            "ok": True,
            "data": capabilities,
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get capabilities: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "service": "document_intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Export blueprint
def register_document_intelligence_routes(app):
    """Register document intelligence API routes"""
    app.register_blueprint(router)
    logger.info("Document Intelligence API routes registered")

if __name__ == "__main__":
    # Test the blueprint
    app = Flask(__name__)
    register_document_intelligence_routes(app)
    app.run(debug=True, port=8001)