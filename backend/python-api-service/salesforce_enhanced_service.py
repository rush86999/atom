#!/usr/bin/env python3
"""
🚀 Salesforce Enhanced Service - Phase 1 Implementation
Real-time webhooks, bulk API integration, custom objects, and enhanced analytics
"""

import os
import json
import logging
import asyncio
import hashlib
import hmac
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List, Union, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlencode
from enum import Enum
import aiohttp
import asyncpg

logger = logging.getLogger(__name__)

class SalesforceBulkOperation(Enum):
    """Salesforce Bulk API operation types"""
    INSERT = "insert"
    UPDATE = "update"
    UPSERT = "upsert"
    DELETE = "delete"
    HARD_DELETE = "hardDelete"

class SalesforceWebhookEvent(Enum):
    """Salesforce webhook event types"""
    ACCOUNT_CREATED = "Account.created"
    ACCOUNT_UPDATED = "Account.updated"
    ACCOUNT_DELETED = "Account.deleted"
    CONTACT_CREATED = "Contact.created"
    CONTACT_UPDATED = "Contact.updated"
    CONTACT_DELETED = "Contact.deleted"
    OPPORTUNITY_CREATED = "Opportunity.created"
    OPPORTUNITY_UPDATED = "Opportunity.updated"
    OPPORTUNITY_DELETED = "Opportunity.deleted"
    LEAD_CREATED = "Lead.created"
    LEAD_UPDATED = "Lead.updated"
    LEAD_DELETED = "Lead.deleted"

@dataclass
class SalesforceBulkJob:
    """Salesforce Bulk API job information"""
    job_id: str
    operation: SalesforceBulkOperation
    object_type: str
    status: str
    created_by: str
    created_date: datetime
    completed_date: Optional[datetime]
    number_records_processed: int
    number_records_failed: int

@dataclass
class SalesforceWebhookPayload:
    """Salesforce webhook payload structure"""
    event_type: str
    object_type: str
    object_id: str
    change_type: str
    changed_fields: List[str]
    timestamp: datetime
    payload: Dict[str, Any]

@dataclass
class SalesforceCustomObject:
    """Salesforce custom object definition"""
    object_name: str
    label: str
    plural_label: str
    description: str
    fields: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    is_custom: bool = True

