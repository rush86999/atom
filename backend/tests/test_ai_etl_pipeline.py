import unittest
import os
import sys
sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
from core.database import Base
import core.models
import ecommerce.models
import saas.models
import sales.models
import accounting.models
import service_delivery.models
import marketing.models
from core.models import Workspace, BusinessProductService
from ecommerce.models import EcommerceOrder
from core.data_ingestion_service import DataIngestionService

class TestAIETLPipeline(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w1", name="Data Corp")
        self.db.add(self.ws)
        self.db.commit()
        
        self.ingestion_service = DataIngestionService(self.db)

    def tearDown(self):
        self.db.close()

    def test_csv_upload_semantic_mapping(self):
        # CSV with "messy" headers
        # "Order_Reference" -> "external_id"
        # "Amount" -> "total_price"
        # "Buyer" -> "customer_id"
        csv_content = """Order_Reference,Sale_Value,Currency_Type,Status_Msg,Buyer
ord_101,150.50,USD,paid,c1
ord_102,299.99,USD,pending,c1
"""
        # Create a customer first
        from ecommerce.models import EcommerceCustomer
        self.db.add(EcommerceCustomer(id="c1", workspace_id="w1", email="test@buyer.com"))
        self.db.commit()

        result = self.ingestion_service.handle_csv_upload(csv_content, "w1", EcommerceOrder)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["ingested_count"], 2)
        
        # Verify records in DB
        orders = self.db.query(EcommerceOrder).filter(EcommerceOrder.workspace_id == "w1").all()
        self.assertEqual(len(orders), 2)

    def test_product_ingestion_with_dedup(self):
        # "Title" -> "name"
        # "Price" -> "base_price"
        # "COGS" -> "unit_cost"
        # "Stock" -> "stock_quantity"
        csv_content = """Title,Price,COGS,Stock
Widget A,49.99,20.00,50
Widget B,99.99,40.00,100
"""
        # First ingest
        self.ingestion_service.handle_csv_upload(csv_content, "w1", BusinessProductService)
        
        # Second ingest with same data (should be duplicates if we had external_id, but here we don't have it in header)
        # For simplicity, let's add external_id to logic
        csv_with_id = """platform_id,name,Price
wid_1,Widget C,10.00
wid_1,Widget C,10.00
"""
        result = self.ingestion_service.handle_csv_upload(csv_with_id, "w1", BusinessProductService)
        
        self.assertEqual(result["ingested_count"], 1)
        self.assertEqual(result["skipped_count"], 1)

if __name__ == "__main__":
    unittest.main()
