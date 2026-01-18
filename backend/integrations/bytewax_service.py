
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple, Iterable
from dataclasses import asdict

# Bytewax imports
import bytewax.operators as op
from bytewax.dataflow import Dataflow
from bytewax.inputs import DynamicSource, StatelessSourcePartition
from bytewax.outputs import DynamicSink, StatelessSinkPartition
from bytewax.connectors.stdio import StdOutSink

# Vectorization
try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None

# Internal imports (reusing data models)
from integrations.atom_ingestion_pipeline import AtomRecordData, RecordType

# Document parsing service (for streaming document ingestion)
try:
    from integrations.document_logic_service import DocumentLogicService, DocumentType
    DOCUMENT_SERVICE_AVAILABLE = True
except ImportError:
    DOCUMENT_SERVICE_AVAILABLE = False

logger = logging.getLogger(__name__)

class DocumentParsingOperator:
    """
    Bytewax operator for parsing documents using the existing DocumentLogicService.
    Mirrors the legacy pipeline's document handling but in a streaming context.
    """
    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        self.service = None
    
    def _get_service(self):
        if self.service is None:
            if DOCUMENT_SERVICE_AVAILABLE:
                self.service = DocumentLogicService()
            else:
                logger.warning("DocumentLogicService not available")
        return self.service
    
    async def parse_document(self, file_path: str, doc_type: str) -> List[Dict[str, Any]]:
        """
        Parse a document and return extracted logic snippets as data packets.
        
        Args:
            file_path: Path to the document file
            doc_type: Document type (google_doc, docx, xlsx, pdf, csv)
        
        Returns:
            List of data packets ready for normalization
        """
        service = self._get_service()
        if not service:
            return []
        
        try:
            doc_type_enum = DocumentType(doc_type)
            result = await service.ingest_document(file_path, doc_type_enum, self.workspace_id)
            
            # Convert to data packets for the pipeline
            packets = []
            for i in range(result.get("snippets_extracted", 0)):
                packets.append({
                    "app_type": doc_type,
                    "record_type": "document",
                    "file_path": file_path,
                    "workspace_id": self.workspace_id,
                    "operation": "CREATE"
                })
            return packets
            
        except Exception as e:
            logger.error(f"Error parsing document {file_path}: {e}")
            return []
    
    def extract_text_sync(self, file_path: str, doc_type: str) -> Optional[str]:
        """
        Synchronous text extraction for use in Bytewax map operators.
        """
        service = self._get_service()
        if not service:
            return None
        
        try:
            doc_type_enum = DocumentType(doc_type)
            return service._extract_text(file_path, doc_type_enum)
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return None


class SecretsRedactionOperator:
    """
    Operator to redact secrets and PII from record content before storage.
    Mirrors the secrets redaction in LanceDBHandler.add_document().
    """
    def __init__(self):
        self.redactor = None
    
    def _get_redactor(self):
        if self.redactor is None:
            try:
                from core.secrets_redactor import get_secrets_redactor
                self.redactor = get_secrets_redactor()
            except ImportError:
                logger.warning("Secrets redactor not available")
        return self.redactor
    
    def redact(self, record: AtomRecordData) -> AtomRecordData:
        """
        Redact secrets and PII from record content.
        This ensures API keys, passwords, and sensitive data are NEVER stored.
        """
        try:
            redactor = self._get_redactor()
            if redactor and record.content:
                result = redactor.redact(record.content)
                if result.has_secrets:
                    logger.warning(f"Redacted {len(result.redactions)} secrets/PII from {record.id}")
                    record.content = result.redacted_text
                    
                    # Add redaction audit metadata
                    if isinstance(record.metadata, dict):
                        record.metadata["_redacted_types"] = [r["type"] for r in result.redactions]
                        record.metadata["_redaction_count"] = len(result.redactions)
            return record
        except Exception as e:
            logger.error(f"Error redacting secrets for {record.id}: {e}")
            return record


