"""
ATOM Document Logic Service
Unified ingestion for Google Docs, Word, Excel, and PDF to extract business rules.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
from core.integration_service import IntegrationService

try:
    from integrations.atom_ingestion_pipeline import atom_ingestion_pipeline, RecordType
    from ai_enhanced_service import ai_enhanced_service, AIRequest, AITaskType
except ImportError:
    logging.warning("Core services not available for Document Logic Service")

logger = logging.getLogger(__name__)

class DocumentType(Enum):
    GOOGLE_DOC = "google_doc"
    MS_WORD = "docx"
    MS_EXCEL = "xlsx"
    PDF = "pdf"
    CSV = "csv"

class DocumentLogicService(IntegrationService):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(tenant_id, config)
        logger.info(f"DocumentLogicService initialized for tenant {self.tenant_id}")

    async def ingest_document(self, file_path: str, doc_type: DocumentType, workspace_id: str):
        """
        Parses a document and extracts logic/rules to be stored in LanceDB.
        """
        logger.info(f"Ingesting {doc_type.value} from {file_path}")
        
        # 1. Extraction (Simulated for Now)
        content = self._extract_text(file_path, doc_type)
        
        # 2. AI Processing: Extract Logic Snippets
        logic_snippets = await self._extract_logic_with_ai(content)
        
        # 3. Ingest to Memory
        for snippet in logic_snippets:
            atom_ingestion_pipeline.ingest_record(
                app_type=doc_type.value,
                record_type="document",
                data={
                    "file_path": file_path,
                    "logic_snippet": snippet,
                    "workspace_id": workspace_id,
                    "ingested_at": datetime.now(timezone.utc).isoformat()
                }
            )
        
        return {"snippets_extracted": len(logic_snippets)}

    def _extract_text(self, file_path: str, doc_type: DocumentType) -> str:
        # Placeholder for actual library-based extraction (PyPDF2, openpyxl, etc.)
        return "Example business rule: All orders over $500 require CFO approval."

    async def _extract_logic_with_ai(self, content: str) -> List[str]:
        """
        Uses LLM to find discrete business rules/logic in unstructured text.
        """
        # Simulated AI return
        return ["orders_over_500_require_cfo_approval"]

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return Document Logic service capabilities.

        Returns:
            Dict with operations, parameters, rate limits
        """
        return {
            "operations": [
                {
                    "id": "parse_document",
                    "name": "Parse Document",
                    "description": "Parse document and extract business rules",
                    "parameters": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to document file",
                            "required": True
                        },
                        "doc_type": {
                            "type": "string",
                            "description": "Document type (google_doc, docx, xlsx, pdf, csv)",
                            "required": True
                        },
                        "workspace_id": {
                            "type": "string",
                            "description": "Workspace ID for tenant isolation",
                            "required": True
                        }
                    },
                    "complexity": 2
                },
                {
                    "id": "extract_text",
                    "name": "Extract Text",
                    "description": "Extract text content from document",
                    "parameters": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to document file",
                            "required": True
                        },
                        "doc_type": {
                            "type": "string",
                            "description": "Document type",
                            "required": True
                        }
                    },
                    "complexity": 1
                },
                {
                    "id": "classify_document",
                    "name": "Classify Document",
                    "description": "Classify document by content type",
                    "parameters": {
                        "content": {
                            "type": "string",
                            "description": "Document content to classify",
                            "required": True
                        }
                    },
                    "complexity": 2
                },
                {
                    "id": "merge_documents",
                    "name": "Merge Documents",
                    "description": "Merge multiple documents",
                    "parameters": {
                        "file_paths": {
                            "type": "array",
                            "description": "List of file paths to merge",
                            "required": True
                        },
                        "output_format": {
                            "type": "string",
                            "description": "Output format (pdf, docx)",
                            "required": False
                        }
                    },
                    "complexity": 3
                }
            ],
            "rate_limits": {
                "requests_per_minute": 50,
                "max_file_size_mb": 50
            },
            "supports_webhooks": False
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Check if Document Logic service is healthy.

        Returns:
            Dict with health status
        """
        return {
            "healthy": True,
            "message": "Document Logic service is operational",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "tenant_id": self.tenant_id
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Document Logic operation with tenant context.

        Args:
            operation: Operation name (parse_document, extract_text, classify_document, merge_documents)
            parameters: Operation parameters
            context: Tenant context dict

        Returns:
            Dict with success, result, error, details

        Raises:
            NotImplementedError: If operation not supported
        """
        # Validate tenant context
        if context:
            tenant_id = context.get("tenant_id")
            if tenant_id != self.tenant_id:
                logger.error(f"Tenant ID mismatch: expected {self.tenant_id}, got {tenant_id}")
                return {
                    "success": False,
                    "error": "Tenant validation failed",
                    "details": {"tenant_mismatch": True}
                }

        try:
            if operation == "parse_document":
                return await self._parse_document(parameters)
            elif operation == "extract_text":
                return self._extract_text_operation(parameters)
            elif operation == "classify_document":
                return await self._classify_document(parameters)
            elif operation == "merge_documents":
                return await self._merge_documents(parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "details": {"available_operations": ["parse_document", "extract_text", "classify_document", "merge_documents"]}
                }
        except Exception as e:
            logger.error(f"Error executing operation {operation}: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"operation": operation}
            }

    async def _parse_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse document and extract business rules."""
        file_path = params.get("file_path")
        doc_type_str = params.get("doc_type")
        workspace_id = params.get("workspace_id")

        if not file_path or not doc_type_str:
            return {
                "success": False,
                "error": "file_path and doc_type are required",
                "details": {}
            }

        try:
            doc_type = DocumentType(doc_type_str)
            result = await self.ingest_document(file_path, doc_type, workspace_id)

            return {
                "success": True,
                "result": result,
                "details": {"file_path": file_path, "doc_type": doc_type_str}
            }
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid document type: {doc_type_str}",
                "details": {"valid_types": [dt.value for dt in DocumentType]}
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {"file_path": file_path}
            }

    def _extract_text_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from document."""
        file_path = params.get("file_path")
        doc_type_str = params.get("doc_type")

        if not file_path or not doc_type_str:
            return {
                "success": False,
                "error": "file_path and doc_type are required",
                "details": {}
            }

        try:
            doc_type = DocumentType(doc_type_str)
            content = self._extract_text(file_path, doc_type)

            return {
                "success": True,
                "result": {"content": content, "file_path": file_path},
                "details": {}
            }
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid document type: {doc_type_str}",
                "details": {}
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {"file_path": file_path}
            }

    async def _classify_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Classify document by content type."""
        content = params.get("content")

        if not content:
            return {
                "success": False,
                "error": "content is required",
                "details": {}
            }

        # Simple classification based on keywords
        content_lower = content.lower()
        if any(keyword in content_lower for keyword in ["invoice", "bill", "payment"]):
            doc_class = "financial"
        elif any(keyword in content_lower for keyword in ["contract", "agreement", "legal"]):
            doc_class = "legal"
        elif any(keyword in content_lower for keyword in ["policy", "procedure", "handbook"]):
            doc_class = "policy"
        else:
            doc_class = "general"

        return {
            "success": True,
            "result": {"classification": doc_class, "confidence": 0.8},
            "details": {"content_length": len(content)}
        }

    async def _merge_documents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple documents."""
        file_paths = params.get("file_paths", [])
        output_format = params.get("output_format", "pdf")

        if not file_paths:
            return {
                "success": False,
                "error": "file_paths is required",
                "details": {}
            }

        # Placeholder for actual merge logic
        return {
            "success": True,
            "result": {
                "merged_file": "merged_document.pdf",
                "source_count": len(file_paths),
                "output_format": output_format
            },
            "details": {"file_paths": file_paths}
        }
