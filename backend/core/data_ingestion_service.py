import csv
import io
import logging
from typing import Any, Dict, List, Type
from ai.etl_mapper import AI_ETL_Mapper
from sqlalchemy.orm import Session

from core.database import Base

logger = logging.getLogger(__name__)

class DataIngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.ai_mapper = AI_ETL_Mapper()

    def handle_csv_upload(self, csv_content: str, workspace_id: str, target_model: Type[Base]) -> Dict[str, Any]:
        """
        Main entry point for manual CSV uploads.
        Parses CSV, maps columns with AI, and stores records.
        """
        raw_data = self.parse_csv(csv_content)
        if not raw_data:
            return {"status": "error", "message": "Empty or invalid CSV"}

        headers = list(raw_data[0].keys())
        target_model_name = target_model.__name__
        
        # 1. Use AI to map headers
        mapping = self.ai_mapper.map_headers_with_ai(headers, target_model_name)
        
        # 2. Transform and commit
        success_count = 0
        skipped_count = 0
        
        for row in raw_data:
            transformed_row = self._apply_mapping(row, mapping)
            transformed_row["workspace_id"] = workspace_id
            
            try:
                # Basic dedup logic (can be expanded)
                if self._is_duplicate(transformed_row, target_model):
                    skipped_count += 1
                    continue
                
                record = target_model(**transformed_row)
                self.db.add(record)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to ingest row {row}: {e}")
                skipped_count += 1

        self.db.commit()
        
        return {
            "status": "success",
            "ingested_count": success_count,
            "skipped_count": skipped_count,
            "mapping_used": mapping
        }

    def parse_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """Parses CSV string into a list of dictionaries."""
        f = io.StringIO(csv_content.strip())
        reader = csv.DictReader(f)
        return list(reader)

    def _apply_mapping(self, row: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        """Transforms a raw row into the target schema using the AI mapping."""
        transformed = {}
        for raw_key, target_key in mapping.items():
            if raw_key in row:
                transformed[target_key] = row[raw_key]
        return transformed

    def _is_duplicate(self, row: Dict[str, Any], target_model: Type[Base]) -> bool:
        """
        Checks for duplicates based on common unique fields (external_id, email, etc).
        """
        filters = []
        if "external_id" in row and row["external_id"]:
            filters.append(target_model.external_id == row["external_id"])
        elif "email" in row and row["email"]:
             # Check if email is an attribute of the model
             if hasattr(target_model, "email"):
                filters.append(target_model.email == row["email"])
        
        if not filters:
            return False
            
        from sqlalchemy import or_
        existing = self.db.query(target_model).filter(or_(*filters)).first()
        return existing is not None