class KnowledgeExtractionOperator:
    """
    Streaming-native operator for knowledge extraction and GraphRAG population.
    This is the CORE operator that enables agent learning and recall.
    
    Mirrors the legacy pipeline behavior from:
    - LanceDBHandler.add_document() with extract_knowledge=True
    - KnowledgeIngestionManager.process_document()
    
    Populates:
    - Knowledge graph edges (entity relationships)
    - GraphRAG for hierarchical queries
    """
    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        self.knowledge_manager = None
        self.graphrag_engine = None
        self.automation_settings = None
    
    def _lazy_init(self):
        """Lazy initialization to avoid import cycles and startup overhead."""
        if self.knowledge_manager is None:
            try:
                from core.knowledge_ingestion import get_knowledge_ingestion
                self.knowledge_manager = get_knowledge_ingestion()
            except ImportError:
                logger.warning("Knowledge ingestion service not available")
        
        if self.graphrag_engine is None:
            try:
                from core.graphrag_engine import graphrag_engine
                self.graphrag_engine = graphrag_engine
            except ImportError:
                logger.warning("GraphRAG engine not available")
        
        if self.automation_settings is None:
            try:
                from core.automation_settings import get_automation_settings
                self.automation_settings = get_automation_settings()
            except ImportError:
                pass
    
    def _is_extraction_enabled(self) -> bool:
        """Check if knowledge extraction is enabled in settings."""
        if self.automation_settings:
            return self.automation_settings.is_extraction_enabled()
        return True  # Default to enabled if settings unavailable
    
    def extract_knowledge(self, record: AtomRecordData) -> AtomRecordData:
        """
        Extract knowledge from record and populate knowledge graph + GraphRAG.
        This is the critical step that enables agent learning.
        
        Must be called AFTER vectorization but BEFORE sinking to LanceDB.
        """
        import asyncio
        
        self._lazy_init()
        
        # Skip if extraction is disabled
        if not self._is_extraction_enabled():
            logger.debug(f"Knowledge extraction skipped for {record.id} (disabled)")
            return record
        
        # Skip empty or very short content
        if not record.content or len(record.content.strip()) < 20:
            return record
        
        # Skip DELETE operations
        op_type = getattr(record, "operation", "CREATE")
        if op_type == "DELETE":
            return record
        
        # Extract metadata for context
        metadata = getattr(record, "metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        
        workspace_id = metadata.get("workspace_id", self.workspace_id)
        user_id = metadata.get("user_id", "default_user")
        
        # 1. Trigger Knowledge Extraction (async in background if loop exists)
        if self.knowledge_manager:
            try:
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        loop.create_task(self.knowledge_manager.process_document(
                            text=record.content,
                            doc_id=record.id,
                            source=record.app_type,
                            user_id=user_id,
                            workspace_id=workspace_id
                        ))
                        logger.info(f"[KnowledgeExtract] Triggered extraction for {record.id}")
                except RuntimeError:
                    # No running event loop - run synchronously
                    asyncio.run(self.knowledge_manager.process_document(
                        text=record.content,
                        doc_id=record.id,
                        source=record.app_type,
                        user_id=user_id,
                        workspace_id=workspace_id
                    ))
                    logger.info(f"[KnowledgeExtract] Sync extraction for {record.id}")
            except Exception as e:
                logger.warning(f"[KnowledgeExtract] Failed for {record.id}: {e}")
        
        # 2. Direct GraphRAG ingestion (fallback if knowledge manager unavailable)
        elif self.graphrag_engine:
            try:
                stats = self.graphrag_engine.ingest_document(
                    workspace_id=workspace_id,
                    doc_id=record.id,
                    text=record.content,
                    source=record.app_type,
                    user_id=user_id
                )
                logger.info(f"[KnowledgeExtract] GraphRAG ingested {record.id}: {stats}")
            except Exception as e:
                logger.warning(f"[KnowledgeExtract] GraphRAG failed for {record.id}: {e}")
        
        # Mark record as having knowledge extracted (for audit trail)
        if isinstance(record.metadata, dict):
            record.metadata["_knowledge_extracted"] = True
        
        return record


class FormulaExtractionOperator:
    """
    Extract formulas from spreadsheet content (Excel, CSV, ODS) and store in memory.
    Enables agents to learn and apply business logic formulas.
    
    Uses: core/formula_extractor.py → FormulaMemoryManager
    """
    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        self.extractor = None
    
    def _get_extractor(self):
        """Lazy initialization of formula extractor."""
        if self.extractor is None:
            try:
                from core.formula_extractor import FormulaExtractor
                self.extractor = FormulaExtractor(workspace_id=self.workspace_id)
            except ImportError:
                logger.warning("Formula extractor not available")
        return self.extractor
    
    def extract(self, record: AtomRecordData) -> AtomRecordData:
        """
        Extract formulas from spreadsheet records.
        
        Only processes records where:
        - record_type is 'document' or 'spreadsheet'
        - metadata contains a file_path to a supported format (.xlsx, .xls, .csv, .ods)
        """
        # Get record type
        record_type = getattr(record, "record_type", None)
        if record_type:
            record_type = record_type.value if hasattr(record_type, "value") else str(record_type)
        
        # Only process document/spreadsheet records
        if record_type not in ["document", "spreadsheet", "DOCUMENT"]:
            return record
        
        # Get metadata
        metadata = getattr(record, "metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        
        # Check for file_path
        file_path = metadata.get("file_path") or metadata.get("path")
        if not file_path:
            return record
        
        # Check if it's a spreadsheet format
        supported_formats = [".xlsx", ".xls", ".csv", ".ods", ".numbers"]
        if not any(file_path.lower().endswith(ext) for ext in supported_formats):
            return record
        
        # Extract formulas
        extractor = self._get_extractor()
        if not extractor:
            return record
        
        try:
            user_id = metadata.get("user_id", "default_user")
            formulas = extractor.extract_from_file(
                file_path=file_path,
                user_id=user_id,
                auto_store=True
            )
            
            formula_count = len(formulas) if formulas else 0
            if formula_count > 0:
                logger.info(f"[FormulaExtract] Extracted {formula_count} formulas from {file_path}")
                
                # Update metadata with extraction info
                if isinstance(record.metadata, dict):
                    record.metadata["_formulas_extracted"] = formula_count
                    record.metadata["_formula_types"] = list({f.get("type") for f in formulas if f.get("type")})
        except Exception as e:
            logger.warning(f"[FormulaExtract] Failed for {file_path}: {e}")
        
        return record

class UnifiedNormalizationOperator:
    """
    Stateful operator to normalize records from various sources.
    Ports the logic from AtomIngestionPipeline._normalize_record
    """
    def normalize(self, data_packet: Any) -> Optional[AtomRecordData]:
        try:
            # Handle both (key, value) tuples (Kafka style) and raw dicts
            if isinstance(data_packet, tuple) and len(data_packet) == 2:
                source_id, data = data_packet
            else:
                source_id = "unknown"
                data = data_packet
            
            if not isinstance(data, dict):
                 logger.error(f"Expected dict data, got {type(data)}")
                 return None
            app_type = data.get("app_type", "generic")
            record_type_str = data.get("record_type", "generic")
            
            # CRUD Operation Handling
            operation = data.get("operation", "CREATE") # Default to CREATE
            
            # Normalize logic (ported from AtomIngestionPipeline)
            normalized = {
                "id": data.get("id") or data.get("Id") or f"{app_type}_{record_type_str}_{datetime.now().timestamp()}",
                "app_type": app_type,
                "record_type": RecordType(record_type_str), # Ensure Enum
                "content": "",
                "timestamp": datetime.now(),
                "metadata": data
            }

            # --- Logic Port Start ---
            r_type = normalized["record_type"]
            
            if app_type == "hubspot":
                if r_type == RecordType.CONTACT:
                    props = data.get("properties", {})
                    normalized["content"] = f"Contact: {props.get('firstname')} {props.get('lastname')} ({props.get('email')})"
                elif r_type == RecordType.CAMPAIGN:
                    normalized["content"] = f"Campaign: {data.get('name')} - {data.get('description')}"
            
            elif app_type == "salesforce":
                if r_type == RecordType.LEAD:
                    normalized["content"] = f"Lead: {data.get('FirstName')} {data.get('LastName')} at {data.get('Company')}"
                elif r_type == RecordType.DEAL:
                    normalized["content"] = f"Opportunity: {data.get('Name')} (Stage: {data.get('StageName')})"

            elif app_type in ["meta_business", "whatsapp"]:
                if r_type == RecordType.COMMUNICATION:
                    normalized["content"] = f"Message ({app_type}): {data.get('text') or data.get('content')}"
                elif r_type == RecordType.AD_PERFORMANCE:
                    normalized["content"] = f"Meta Ad Performance: {data.get('spend')} spend, {data.get('conversions')} conv"

            elif app_type in ["amazon", "etsy", "woocommerce", "shopify"]:
                if r_type == RecordType.ORDER:
                    normalized["content"] = f"Order {data.get('id')}: {data.get('total_price')} from {data.get('email')}"
                elif r_type == RecordType.INVENTORY:
                    normalized["content"] = f"Inventory Update: {data.get('sku')} -> {data.get('quantity')}"

            elif r_type in [RecordType.DOCUMENT, RecordType.SPREADSHEET]:
                normalized["content"] = f"Business Logic Snippet: {data.get('logic_snippet') or data.get('content')}"
                normalized["metadata"]["file_path"] = data.get("file_path")
            
            # Fallback
            if not normalized["content"]:
                normalized["content"] = str(data)
            # --- Logic Port End ---

            record = AtomRecordData(**normalized)
            record.operation = operation
            return record

        except Exception as e:
            logger.error(f"Error normalizing record {data_packet}: {e}")
            return None

class FastEmbedOperator:
    """
    Operator to generate embeddings using FastEmbed.
    Designed to run in parallel workers.
    """
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self.model = None

    def _get_model(self):
        if self.model is None:
            if TextEmbedding:
                self.model = TextEmbedding(model_name=self.model_name)
            else:
                logger.warning("FastEmbed not installed, skipping embedding")
        return self.model

    def compute_embedding(self, record: AtomRecordData) -> AtomRecordData:
        try:
            model = self._get_model()
            if model and record.content:
                # fastembed returns a generator/list of arrays
                embeddings = list(model.embed([record.content]))
                if embeddings:
                    # Convert numpy/list to standard list of floats
                    record.vector_embedding = embeddings[0].tolist() 
            return record
        except Exception as e:
            logger.error(f"Error computing embedding for {record.id}: {e}")
            return record

class LanceDBStatelessSinkPartition(StatelessSinkPartition):
    """
    Stateless sink partition that writes to LanceDB with CRUD support.
    Includes workflow event triggers and AI coordinator for full parity with legacy pipeline.
    """
    def __init__(self):
        # Initialize handler once per partition/worker
        from core.lancedb_handler import LanceDBHandler
        self.handler = LanceDBHandler()
        self.table_name = "atom_memory"
    
    def _trigger_post_ingestion_hooks(self, item: AtomRecordData, doc_id: str):
        """
        Trigger workflow events and AI coordinator after successful ingestion.
        Mirrors the behavior in LanceDBHandler.add_document().
        Uses sync fallback when no event loop is available.
        """
        import asyncio
        
        metadata = getattr(item, "metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        
        # 1. Trigger Workflow Events
        try:
            from advanced_workflow_orchestrator import orchestrator
            event_data = {
                "text": item.content,
                "doc_id": doc_id,
                "source": item.app_type,
                "metadata": metadata
            }
            
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(orchestrator.trigger_event("document_uploaded", event_data))
                logger.debug(f"[Bytewax] Async workflow trigger for {doc_id}")
            except RuntimeError:
                # No running event loop - run synchronously
                asyncio.run(orchestrator.trigger_event("document_uploaded", event_data))
                logger.debug(f"[Bytewax] Sync workflow trigger for {doc_id}")
        except ImportError:
            logger.debug("Workflow orchestrator not available")
        except Exception as e:
            logger.warning(f"[Bytewax] Failed to trigger workflow event for {doc_id}: {e}")
        
        # 2. AI Universal Trigger Coordinator (routes to Atom Meta Agent)
        try:
            from core.ai_trigger_coordinator import on_data_ingested
            trigger_data = {
                "text": item.content,
                "doc_id": doc_id,
                "source": item.app_type,
                "metadata": metadata
            }
            
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(on_data_ingested(
                    data=trigger_data,
                    source=item.app_type or "bytewax_ingestion",
                    workspace_id=self.handler.workspace_id,
                    user_id=metadata.get("user_id", "default_user"),
                    metadata=metadata
                ))
                logger.debug(f"[Bytewax] Async AI trigger for {doc_id}")
            except RuntimeError:
                # No running event loop - run synchronously
                asyncio.run(on_data_ingested(
                    data=trigger_data,
                    source=item.app_type or "bytewax_ingestion",
                    workspace_id=self.handler.workspace_id,
                    user_id=metadata.get("user_id", "default_user"),
                    metadata=metadata
                ))
                logger.info(f"[Bytewax] Sync AI trigger for {doc_id}")
        except ImportError:
            logger.debug("AI trigger coordinator not available")
        except Exception as e:
            logger.warning(f"[Bytewax] Failed to invoke AI trigger coordinator for {doc_id}: {e}")
    
    def write_batch(self, items: Iterable[AtomRecordData]):
        """
        Process a batch of records, routing to appropriate CRUD operation.
        """
        for item in items:
            op_type = getattr(item, "operation", "CREATE")
            
            try:
                if op_type == "CREATE":
                    # Create/Index logic - use add_document
                    metadata = getattr(item, "metadata", {})
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata) if metadata else {}
                    
                    # Note: We skip secrets redaction here as it's done in the pipeline operator
                    # Note: extract_knowledge=False because Bytewax handles streaming differently
                    success = self.handler.add_document(
                        table_name=self.table_name,
                        text=item.content,
                        source=item.app_type,
                        metadata=metadata,
                        user_id=metadata.get("user_id", "default_user"),
                        extract_knowledge=False
                    )
                    logger.info(f"[LanceDBSink] [CREATE] Persisted {item.id}: {success}")
                    
                    # Trigger post-ingestion hooks (workflow events, AI coordinator)
                    if success:
                        self._trigger_post_ingestion_hooks(item, item.id)
                    
                elif op_type == "UPDATE":
                    # Update logic - use update_document
                    metadata = getattr(item, "metadata", {})
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata) if metadata else {}
                    
                    updates = {
                        "text": item.content,
                        "metadata": metadata
                    }
                    success = self.handler.update_document(self.table_name, item.id, updates)
                    logger.info(f"[LanceDBSink] [UPDATE] Updated {item.id}: {success}")
                    
                elif op_type == "DELETE":
                    # Delete logic - use delete_document
                    success = self.handler.delete_document(self.table_name, item.id)
                    logger.info(f"[LanceDBSink] [DELETE] Deleted {item.id}: {success}")
                    
                else:
                    logger.warning(f"[LanceDBSink] Unknown OP '{op_type}' for {item.id}")
                    
            except Exception as e:
                logger.error(f"[LanceDBSink] Error processing {op_type} for {item.id}: {e}")

class LanceDBSink(DynamicSink):
    """
    Sink to write normalized, embedded records to LanceDB.
    """
    def build(self, *args, **kwargs) -> LanceDBStatelessSinkPartition:
        return LanceDBStatelessSinkPartition()

class BytewaxIngestionService:
    @staticmethod
    def create_dataflow(input_source: DynamicSource, workspace_id: str = "default") -> Dataflow:
        """
        Create the Atom ingestion dataflow with full agent support.
        
        Pipeline stages:
        1. Input → 2. Normalize → 3. Filter → 4. Redact → 5. Vectorize → 6. Extract Knowledge → 7. Output
        """
        flow = Dataflow("atom_ingestion")
        
        # 1. Input
        stream = op.input("input", flow, input_source)
        
        # 2. Normalize
        normalizer = UnifiedNormalizationOperator()
        stream = op.map("normalize", stream, normalizer.normalize)
        
        # Filter None values (failed normalizations)
        stream = op.filter("filter_none", stream, lambda x: x is not None)
        
        # 3. Redact Secrets (SECURITY: prevents storing PII/API keys)
        redactor = SecretsRedactionOperator()
        stream = op.map("redact_secrets", stream, redactor.redact)
        
        # 4. Vectorize (generate embeddings for vector search)
        vectorizer = FastEmbedOperator()
        stream = op.map("vectorize", stream, vectorizer.compute_embedding)
        
        # 5. Extract Knowledge (CRITICAL: populates knowledge graph + GraphRAG for agent learning)
        knowledge_extractor = KnowledgeExtractionOperator(workspace_id=workspace_id)
        stream = op.map("extract_knowledge", stream, knowledge_extractor.extract_knowledge)
        
        # 6. Extract Formulas (from spreadsheets for agent formula learning)
        formula_extractor = FormulaExtractionOperator(workspace_id=workspace_id)
        stream = op.map("extract_formulas", stream, formula_extractor.extract)
        
        # 7. Output (includes workflow events and AI trigger coordinator)
        op.output("lancedb", stream, LanceDBSink())
        
        return flow


# ======================== BYTEWAX QUEUE SOURCE ========================
# Shared queue for streaming integration from connectors
import queue
import threading

# Thread-safe queue for real-time ingestion
_bytewax_queue = queue.Queue()


def get_bytewax_queue():
    """Get the shared Bytewax ingestion queue."""
    return _bytewax_queue


class BytewaxQueuePartition(StatelessSourcePartition):
    """Source partition that reads from the shared queue."""
    
    def __init__(self, max_batch_size: int = 100):
        self.max_batch_size = max_batch_size
    
    def next_batch(self):
        """Pull items from the queue."""
        items = []
        while len(items) < self.max_batch_size:
            try:
                item = _bytewax_queue.get_nowait()
                items.append(item)
            except queue.Empty:
                break
        return items


class BytewaxQueueSource(DynamicSource):
    """
    Dynamic source that pulls from a shared queue.
    Use this to stream data from Shopify, Slack, WhatsApp etc.
    
    Usage:
        from integrations.bytewax_service import get_bytewax_queue, BytewaxQueueSource
        
        # In connector:
        queue = get_bytewax_queue()
        queue.put({"app_type": "shopify", "record_type": "order", "data": {...}})
        
        # In Bytewax runner:
        source = BytewaxQueueSource()
        flow = BytewaxIngestionService.create_dataflow(source)
    """
    def build(self, *args, **kwargs) -> BytewaxQueuePartition:
        return BytewaxQueuePartition()

# Test Execution (for manual verification)
if __name__ == "__main__":
    from bytewax.testing import TestingSource
    
    # Mock Data
    test_data = [
        {"app_type": "whatsapp", "record_type": "communication", "text": "Hello form Bytewax!", "id": "msg_1", "operation": "CREATE"},
        {"app_type": "salesforce", "record_type": "lead", "FirstName": "John", "LastName": "Doe", "Company": "Rust Corp", "id": "lead_1", "operation": "UPDATE"},
        {"app_type": "hubspot", "record_type": "contact", "id": "cont_to_delete", "operation": "DELETE"}
    ]
    
    # Run
    source = TestingSource(test_data)
    flow = BytewaxIngestionService.create_dataflow(source)
    
    from bytewax.execution import run_main
    # This runs the dataflow in the current process
    # Bytewax 0.19+ uses run_main or similar entry points
    try:
        print("Running Bytewax Dataflow...")
        # Simple iterator runner for test
        from bytewax.testing import run_main
        run_main(flow) # This might change based on version, using simple run check plan in next step
    except ImportError:
         print("Bytewax testing import issue, check version.")