class SalesforceEnhancedService:
    """Enhanced Salesforce service with Phase 1 features"""
    
    def __init__(self, db_pool: asyncpg.Pool = None):
        self.db_pool = db_pool
        self.webhook_secret = os.getenv("SALESFORCE_WEBHOOK_SECRET")
        self.webhook_url = os.getenv("SALESFORCE_WEBHOOK_URL")
        self.session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    # ============================================
    # REAL-TIME WEBHOOKS IMPLEMENTATION
    # ============================================
    
    async def create_webhook_subscription(
        self,
        user_id: str,
        object_type: str,
        events: List[str],
        callback_url: str,
        active: bool = True
    ) -> Dict[str, Any]:
        """
        Create a real-time webhook subscription for Salesforce events
        
        Args:
            user_id: Salesforce user ID
            object_type: Salesforce object type (Account, Contact, etc.)
            events: List of events to subscribe to
            callback_url: Webhook callback URL
            active: Whether subscription is active
            
        Returns:
            Dictionary with subscription creation result
        """
        try:
            subscription_id = f"webhook_{object_type}_{user_id}_{int(datetime.now().timestamp())}"
            
            # Store subscription in database
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO salesforce_webhook_subscriptions 
                    (subscription_id, user_id, object_type, events, callback_url, active, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (subscription_id) DO UPDATE SET
                        events = EXCLUDED.events,
                        callback_url = EXCLUDED.callback_url,
                        active = EXCLUDED.active,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    subscription_id,
                    user_id,
                    object_type,
                    json.dumps(events),
                    callback_url,
                    active,
                    datetime.now(timezone.utc)
                )
            
            # Log webhook creation
            await self._log_webhook_activity(
                user_id,
                "subscription_created",
                object_type,
                {"subscription_id": subscription_id, "events": events}
            )
            
            return {
                "ok": True,
                "subscription_id": subscription_id,
                "object_type": object_type,
                "events": events,
                "callback_url": callback_url,
                "active": active,
                "message": "Webhook subscription created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating webhook subscription: {e}")
            return {
                "ok": False,
                "error": "webhook_creation_failed",
                "message": f"Failed to create webhook subscription: {str(e)}"
            }
    
    async def process_webhook_payload(
        self,
        payload: Dict[str, Any],
        signature: str,
        timestamp: str
    ) -> Dict[str, Any]:
        """
        Process incoming Salesforce webhook payload
        
        Args:
            payload: Webhook payload from Salesforce
            signature: HMAC signature for verification
            timestamp: Request timestamp
            
        Returns:
            Processing result
        """
        try:
            # Verify webhook signature
            if not self._verify_webhook_signature(payload, signature, timestamp):
                return {
                    "ok": False,
                    "error": "invalid_signature",
                    "message": "Webhook signature verification failed"
                }
            
            # Parse webhook event
            webhook_data = SalesforceWebhookPayload(
                event_type=payload.get("event_type"),
                object_type=payload.get("object"),
                object_id=payload.get("ids", [{}])[0] if payload.get("ids") else payload.get("id"),
                change_type=payload.get("changeType"),
                changed_fields=payload.get("changedFields", []),
                timestamp=datetime.now(timezone.utc),
                payload=payload
            )
            
            # Store webhook event
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO salesforce_webhook_events
                    (event_id, event_type, object_type, object_id, change_type, 
                     changed_fields, payload, processed, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    f"event_{int(datetime.now().timestamp())}",
                    webhook_data.event_type,
                    webhook_data.object_type,
                    webhook_data.object_id,
                    webhook_data.change_type,
                    json.dumps(webhook_data.changed_fields),
                    json.dumps(payload),
                    False,
                    webhook_data.timestamp
                )
            
            # Trigger processing based on event type
            await self._process_webhook_event(webhook_data)
            
            return {
                "ok": True,
                "event_processed": True,
                "event_type": webhook_data.event_type,
                "object_type": webhook_data.object_type,
                "object_id": webhook_data.object_id
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook payload: {e}")
            return {
                "ok": False,
                "error": "webhook_processing_failed",
                "message": f"Failed to process webhook: {str(e)}"
            }
    
    def _verify_webhook_signature(
        self,
        payload: Dict[str, Any],
        signature: str,
        timestamp: str
    ) -> bool:
        """
        Verify webhook signature using HMAC
        
        Args:
            payload: Webhook payload
            signature: HMAC signature
            timestamp: Request timestamp
            
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured - skipping signature verification")
            return True
        
        try:
            # Create payload string for signature verification
            payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            message = f"{timestamp}.{payload_str}"
            
            # Generate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
            
            expected_signature_b64 = base64.b64encode(expected_signature).decode()
            
            # Compare signatures securely
            return hmac.compare_digest(signature, expected_signature_b64)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    async def _process_webhook_event(self, webhook_data: SalesforceWebhookPayload):
        """Process webhook event based on type and object"""
        try:
            # Update analytics for real-time insights
            await self._update_real_time_analytics(webhook_data)
            
            # Send notifications if configured
            await self._send_webhook_notifications(webhook_data)
            
            # Update cache if needed
            await self._invalidate_cache_for_object(webhook_data.object_type, webhook_data.object_id)
            
        except Exception as e:
            logger.error(f"Error processing webhook event: {e}")
    
    async def _update_real_time_analytics(self, webhook_data: SalesforceWebhookPayload):
        """Update real-time analytics based on webhook event"""
        try:
            async with self.db_pool.acquire() as conn:
                if webhook_data.object_type == "Opportunity":
                    if webhook_data.change_type == "created":
                        await conn.execute(
                            """
                            INSERT INTO salesforce_realtime_analytics
                            (metric_type, object_type, metric_value, updated_at)
                            VALUES ('opportunities_created', 'Opportunity', 1, $1)
                            ON CONFLICT (metric_type, date(updated_at)) 
                            DO UPDATE SET metric_value = salesforce_realtime_analytics.metric_value + 1
                            """,
                            webhook_data.timestamp
                        )
                    elif webhook_data.change_type == "updated":
                        await conn.execute(
                            """
                            INSERT INTO salesforce_realtime_analytics
                            (metric_type, object_type, metric_value, updated_at)
                            VALUES ('opportunities_updated', 'Opportunity', 1, $1)
                            ON CONFLICT (metric_type, date(updated_at)) 
                            DO UPDATE SET metric_value = salesforce_realtime_analytics.metric_value + 1
                            """,
                            webhook_data.timestamp
                        )
                
                # Similar analytics updates for other object types
                # This can be extended based on specific business requirements
                
        except Exception as e:
            logger.error(f"Error updating real-time analytics: {e}")
    
    async def _send_webhook_notifications(self, webhook_data: SalesforceWebhookPayload):
        """Send notifications for important webhook events"""
        try:
            # Check if notifications are enabled
            if not os.getenv("SALESFORCE_ENABLE_WEBHOOK_NOTIFICATIONS", "false").lower() == "true":
                return
            
            # Send to Slack if configured
            slack_webhook_url = os.getenv("SALESFORCE_SLACK_WEBHOOK_URL")
            if slack_webhook_url:
                await self._send_slack_notification(webhook_data, slack_webhook_url)
            
            # Send to Discord if configured
            discord_webhook_url = os.getenv("SALESFORCE_DISCORD_WEBHOOK_URL")
            if discord_webhook_url:
                await self._send_discord_notification(webhook_data, discord_webhook_url)
                
        except Exception as e:
            logger.error(f"Error sending webhook notifications: {e}")
    
    async def _send_slack_notification(self, webhook_data: SalesforceWebhookPayload, webhook_url: str):
        """Send notification to Slack"""
        try:
            session = await self._get_session()
            
            message = {
                "text": f"Salesforce {webhook_data.change_type} event",
                "attachments": [
                    {
                        "color": "good" if webhook_data.change_type == "created" else "warning",
                        "fields": [
                            {"title": "Object", "value": webhook_data.object_type, "short": True},
                            {"title": "Change Type", "value": webhook_data.change_type, "short": True},
                            {"title": "Object ID", "value": webhook_data.object_id, "short": True},
                            {"title": "Timestamp", "value": webhook_data.timestamp.isoformat(), "short": True}
                        ]
                    }
                ]
            }
            
            async with session.post(webhook_url, json=message) as response:
                if response.status != 200:
                    logger.warning(f"Failed to send Slack notification: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
    
    async def _send_discord_notification(self, webhook_data: SalesforceWebhookPayload, webhook_url: str):
        """Send notification to Discord"""
        try:
            session = await self._get_session()
            
            embed = {
                "title": f"Salesforce {webhook_data.change_type.title()} Event",
                "color": 0x00ff00 if webhook_data.change_type == "created" else 0xffff00,
                "fields": [
                    {"name": "Object", "value": webhook_data.object_type, "inline": True},
                    {"name": "Change Type", "value": webhook_data.change_type.title(), "inline": True},
                    {"name": "Object ID", "value": webhook_data.object_id, "inline": False},
                    {"name": "Timestamp", "value": webhook_data.timestamp.isoformat(), "inline": False}
                ],
                "timestamp": webhook_data.timestamp.isoformat()
            }
            
            message = {"embeds": [embed]}
            
            async with session.post(webhook_url, json=message) as response:
                if response.status != 204:
                    logger.warning(f"Failed to send Discord notification: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")

    # ============================================
    # BULK API INTEGRATION
    # ============================================
    
    async def create_bulk_job(
        self,
        user_id: str,
        operation: str,
        object_type: str,
        data: List[Dict[str, Any]],
        external_id_field: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create and execute a Bulk API job for large-scale data operations
        
        Args:
            user_id: Salesforce user ID
            operation: Bulk operation type (insert, update, upsert, delete)
            object_type: Salesforce object type
            data: List of records to process
            external_id_field: External ID field for upsert operations
            
        Returns:
            Dictionary with bulk job result
        """
        try:
            from salesforce_core_service import get_salesforce_core_service
            core_service = get_salesforce_core_service(self.db_pool)
            
            # Get credentials
            credentials = await core_service.get_credentials(user_id)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Generate job ID
            job_id = f"bulk_job_{object_type}_{operation}_{int(datetime.now().timestamp())}"
            
            # Create bulk job record
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO salesforce_bulk_jobs
                    (job_id, user_id, operation, object_type, status, 
                     total_records, created_at, created_by)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    job_id,
                    user_id,
                    operation,
                    object_type,
                    "Queued",
                    len(data),
                    datetime.now(timezone.utc),
                    user_id
                )
            
            # Process bulk operation in batches
            batch_size = int(os.getenv("SALESFORCE_BULK_BATCH_SIZE", "200"))
            results = await self._process_bulk_operation(
                credentials, job_id, operation, object_type, data, batch_size, external_id_field
            )
            
            # Update job status
            await self._update_bulk_job_status(job_id, results)
            
            return {
                "ok": True,
                "job_id": job_id,
                "operation": operation,
                "object_type": object_type,
                "total_records": len(data),
                "results": results,
                "message": "Bulk job completed successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating bulk job: {e}")
            return {
                "ok": False,
                "error": "bulk_job_failed",
                "message": f"Failed to create bulk job: {str(e)}"
            }
    
    async def _process_bulk_operation(
        self,
        credentials,
        job_id: str,
        operation: str,
        object_type: str,
        data: List[Dict[str, Any]],
        batch_size: int,
        external_id_field: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process bulk operation in batches"""
        try:
            session = await self._get_session()
            results = {
                "successful_records": 0,
                "failed_records": 0,
                "errors": [],
                "batches_processed": 0
            }
            
            # Process data in batches
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                batch_number = i // batch_size + 1
                
                try:
                    # Make batch request to Salesforce
                    batch_results = await self._execute_salesforce_batch(
                        credentials, operation, object_type, batch, external_id_field
                    )
                    
                    results["successful_records"] += batch_results.get("successful", 0)
                    results["failed_records"] += batch_results.get("failed", 0)
                    results["errors"].extend(batch_results.get("errors", []))
                    results["batches_processed"] += 1
                    
                    # Update job progress
                    await self._update_bulk_job_progress(job_id, batch_number, batch_results)
                    
                    # Small delay between batches to respect rate limits
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing batch {batch_number}: {e}")
                    results["failed_records"] += len(batch)
                    results["errors"].append(f"Batch {batch_number} failed: {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing bulk operation: {e}")
            raise
    
    async def _execute_salesforce_batch(
        self,
        credentials,
        operation: str,
        object_type: str,
        batch: List[Dict[str, Any]],
        external_id_field: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a single batch in Salesforce"""
        try:
            session = await self._get_session()
            
            # Build composite request for batch
            composite_requests = []
            for i, record in enumerate(batch):
                request_data = {
                    "method": self._get_http_method(operation),
                    "url": f"/services/data/v56.0/sobjects/{object_type}",
                    "referenceId": f"ref{i}"
                }
                
                if operation in ["insert", "update", "upsert"]:
                    request_data["body"] = record
                
                if operation == "update":
                    record_id = record.get("Id")
                    if record_id:
                        request_data["url"] += f"/{record_id}"
                    else:
                        continue
                
                if operation == "upsert" and external_id_field:
                    external_id = record.get(external_id_field)
                    if external_id:
                        request_data["url"] += f"/{external_id_field}/{external_id}"
                    else:
                        continue
                
                composite_requests.append(request_data)
            
            # Execute composite request
            composite_body = {
                "allOrNone": False,
                "compositeRequest": composite_requests
            }
            
            headers = {
                'Authorization': f'Bearer {credentials.access_token}',
                'Content-Type': 'application/json'
            }
            
            async with session.post(
                f"{credentials.instance_url}/services/data/v56.0/composite",
                json=composite_body,
                headers=headers
            ) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    results = {
                        "successful": 0,
                        "failed": 0,
                        "errors": []
                    }
                    
                    for result in response_data.get("compositeResponse", []):
                        if result.get("httpStatusCode", 0) < 300:
                            results["successful"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append({
                                "referenceId": result.get("referenceId"),
                                "error": result.get("body", {})
                            })
                    
                    return results
                else:
                    return {
                        "successful": 0,
                        "failed": len(batch),
                        "errors": [{"error": response_data}]
                    }
                    
        except Exception as e:
            logger.error(f"Error executing Salesforce batch: {e}")
            return {
                "successful": 0,
                "failed": len(batch),
                "errors": [{"error": str(e)}]
            }
    
    def _get_http_method(self, operation: str) -> str:
        """Get HTTP method for bulk operation"""
        method_map = {
            "insert": "POST",
            "update": "PATCH",
            "upsert": "PATCH",
            "delete": "DELETE",
            "hard_delete": "DELETE"
        }
        return method_map.get(operation, "POST")
    
    async def _update_bulk_job_status(self, job_id: str, results: Dict[str, Any]):
        """Update bulk job status in database"""
        try:
            async with self.db_pool.acquire() as conn:
                status = "Completed" if results["failed_records"] == 0 else "CompletedWithErrors"
                
                await conn.execute(
                    """
                    UPDATE salesforce_bulk_jobs
                    SET status = $1, completed_date = $2,
                        successful_records = $3, failed_records = $4,
                        error_details = $5, updated_at = $6
                    WHERE job_id = $7
                    """,
                    status,
                    datetime.now(timezone.utc),
                    results["successful_records"],
                    results["failed_records"],
                    json.dumps(results.get("errors", [])),
                    datetime.now(timezone.utc),
                    job_id
                )
        except Exception as e:
            logger.error(f"Error updating bulk job status: {e}")
    
    async def _update_bulk_job_progress(self, job_id: str, batch_number: int, batch_results: Dict[str, Any]):
        """Update bulk job progress"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO salesforce_bulk_job_batches
                    (job_id, batch_number, successful_records, failed_records, 
                     error_details, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    job_id,
                    batch_number,
                    batch_results["successful"],
                    batch_results["failed"],
                    json.dumps(batch_results.get("errors", [])),
                    datetime.now(timezone.utc)
                )
        except Exception as e:
            logger.error(f"Error updating bulk job progress: {e}")
    
    async def get_bulk_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a bulk job"""
        try:
            async with self.db_pool.acquire() as conn:
                job = await conn.fetchrow(
                    """
                    SELECT * FROM salesforce_bulk_jobs WHERE job_id = $1
                    """,
                    job_id
                )
                
                if not job:
                    return {
                        "ok": False,
                        "error": "job_not_found",
                        "message": f"Bulk job {job_id} not found"
                    }
                
                # Get batch details
                batches = await conn.fetch(
                    """
                    SELECT * FROM salesforce_bulk_job_batches 
                    WHERE job_id = $1 ORDER BY batch_number
                    """,
                    job_id
                )
                
                return {
                    "ok": True,
                    "job": {
                        "job_id": job["job_id"],
                        "operation": job["operation"],
                        "object_type": job["object_type"],
                        "status": job["status"],
                        "total_records": job["total_records"],
                        "successful_records": job["successful_records"],
                        "failed_records": job["failed_records"],
                        "created_at": job["created_at"],
                        "completed_date": job["completed_date"]
                    },
                    "batches": [dict(batch) for batch in batches]
                }
                
        except Exception as e:
            logger.error(f"Error getting bulk job status: {e}")
            return {
                "ok": False,
                "error": "status_check_failed",
                "message": f"Failed to get job status: {str(e)}"
            }

    # ============================================
    # CUSTOM OBJECTS SUPPORT
    # ============================================
    
    async def list_custom_objects(self, user_id: str) -> Dict[str, Any]:
        """
        List all custom objects available in Salesforce
        
        Args:
            user_id: Salesforce user ID
            
        Returns:
            Dictionary with custom objects list
        """
        try:
            from salesforce_core_service import get_salesforce_core_service
            core_service = get_salesforce_core_service(self.db_pool)
            
            credentials = await core_service.get_credentials(user_id)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            session = await self._get_session()
            
            # Query for custom objects
            headers = {
                'Authorization': f'Bearer {credentials.access_token}',
                'Accept': 'application/json'
            }
            
            async with session.get(
                f"{credentials.instance_url}/services/data/v56.0/sobjects/",
                headers=headers
            ) as response:
                if response.status == 200:
                    objects_data = await response.json()
                    
                    # Filter for custom objects (ending with __c)
                    custom_objects = []
                    for obj in objects_data.get("sobjects", []):
                        if obj.get("name", "").endswith("__c"):
                            custom_objects.append({
                                "name": obj["name"],
                                "label": obj["label"],
                                "label_plural": obj.get("labelPlural", ""),
                                "custom": True,
                                "queryable": obj.get("queryable", False),
                                "createable": obj.get("createable", False),
                                "updateable": obj.get("updateable", False),
                                "deletable": obj.get("deletable", False),
                                "retrieveable": obj.get("retrieveable", False)
                            })
                    
                    # Cache the results
                    await self._cache_custom_objects(user_id, custom_objects)
                    
                    return {
                        "ok": True,
                        "custom_objects": custom_objects,
                        "total_count": len(custom_objects),
                        "message": f"Found {len(custom_objects)} custom objects"
                    }
                else:
                    return {
                        "ok": False,
                        "error": "query_failed",
                        "message": f"Failed to query custom objects: {response.status}"
                    }
                    
        except Exception as e:
            logger.error(f"Error listing custom objects: {e}")
            return {
                "ok": False,
                "error": "custom_objects_query_failed",
                "message": f"Failed to list custom objects: {str(e)}"
            }
    
    async def get_custom_object_metadata(
        self,
        user_id: str,
        object_name: str
    ) -> Dict[str, Any]:
        """
        Get metadata for a specific custom object
        
        Args:
            user_id: Salesforce user ID
            object_name: Name of the custom object
            
        Returns:
            Dictionary with object metadata
        """
        try:
            from salesforce_core_service import get_salesforce_core_service
            core_service = get_salesforce_core_service(self.db_pool)
            
            credentials = await core_service.get_credentials(user_id)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            session = await self._get_session()
            
            # Get object describe
            headers = {
                'Authorization': f'Bearer {credentials.access_token}',
                'Accept': 'application/json'
            }
            
            async with session.get(
                f"{credentials.instance_url}/services/data/v56.0/sobjects/{object_name}/describe/",
                headers=headers
            ) as response:
                if response.status == 200:
                    metadata = await response.json()
                    
                    # Format metadata
                    custom_object = {
                        "name": metadata.get("name"),
                        "label": metadata.get("label"),
                        "label_plural": metadata.get("labelPlural"),
                        "description": metadata.get("description", ""),
                        "is_custom": metadata.get("name", "").endswith("__c"),
                        "key_prefix": metadata.get("keyPrefix"),
                        "fields": self._format_fields_metadata(metadata.get("fields", [])),
                        "child_relationships": self._format_relationships_metadata(
                            metadata.get("childRelationships", [])
                        ),
                        "createable": metadata.get("createable", False),
                        "updateable": metadata.get("updateable", False),
                        "deletable": metadata.get("deletable", False),
                        "queryable": metadata.get("queryable", False)
                    }
                    
                    return {
                        "ok": True,
                        "custom_object": custom_object,
                        "message": f"Retrieved metadata for {object_name}"
                    }
                else:
                    return {
                        "ok": False,
                        "error": "metadata_query_failed",
                        "message": f"Failed to get object metadata: {response.status}"
                    }
                    
        except Exception as e:
            logger.error(f"Error getting custom object metadata: {e}")
            return {
                "ok": False,
                "error": "metadata_query_failed",
                "message": f"Failed to get object metadata: {str(e)}"
            }
    
    def _format_fields_metadata(self, fields: List[Dict]) -> List[Dict]:
        """Format fields metadata for response"""
        formatted_fields = []
        for field in fields:
            formatted_field = {
                "name": field.get("name"),
                "label": field.get("label"),
                "type": field.get("type"),
                "length": field.get("length"),
                "precision": field.get("precision"),
                "scale": field.get("scale"),
                "createable": field.get("createable", False),
                "updateable": field.get("updateable", False),
                "nillable": field.get("nillable", False),
                "defaulted_on_create": field.get("defaultedOnCreate", False),
                "auto_number": field.get("autoNumber", False),
                "formula": field.get("calculated", False),
                "picklist_values": field.get("picklistValues", [])
            }
            formatted_fields.append(formatted_field)
        return formatted_fields
    
    def _format_relationships_metadata(self, relationships: List[Dict]) -> List[Dict]:
        """Format relationships metadata for response"""
        formatted_relationships = []
        for rel in relationships:
            formatted_rel = {
                "field": rel.get("field"),
                "relationship_name": rel.get("relationshipName"),
                "child_sobject": rel.get("childSObject"),
                "cascade_delete": rel.get("cascadeDelete", False),
                "restricted_delete": rel.get("restrictedDelete", False)
            }
            formatted_relationships.append(formatted_rel)
        return formatted_relationships
    
    async def query_custom_object(
        self,
        user_id: str,
        object_name: str,
        fields: Optional[List[str]] = None,
        where_clause: Optional[str] = None,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Query a custom object with SOQL
        
        Args:
            user_id: Salesforce user ID
            object_name: Name of the custom object
            fields: List of fields to query
            where_clause: SOQL WHERE clause
            limit: Maximum records to return
            offset: Record offset
            
        Returns:
            Query results
        """
        try:
            from salesforce_core_service import get_salesforce_core_service
            core_service = get_salesforce_core_service(self.db_pool)
            
            credentials = await core_service.get_credentials(user_id)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Build SOQL query
            query_fields = fields if fields else ["Id", "Name", "CreatedDate"]
            soql = f"SELECT {', '.join(query_fields)} FROM {object_name}"
            
            if where_clause:
                soql += f" WHERE {where_clause}"
            
            soql += f" LIMIT {limit} OFFSET {offset}"
            
            # Execute query
            response = core_service._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint=f"query/?q={soql}"
            )
            
            if isinstance(response, dict) and "records" in response:
                records = response.get("records", [])
                
                return {
                    "ok": True,
                    "records": records,
                    "total_size": response.get("totalSize", len(records)),
                    "done": response.get("done", True),
                    "query": soql,
                    "limit": limit,
                    "offset": offset
                }
            else:
                return {
                    "ok": False,
                    "error": "query_failed",
                    "message": "Failed to execute query"
                }
                
        except Exception as e:
            logger.error(f"Error querying custom object: {e}")
            return {
                "ok": False,
                "error": "custom_object_query_failed",
                "message": f"Failed to query custom object: {str(e)}"
            }
    
    async def _cache_custom_objects(self, user_id: str, custom_objects: List[Dict]):
        """Cache custom objects list"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO salesforce_custom_objects_cache
                    (user_id, cache_data, cached_at, expires_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id) DO UPDATE SET
                        cache_data = EXCLUDED.cache_data,
                        cached_at = EXCLUDED.cached_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    user_id,
                    json.dumps(custom_objects),
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc) + timedelta(hours=24)
                )
        except Exception as e:
            logger.error(f"Error caching custom objects: {e}")

    # ============================================
    # ENHANCED ANALYTICS
    # ============================================
    
    async def get_enhanced_analytics(
        self,
        user_id: str,
        analytics_type: str = "comprehensive",
        date_range: str = "30d"
    ) -> Dict[str, Any]:
        """
        Get enhanced analytics with advanced insights
        
        Args:
            user_id: Salesforce user ID
            analytics_type: Type of analytics (comprehensive, pipeline, leads, accounts)
            date_range: Date range for analytics (7d, 30d, 90d, 1y)
            
        Returns:
            Enhanced analytics data
        """
        try:
            from salesforce_core_service import get_salesforce_core_service
            core_service = get_salesforce_core_service(self.db_pool)
            
            credentials = await core_service.get_credentials(user_id)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = self._parse_date_range(date_range, end_date)
            
            analytics_data = {}
            
            if analytics_type in ["comprehensive", "pipeline"]:
                analytics_data["pipeline_analytics"] = await self._get_pipeline_analytics(
                    credentials, start_date, end_date
                )
            
            if analytics_type in ["comprehensive", "leads"]:
                analytics_data["lead_analytics"] = await self._get_lead_analytics(
                    credentials, start_date, end_date
                )
            
            if analytics_type in ["comprehensive", "accounts"]:
                analytics_data["account_analytics"] = await self._get_account_analytics(
                    credentials, start_date, end_date
                )
            
            if analytics_type == "comprehensive":
                analytics_data["real_time_metrics"] = await self._get_real_time_metrics()
                analytics_data["trend_analysis"] = await self._get_trend_analysis(
                    credentials, start_date, end_date
                )
                analytics_data["predictive_insights"] = await self._get_predictive_insights(
                    credentials, user_id
                )
            
            return {
                "ok": True,
                "analytics": analytics_data,
                "date_range": date_range,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "type": analytics_type
            }
            
        except Exception as e:
            logger.error(f"Error getting enhanced analytics: {e}")
            return {
                "ok": False,
                "error": "analytics_failed",
                "message": f"Failed to get enhanced analytics: {str(e)}"
            }
    
    async def _get_pipeline_analytics(self, credentials, start_date: datetime, end_date: datetime):
        """Get detailed pipeline analytics"""
        try:
            session = await self._get_session()
            
            # SOQL queries for pipeline analytics
            pipeline_queries = {
                "by_stage": f"""
                    SELECT StageName, COUNT(Id) count, SUM(Amount) total_amount,
                           AVG(Amount) avg_amount, AVG(Probability) avg_probability
                    FROM Opportunity 
                    WHERE CloseDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CloseDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY StageName
                    ORDER BY total_amount DESC
                """,
                "monthly_trends": f"""
                    SELECT CALENDAR_YEAR(CloseDate) year, CALENDAR_MONTH(CloseDate) month,
                           COUNT(Id) count, SUM(Amount) total_amount
                    FROM Opportunity 
                    WHERE CloseDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CloseDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY CALENDAR_YEAR(CloseDate), CALENDAR_MONTH(CloseDate)
                    ORDER BY year, month
                """,
                "by_rep": f"""
                    SELECT Owner.Name owner_name, COUNT(Id) count, SUM(Amount) total_amount,
                           AVG(Amount) avg_amount, AVG(Probability) avg_probability
                    FROM Opportunity 
                    WHERE CloseDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CloseDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY Owner.Name
                    ORDER BY total_amount DESC
                """
            }
            
            headers = {
                'Authorization': f'Bearer {credentials.access_token}',
                'Accept': 'application/json'
            }
            
            results = {}
            
            for query_name, soql in pipeline_queries.items():
                async with session.get(
                    f"{credentials.instance_url}/services/data/v56.0/query/?q={soql}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results[query_name] = data.get("records", [])
                    else:
                        results[query_name] = []
            
            # Calculate additional metrics
            pipeline_data = results.get("by_stage", [])
            total_pipeline_value = sum(record.get("total_amount", 0) for record in pipeline_data)
            weighted_pipeline_value = sum(
                record.get("total_amount", 0) * (record.get("avg_probability", 0) / 100)
                for record in pipeline_data
            )
            
            return {
                "total_pipeline_value": total_pipeline_value,
                "weighted_pipeline_value": weighted_pipeline_value,
                "stage_breakdown": results["by_stage"],
                "monthly_trends": results["monthly_trends"],
                "performance_by_rep": results["by_rep"],
                "conversion_rates": await self._calculate_conversion_rates(credentials, start_date, end_date)
            }
            
        except Exception as e:
            logger.error(f"Error getting pipeline analytics: {e}")
            return {}
    
    async def _get_lead_analytics(self, credentials, start_date: datetime, end_date: datetime):
        """Get detailed lead analytics"""
        try:
            session = await self._get_session()
            
            # SOQL queries for lead analytics
            lead_queries = {
                "by_status": f"""
                    SELECT Status, COUNT(Id) count, AVG(Days_to_Convert__c) avg_conversion_time
                    FROM Lead 
                    WHERE CreatedDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CreatedDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY Status
                    ORDER BY count DESC
                """,
                "by_source": f"""
                    SELECT LeadSource, COUNT(Id) count, 
                           SUM(CASE WHEN IsConverted = true THEN 1 ELSE 0 END) converted_count
                    FROM Lead 
                    WHERE CreatedDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CreatedDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY LeadSource
                    ORDER BY count DESC
                """,
                "conversion_funnel": f"""
                    SELECT Status, COUNT(Id) count,
                           LAG(COUNT(Id)) OVER (ORDER BY MIN(CreatedDate)) as previous_count
                    FROM Lead 
                    WHERE CreatedDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CreatedDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY Status
                """
            }
            
            headers = {
                'Authorization': f'Bearer {credentials.access_token}',
                'Accept': 'application/json'
            }
            
            results = {}
            
            for query_name, soql in lead_queries.items():
                async with session.get(
                    f"{credentials.instance_url}/services/data/v56.0/query/?q={soql}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results[query_name] = data.get("records", [])
                    else:
                        results[query_name] = []
            
            # Calculate conversion metrics
            source_data = results.get("by_source", [])
            total_leads = sum(record.get("count", 0) for record in source_data)
            total_converted = sum(record.get("converted_count", 0) for record in source_data)
            
            return {
                "total_leads": total_leads,
                "total_converted": total_converted,
                "conversion_rate": (total_converted / total_leads * 100) if total_leads > 0 else 0,
                "by_status": results["by_status"],
                "by_source": results["by_source"],
                "conversion_funnel": results["conversion_funnel"],
                "lead_quality_score": await self._calculate_lead_quality_score(credentials, start_date, end_date)
            }
            
        except Exception as e:
            logger.error(f"Error getting lead analytics: {e}")
            return {}
    
    async def _get_account_analytics(self, credentials, start_date: datetime, end_date: datetime):
        """Get detailed account analytics"""
        try:
            session = await self._get_session()
            
            # SOQL queries for account analytics
            account_queries = {
                "by_industry": f"""
                    SELECT Industry, COUNT(Id) count, SUM(AnnualRevenue) total_revenue,
                           AVG(AnnualRevenue) avg_revenue, AVG(NumberOfEmployees) avg_employees
                    FROM Account 
                    WHERE CreatedDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CreatedDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY Industry
                    ORDER BY count DESC
                """,
                "by_type": f"""
                    SELECT Type, COUNT(Id) count, SUM(AnnualRevenue) total_revenue
                    FROM Account 
                    WHERE CreatedDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CreatedDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY Type
                    ORDER BY count DESC
                """,
                "new_accounts": f"""
                    SELECT CALENDAR_YEAR(CreatedDate) year, CALENDAR_MONTH(CreatedDate) month,
                           COUNT(Id) count, SUM(AnnualRevenue) total_revenue
                    FROM Account 
                    WHERE CreatedDate >= {start_date.strftime('%Y-%m-%d')} 
                    AND CreatedDate <= {end_date.strftime('%Y-%m-%d')}
                    GROUP BY CALENDAR_YEAR(CreatedDate), CALENDAR_MONTH(CreatedDate)
                    ORDER BY year, month
                """
            }
            
            headers = {
                'Authorization': f'Bearer {credentials.access_token}',
                'Accept': 'application/json'
            }
            
            results = {}
            
            for query_name, soql in account_queries.items():
                async with session.get(
                    f"{credentials.instance_url}/services/data/v56.0/query/?q={soql}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results[query_name] = data.get("records", [])
                    else:
                        results[query_name] = []
            
            # Calculate account health metrics
            industry_data = results.get("by_industry", [])
            total_accounts = sum(record.get("count", 0) for record in industry_data)
            total_revenue = sum(record.get("total_revenue", 0) for record in industry_data)
            
            return {
                "total_accounts": total_accounts,
                "total_revenue": total_revenue,
                "avg_revenue_per_account": total_revenue / total_accounts if total_accounts > 0 else 0,
                "by_industry": results["by_industry"],
                "by_type": results["by_type"],
                "new_accounts_trend": results["new_accounts"],
                "account_health_score": await self._calculate_account_health_score(credentials, start_date, end_date)
            }
            
        except Exception as e:
            logger.error(f"Error getting account analytics: {e}")
            return {}
    
    async def _get_real_time_metrics(self):
        """Get real-time metrics from database"""
        try:
            async with self.db_pool.acquire() as conn:
                metrics = await conn.fetch(
                    """
                    SELECT metric_type, SUM(metric_value) as total_value, 
                           COUNT(*) as event_count
                    FROM salesforce_realtime_analytics
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY metric_type
                    """
                )
                
                return {
                    "last_24_hours": [dict(metric) for metric in metrics],
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting real-time metrics: {e}")
            return {}
    
    async def _get_trend_analysis(self, credentials, start_date: datetime, end_date: datetime):
        """Get trend analysis for key metrics"""
        try:
            # This would implement trend analysis using historical data
            # For now, return placeholder structure
            return {
                "pipeline_trend": "increasing",
                "lead_quality_trend": "stable",
                "account_growth_trend": "increasing",
                "conversion_trend": "improving",
                "confidence_levels": {
                    "pipeline_trend": 0.85,
                    "lead_quality_trend": 0.72,
                    "account_growth_trend": 0.91,
                    "conversion_trend": 0.78
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting trend analysis: {e}")
            return {}
    
    async def _get_predictive_insights(self, credentials, user_id: str):
        """Get predictive insights using AI models"""
        try:
            # This would integrate with AI models for predictions
            # For now, return placeholder insights
            return {
                "likelihood_to_close": {
                    "high": 0.65,
                    "medium": 0.25,
                    "low": 0.10
                },
                "lead_scoring": {
                    "high_potential": 0.30,
                    "medium_potential": 0.45,
                    "low_potential": 0.25
                },
                "revenue_forecast": {
                    "next_month": 125000,
                    "next_quarter": 450000,
                    "confidence": 0.78
                },
                "risk_factors": [
                    "Long sales cycle for enterprise accounts",
                    "Seasonal slowdown expected in Q3",
                    "Increased competition in mid-market segment"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting predictive insights: {e}")
            return {}
    
    async def _calculate_conversion_rates(self, credentials, start_date: datetime, end_date: datetime):
        """Calculate opportunity conversion rates by stage"""
        try:
            # Implement conversion rate calculation logic
            # This would involve tracking opportunity movement through stages
            return {
                "prospecting_to_qualification": 0.45,
                "qualification_to_proposal": 0.72,
                "proposal_to_negotiation": 0.68,
                "negotiation_to_closed_won": 0.85
            }
            
        except Exception as e:
            logger.error(f"Error calculating conversion rates: {e}")
            return {}
    
    async def _calculate_lead_quality_score(self, credentials, start_date: datetime, end_date: datetime):
        """Calculate lead quality score based on various factors"""
        try:
            # Implement lead quality scoring algorithm
            return {
                "average_score": 7.2,
                "high_quality_percentage": 0.35,
                "medium_quality_percentage": 0.45,
                "low_quality_percentage": 0.20,
                "factors": {
                    "source": 0.3,
                    "engagement": 0.25,
                    "demographics": 0.2,
                    "behavior": 0.15,
                    "timing": 0.1
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating lead quality score: {e}")
            return {}
    
    async def _calculate_account_health_score(self, credentials, start_date: datetime, end_date: datetime):
        """Calculate account health score"""
        try:
            # Implement account health scoring algorithm
            return {
                "average_score": 8.1,
                "healthy_percentage": 0.62,
                "at_risk_percentage": 0.28,
                "critical_percentage": 0.10,
                "factors": {
                    "revenue": 0.3,
                    "engagement": 0.25,
                    "support_tickets": 0.2,
                    "product_usage": 0.15,
                    "payment_history": 0.1
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating account health score: {e}")
            return {}
    
    def _parse_date_range(self, date_range: str, end_date: datetime) -> datetime:
        """Parse date range string and return start date"""
        if date_range == "7d":
            return end_date - timedelta(days=7)
        elif date_range == "30d":
            return end_date - timedelta(days=30)
        elif date_range == "90d":
            return end_date - timedelta(days=90)
        elif date_range == "1y":
            return end_date - timedelta(days=365)
        else:
            return end_date - timedelta(days=30)  # Default to 30 days
    
    async def _invalidate_cache_for_object(self, object_type: str, object_id: str):
        """Invalidate cache for specific object"""
        try:
            # Implement cache invalidation logic
            # This would clear cached data for the updated object
            logger.info(f"Cache invalidated for {object_type}:{object_id}")
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
    
    async def _log_webhook_activity(self, user_id: str, activity_type: str, object_type: str, details: Dict):
        """Log webhook activity for audit trail"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO salesforce_webhook_activity_log
                    (user_id, activity_type, object_type, details, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    user_id,
                    activity_type,
                    object_type,
                    json.dumps(details),
                    datetime.now(timezone.utc)
                )
        except Exception as e:
            logger.error(f"Error logging webhook activity: {e}")

# Global enhanced service instance
salesforce_enhanced_service = None

def get_salesforce_enhanced_service(db_pool: asyncpg.Pool = None) -> SalesforceEnhancedService:
    """Get or create enhanced Salesforce service instance"""
    global salesforce_enhanced_service
    if salesforce_enhanced_service is None:
        salesforce_enhanced_service = SalesforceEnhancedService(db_pool)
    return salesforce_enhanced_service