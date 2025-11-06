"""
Shopify Bulk API Integration
Large-scale data operations and bulk processing for Shopify
"""

import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

class BulkOperationStatus(Enum):
    """Bulk operation status"""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    TIMEOUT = "TIMEOUT"

@dataclass
class BulkOperation:
    """Bulk operation model"""
    id: str
    query: str
    status: BulkOperationStatus
    created_at: datetime
    completed_at: Optional[datetime]
    url: Optional[str]
    object_count: int = 0
    file_size: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
@dataclass
class BulkQuery:
    """Bulk GraphQL query model"""
    query: str
    variables: Dict[str, Any] = field(default_factory=dict)
    operation_name: Optional[str] = None
    
@dataclass
class BulkOperationResult:
    """Bulk operation result model"""
    success: bool
    operation_id: str
    data: Optional[List[Dict[str, Any]]] = None
    errors: List[str] = field(default_factory=list)
    file_url: Optional[str] = None
    total_count: int = 0
    processing_time: float = 0.0

class ShopifyBulkAPI:
    """Shopify Bulk API operations"""
    
    def __init__(self, shopify_service):
        self.shopify_service = shopify_service
        self.max_query_complexity = 1000
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.operation_timeout = 600  # 10 minutes
        self.active_operations: Dict[str, BulkOperation] = {}
    
    async def create_bulk_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None
    ) -> BulkOperationResult:
        """Create and execute bulk query"""
        try:
            # Prepare GraphQL mutation for bulk operation
            bulk_mutation = self._build_bulk_query_mutation(query, variables, operation_name)
            
            # Execute mutation
            response = await self._execute_graphql_query(bulk_mutation)
            
            if not response.get("success"):
                return BulkOperationResult(
                    success=False,
                    operation_id="",
                    errors=[response.get("error", "Unknown error")]
                )
            
            # Extract bulk operation data
            bulk_operation_data = response.get("data", {}).get("bulkOperationRunQuery", {})
            
            if bulk_operation_data.get("userErrors"):
                return BulkOperationResult(
                    success=False,
                    operation_id="",
                    errors=[error.get("message") for error in bulk_operation_data["userErrors"]]
                )
            
            operation = bulk_operation_data.get("bulkOperation", {})
            bulk_op = BulkOperation(
                id=operation.get("id"),
                query=query,
                status=BulkOperationStatus(operation.get("status", "CREATED")),
                created_at=datetime.fromisoformat(operation["createdAt"].replace("Z", "+00:00")),
                completed_at=None,
                url=operation.get("url"),
                object_count=operation.get("objectCount", 0),
                error_code=operation.get("errorCode"),
                error_message=operation.get("errorMessage")
            )
            
            # Store in active operations
            self.active_operations[bulk_op.id] = bulk_op
            
            logger.info(f"Created bulk operation: {bulk_op.id} - Status: {bulk_op.status.value}")
            
            return BulkOperationResult(
                success=True,
                operation_id=bulk_op.id,
                file_url=bulk_op.url
            )
            
        except Exception as e:
            logger.error(f"Error creating bulk query: {e}")
            return BulkOperationResult(
                success=False,
                operation_id="",
                errors=[str(e)]
            )
    
    def _build_bulk_query_mutation(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build GraphQL mutation for bulk operation"""
        
        # Escape query string
        escaped_query = query.replace('"', '\\"')
        
        mutation = f"""
        mutation {{
          bulkOperationRunQuery(
            query: "{escaped_query}"
          ) {{
            bulkOperation {{
              id
              status
              errorCode
              errorMessage
              createdAt
              completedAt
              objectCount
              fileSize
              url
            }}
            userErrors {{
              field
              message
            }}
          }}
        }}
        """
        
        return {
            "query": mutation,
            "variables": variables or {}
        }
    
    async def _execute_graphql_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute GraphQL query"""
        try:
            # Use Shopify service's GraphQL client
            if hasattr(self.shopify_service, '_make_graphql_request'):
                return await self.shopify_service._make_graphql_request(query_data)
            else:
                # Fallback to regular REST client
                response = await self.shopify_service._make_request(
                    "POST",
                    "graphql.json",
                    query_data
                )
                return {"success": True, "data": response}
        
        except Exception as e:
            logger.error(f"GraphQL query execution error: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_operation_status(self, operation_id: str) -> BulkOperation:
        """Check status of bulk operation"""
        try:
            query = """
            query getBulkOperation($id: ID!) {
              node(id: $id) {
                ... on BulkOperation {
                  id
                  status
                  errorCode
                  errorMessage
                  createdAt
                  completedAt
                  objectCount
                  fileSize
                  url
                }
              }
            }
            """
            
            response = await self._execute_graphql_query({
                "query": query,
                "variables": {"id": operation_id}
            })
            
            if not response.get("success"):
                logger.error(f"Failed to check operation status: {response.get('error')}")
                return self.active_operations.get(operation_id)
            
            node_data = response.get("data", {}).get("node", {})
            
            if node_data:
                operation = BulkOperation(
                    id=node_data["id"],
                    query=self.active_operations.get(operation_id, BulkOperation("", "", BulkOperationStatus.CREATED, datetime.now(timezone.utc), None, None)).query,
                    status=BulkOperationStatus(node_data["status"]),
                    created_at=datetime.fromisoformat(node_data["createdAt"].replace("Z", "+00:00")),
                    completed_at=datetime.fromisoformat(node_data["completedAt"].replace("Z", "+00:00")) if node_data["completedAt"] else None,
                    url=node_data.get("url"),
                    object_count=node_data.get("objectCount", 0),
                    file_size=node_data.get("fileSize", 0),
                    error_code=node_data.get("errorCode"),
                    error_message=node_data.get("errorMessage")
                )
                
                # Update active operations
                self.active_operations[operation_id] = operation
                
                logger.info(f"Operation {operation_id} status: {operation.status.value}")
                return operation
            
            return self.active_operations.get(operation_id)
            
        except Exception as e:
            logger.error(f"Error checking operation status: {e}")
            return self.active_operations.get(operation_id)
    
    async def wait_for_operation_completion(
        self,
        operation_id: str,
        check_interval: int = 5,
        max_wait_time: int = 600
    ) -> BulkOperationResult:
        """Wait for bulk operation to complete"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            operation = await self.check_operation_status(operation_id)
            
            if not operation:
                return BulkOperationResult(
                    success=False,
                    operation_id=operation_id,
                    errors=["Operation not found"]
                )
            
            # Check if operation is completed
            if operation.status in [BulkOperationStatus.COMPLETED, BulkOperationStatus.FAILED, BulkOperationStatus.CANCELED, BulkOperationStatus.TIMEOUT]:
                
                if operation.status == BulkOperationStatus.COMPLETED:
                    # Download and parse results
                    return await self._download_and_parse_results(operation)
                else:
                    # Operation failed
                    return BulkOperationResult(
                        success=False,
                        operation_id=operation_id,
                        errors=[f"Operation {operation.status.value}: {operation.error_message or 'Unknown error'}"],
                        total_count=operation.object_count
                    )
            
            # Check timeout
            elapsed_time = asyncio.get_event_loop().time() - start_time
            if elapsed_time > max_wait_time:
                return BulkOperationResult(
                    success=False,
                    operation_id=operation_id,
                    errors=["Operation timed out"],
                    total_count=operation.object_count
                )
            
            # Wait before next check
            await asyncio.sleep(check_interval)
    
    async def _download_and_parse_results(self, operation: BulkOperation) -> BulkOperationResult:
        """Download and parse bulk operation results"""
        try:
            if not operation.url:
                return BulkOperationResult(
                    success=False,
                    operation_id=operation.id,
                    errors=["No results URL available"]
                )
            
            # Download results
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(operation.url) as response:
                    if response.status != 200:
                        return BulkOperationResult(
                            success=False,
                            operation_id=operation.id,
                            errors=[f"Failed to download results: HTTP {response.status}"]
                        )
                    
                    # Read JSONL content
                    content = await response.text()
                    
                    # Parse each line as JSON
                    results = []
                    errors = []
                    
                    for line in content.splitlines():
                        if not line.strip():
                            continue
                        
                        try:
                            data = json.loads(line)
                            results.append(data)
                        except json.JSONDecodeError as e:
                            errors.append(f"JSON parse error: {e}")
                    
                    return BulkOperationResult(
                        success=True,
                        operation_id=operation.id,
                        data=results,
                        errors=errors,
                        file_url=operation.url,
                        total_count=len(results)
                    )
        
        except Exception as e:
            logger.error(f"Error downloading results: {e}")
            return BulkOperationResult(
                success=False,
                operation_id=operation.id,
                errors=[str(e)],
                total_count=operation.object_count
            )
    
    # Predefined bulk operations
    async def bulk_get_products(
        self,
        product_ids: Optional[List[str]] = None,
        collection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> BulkOperationResult:
        """Bulk get products"""
        query = self._build_products_query(product_ids, collection_id, status, limit)
        return await self.create_bulk_query(query)
    
    async def bulk_get_orders(
        self,
        order_ids: Optional[List[str]] = None,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        financial_status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> BulkOperationResult:
        """Bulk get orders"""
        query = self._build_orders_query(order_ids, created_at_min, created_at_max, financial_status, limit)
        return await self.create_bulk_query(query)
    
    async def bulk_get_customers(
        self,
        customer_ids: Optional[List[str]] = None,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        limit: Optional[int] = None
    ) -> BulkOperationResult:
        """Bulk get customers"""
        query = self._build_customers_query(customer_ids, created_at_min, created_at_max, limit)
        return await self.create_bulk_query(query)
    
    async def bulk_get_inventory_levels(
        self,
        location_ids: Optional[List[str]] = None,
        inventory_item_ids: Optional[List[str]] = None
    ) -> BulkOperationResult:
        """Bulk get inventory levels"""
        query = self._build_inventory_query(location_ids, inventory_item_ids)
        return await self.create_bulk_query(query)
    
    async def bulk_create_products(self, products: List[Dict[str, Any]]) -> BulkOperationResult:
        """Bulk create products"""
        mutations = []
        
        for i, product in enumerate(products):
            mutation = f'''
            product{i}: productCreate(input: {json.dumps(product).replace('"', '\\"')}) {{
              product {{
                id
                title
                handle
                status
              }}
              userErrors {{
                field
                message
              }}
            }}
            '''
            mutations.append(mutation)
        
        query = f"mutation {{ {chr(10).join(mutations)} }}"
        return await self.create_bulk_query(query)
    
    async def bulk_update_products(self, products: List[Dict[str, Any]]) -> BulkOperationResult:
        """Bulk update products"""
        mutations = []
        
        for i, product in enumerate(products):
            mutation = f'''
            product{i}: productUpdate(input: {json.dumps(product).replace('"', '\\"')}) {{
              product {{
                id
                title
                handle
                status
              }}
              userErrors {{
                field
                message
              }}
            }}
            '''
            mutations.append(mutation)
        
        query = f"mutation {{ {chr(10).join(mutations)} }}"
        return await self.create_bulk_query(query)
    
    def _build_products_query(
        self,
        product_ids: Optional[List[str]] = None,
        collection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        """Build products query"""
        filters = []
        
        if product_ids:
            filters.append(f'id:in: {json.dumps(product_ids)}')
        if collection_id:
            filters.append(f'collections: {collection_id}')
        if status:
            filters.append(f'status: {status.upper()}')
        
        filter_clause = f'({", ".join(filters)})' if filters else ''
        limit_clause = f'first: {limit}' if limit else 'first: 250'
        
        return f'''
        query {{
          products({filter_clause}) {{
            edges {{
              node {{
                id
                title
                handle
                status
                vendor
                productType
                createdAt
                updatedAt
                tags
                variants {{
                  edges {{
                    node {{
                      id
                      title
                      sku
                      price
                      inventoryQuantity
                      selectedOptions {{
                        name
                        value
                      }}
                    }}
                  }}
                }}
                images {{
                  edges {{
                    node {{
                      id
                      url
                      altText
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        '''
    
    def _build_orders_query(
        self,
        order_ids: Optional[List[str]] = None,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        financial_status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        """Build orders query"""
        filters = []
        
        if order_ids:
            filters.append(f'id:in: {json.dumps(order_ids)}')
        if created_at_min:
            filters.append(f'createdAt >= "{created_at_min}"')
        if created_at_max:
            filters.append(f'createdAt <= "{created_at_max}"')
        if financial_status:
            filters.append(f'financialStatus: {financial_status.upper()}')
        
        filter_clause = f'({", ".join(filters)})' if filters else ''
        limit_clause = f'first: {limit}' if limit else 'first: 250'
        
        return f'''
        query {{
          orders({filter_clause}) {{
            edges {{
              node {{
                id
                name
                email
                phone
                financialStatus
                fulfillmentStatus
                createdAt
                updatedAt
                totalPrice
                currency
                tags
                lineItems {{
                  edges {{
                    node {{
                      id
                      title
                      quantity
                      price
                      variant {{
                        id
                        title
                        sku
                      }}
                    }}
                  }}
                }}
                shippingAddress {{
                  firstName
                  lastName
                  address1
                  city
                  province
                  country
                  zip
                }}
              }}
            }}
          }}
        }}
        '''
    
    def _build_customers_query(
        self,
        customer_ids: Optional[List[str]] = None,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        """Build customers query"""
        filters = []
        
        if customer_ids:
            filters.append(f'id:in: {json.dumps(customer_ids)}')
        if created_at_min:
            filters.append(f'createdAt >= "{created_at_min}"')
        if created_at_max:
            filters.append(f'createdAt <= "{created_at_max}"')
        
        filter_clause = f'({", ".join(filters)})' if filters else ''
        limit_clause = f'first: {limit}' if limit else 'first: 250'
        
        return f'''
        query {{
          customers({filter_clause}) {{
            edges {{
              node {{
                id
                email
                firstName
                lastName
                phone
                state
                createdAt
                updatedAt
                ordersCount
                totalSpent
                currency
                tags
                addresses {{
                  firstName
                  lastName
                  address1
                  city
                  province
                  country
                  zip
                }}
              }}
            }}
          }}
        }}
        '''
    
    def _build_inventory_query(
        self,
        location_ids: Optional[List[str]] = None,
        inventory_item_ids: Optional[List[str]] = None
    ) -> str:
        """Build inventory levels query"""
        filters = []
        
        if location_ids:
            filters.append(f'locationIds: {json.dumps(location_ids)}')
        if inventory_item_ids:
            filters.append(f'inventoryItemIds: {json.dumps(inventory_item_ids)}')
        
        filter_clause = f'({", ".join(filters)})' if filters else ''
        
        return f'''
        query {{
          inventoryLevels({filter_clause}) {{
            edges {{
              node {{
                id
                location {{
                  id
                  name
                }}
                item {{
                  id
                  variant {{
                    id
                    title
                    sku
                  }}
                  product {{
                    id
                    title
                  }}
                }}
                available
                updatedAt
                costs {{
                  amount
                  currencyCode
                }}
              }}
            }}
          }}
        }}
        '''
    
    async def get_active_operations(self) -> List[BulkOperation]:
        """Get list of active bulk operations"""
        return list(self.active_operations.values())
    
    async def cancel_operation(self, operation_id: str) -> BulkOperationResult:
        """Cancel bulk operation"""
        try:
            query = """
            mutation bulkOperationCancel($id: ID!) {
              bulkOperationCancel(id: $id) {
                bulkOperation {
                  id
                  status
                  errorMessage
                }
                userErrors {
                  message
                }
              }
            }
            """
            
            response = await self._execute_graphql_query({
                "query": query,
                "variables": {"id": operation_id}
            })
            
            if not response.get("success"):
                return BulkOperationResult(
                    success=False,
                    operation_id=operation_id,
                    errors=[response.get("error", "Unknown error")]
                )
            
            bulk_op_data = response.get("data", {}).get("bulkOperationCancel", {})
            
            if bulk_op_data.get("userErrors"):
                return BulkOperationResult(
                    success=False,
                    operation_id=operation_id,
                    errors=[error.get("message") for error in bulk_op_data["userErrors"]]
                )
            
            # Update operation status
            operation = self.active_operations.get(operation_id)
            if operation:
                operation.status = BulkOperationStatus.CANCELED
            
            return BulkOperationResult(
                success=True,
                operation_id=operation_id
            )
            
        except Exception as e:
            logger.error(f"Error canceling operation: {e}")
            return BulkOperationResult(
                success=False,
                operation_id=operation_id,
                errors=[str(e)]
            )

# Export components
__all__ = [
    "ShopifyBulkAPI",
    "BulkOperation",
    "BulkQuery",
    "BulkOperationResult",
    "BulkOperationStatus"
]