#!/usr/bin/env python3
"""
🚀 Salesforce Enhanced API Handler - Phase 1 Implementation
RESTful endpoints for webhooks, bulk API, custom objects, and enhanced analytics
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify
import json

logger = logging.getLogger(__name__)

# Create Blueprint for enhanced Salesforce endpoints
salesforce_enhanced_bp = Blueprint("salesforce_enhanced", __name__)

# Global service instance (will be initialized with database pool)
salesforce_enhanced_service = None

def init_salesforce_enhanced_handler(db_pool):
    """Initialize enhanced Salesforce service with database pool"""
    global salesforce_enhanced_service
    from salesforce_enhanced_service import get_salesforce_enhanced_service
    salesforce_enhanced_service = get_salesforce_enhanced_service(db_pool)

# ============================================
# WEBHOOK ENDPOINTS
# ============================================

@salesforce_enhanced_bp.route("/api/salesforce/webhooks/subscribe", methods=["POST"])
async def create_webhook_subscription():
    """Create a new webhook subscription for Salesforce events"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ["user_id", "object_type", "events", "callback_url"]
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "ok": False,
                    "error": "missing_required_field",
                    "message": f"Missing required field: {field}"
                }), 400
        
        user_id = data["user_id"]
        object_type = data["object_type"]
        events = data["events"]
        callback_url = data["callback_url"]
        active = data.get("active", True)
        
        # Validate events list
        valid_events = [
            "Account.created", "Account.updated", "Account.deleted",
            "Contact.created", "Contact.updated", "Contact.deleted",
            "Opportunity.created", "Opportunity.updated", "Opportunity.deleted",
            "Lead.created", "Lead.updated", "Lead.deleted"
        ]
        
        for event in events:
            if event not in valid_events:
                return jsonify({
                    "ok": False,
                    "error": "invalid_event",
                    "message": f"Invalid event: {event}. Valid events: {valid_events}"
                }), 400
        
        # Create webhook subscription
        result = await salesforce_enhanced_service.create_webhook_subscription(
            user_id=user_id,
            object_type=object_type,
            events=events,
            callback_url=callback_url,
            active=active
        )
        
        if result.get("ok"):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error creating webhook subscription: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

@salesforce_enhanced_bp.route("/api/salesforce/webhooks/<subscription_id>", methods=["DELETE"])
async def delete_webhook_subscription(subscription_id: str):
    """Delete a webhook subscription"""
    try:
        # For now, we'll implement basic deletion
        # In a production system, you'd want to de-activate first
        async with salesforce_enhanced_service.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE salesforce_webhook_subscriptions 
                SET active = false, updated_at = CURRENT_TIMESTAMP
                WHERE subscription_id = $1
                """,
                subscription_id
            )
        
        return jsonify({
            "ok": True,
            "message": "Webhook subscription deactivated successfully",
            "subscription_id": subscription_id
        })
        
    except Exception as e:
        logger.error(f"Error deleting webhook subscription: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

@salesforce_enhanced_bp.route("/webhooks/salesforce", methods=["POST"])
async def handle_salesforce_webhook():
    """Handle incoming webhook from Salesforce"""
    try:
        # Get webhook data
        payload = request.get_json()
        
        # Get headers for signature verification
        signature = request.headers.get("X-Salesforce-Signature", "")
        timestamp = request.headers.get("X-Salesforce-Timestamp", "")
        
        # Process webhook payload
        result = await salesforce_enhanced_service.process_webhook_payload(
            payload=payload,
            signature=signature,
            timestamp=timestamp
        )
        
        if result.get("ok"):
            return jsonify({
                "ok": True,
                "message": "Webhook processed successfully"
            }), 200
        else:
            # Log error but return 200 to avoid webhook retries
            logger.warning(f"Webhook processing failed: {result.get('message')}")
            return jsonify({
                "ok": False,
                "message": "Webhook processing failed"
            }), 200
            
    except Exception as e:
        logger.error(f"Error handling Salesforce webhook: {e}")
        return jsonify({
            "ok": False,
            "message": "Webhook processing failed"
        }), 200

@salesforce_enhanced_bp.route("/api/salesforce/webhooks/subscriptions", methods=["GET"])
async def list_webhook_subscriptions():
    """List webhook subscriptions for a user"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "missing_user_id",
                "message": "user_id parameter is required"
            }), 400
        
        async with salesforce_enhanced_service.db_pool.acquire() as conn:
            subscriptions = await conn.fetch(
                """
                SELECT subscription_id, object_type, events, callback_url, active,
                       created_at, updated_at
                FROM salesforce_webhook_subscriptions
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                user_id
            )
        
        return jsonify({
            "ok": True,
            "subscriptions": [dict(sub) for sub in subscriptions],
            "count": len(subscriptions)
        })
        
    except Exception as e:
        logger.error(f"Error listing webhook subscriptions: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

# ============================================
# BULK API ENDPOINTS
# ============================================

@salesforce_enhanced_bp.route("/api/salesforce/bulk/create-job", methods=["POST"])
async def create_bulk_job():
    """Create and execute a bulk API job"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ["user_id", "operation", "object_type", "data"]
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "ok": False,
                    "error": "missing_required_field",
                    "message": f"Missing required field: {field}"
                }), 400
        
        user_id = data["user_id"]
        operation = data["operation"]
        object_type = data["object_type"]
        records = data["data"]
        external_id_field = data.get("external_id_field")
        
        # Validate operation
        valid_operations = ["insert", "update", "upsert", "delete", "hard_delete"]
        if operation not in valid_operations:
            return jsonify({
                "ok": False,
                "error": "invalid_operation",
                "message": f"Invalid operation: {operation}. Valid operations: {valid_operations}"
            }), 400
        
        # Validate data
        if not isinstance(records, list) or len(records) == 0:
            return jsonify({
                "ok": False,
                "error": "invalid_data",
                "message": "Data must be a non-empty list of records"
            }), 400
        
        # Check data limits
        max_records = 10000  # Configurable limit
        if len(records) > max_records:
            return jsonify({
                "ok": False,
                "error": "data_too_large",
                "message": f"Maximum {max_records} records allowed per job"
            }), 400
        
        # Create bulk job
        result = await salesforce_enhanced_service.create_bulk_job(
            user_id=user_id,
            operation=operation,
            object_type=object_type,
            data=records,
            external_id_field=external_id_field
        )
        
        if result.get("ok"):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error creating bulk job: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

@salesforce_enhanced_bp.route("/api/salesforce/bulk/jobs/<job_id>", methods=["GET"])
async def get_bulk_job_status(job_id: str):
    """Get status and details of a bulk job"""
    try:
        result = await salesforce_enhanced_service.get_bulk_job_status(job_id)
        
        if result.get("ok"):
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"Error getting bulk job status: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

@salesforce_enhanced_bp.route("/api/salesforce/bulk/jobs", methods=["GET"])
async def list_bulk_jobs():
    """List bulk jobs for a user"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "missing_user_id",
                "message": "user_id parameter is required"
            }), 400
        
        status_filter = request.args.get("status")
        limit = int(request.args.get("limit", 25))
        offset = int(request.args.get("offset", 0))
        
        # Build query with filters
        query = """
            SELECT job_id, operation, object_type, status, total_records,
                   successful_records, failed_records, created_at, completed_at
            FROM salesforce_bulk_jobs
            WHERE user_id = $1
        """
        params = [user_id]
        
        if status_filter:
            query += " AND status = $2"
            params.append(status_filter)
        
        query += " ORDER BY created_at DESC LIMIT $%s OFFSET $%s"
        params.extend([limit, offset])
        
        async with salesforce_enhanced_service.db_pool.acquire() as conn:
            jobs = await conn.fetch(query, *params)
            
            # Get total count
            count_query = "SELECT COUNT(*) FROM salesforce_bulk_jobs WHERE user_id = $1"
            if status_filter:
                count_query += " AND status = $2"
            
            total_count = await conn.fetchval(count_query, *params[:2 if status_filter else 1])
        
        return jsonify({
            "ok": True,
            "jobs": [dict(job) for job in jobs],
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        logger.error(f"Error listing bulk jobs: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

# ============================================
# CUSTOM OBJECTS ENDPOINTS
# ============================================

@salesforce_enhanced_bp.route("/api/salesforce/custom-objects", methods=["GET"])
async def list_custom_objects():
    """List all custom objects available in Salesforce"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "missing_user_id",
                "message": "user_id parameter is required"
            }), 400
        
        # Check cache first
        use_cache = request.args.get("cache", "true").lower() == "true"
        if use_cache:
            async with salesforce_enhanced_service.db_pool.acquire() as conn:
                cache_data = await conn.fetchrow(
                    """
                    SELECT cache_data, expires_at 
                    FROM salesforce_custom_objects_cache 
                    WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP
                    """,
                    user_id
                )
                
                if cache_data:
                    return jsonify({
                        "ok": True,
                        "custom_objects": cache_data["cache_data"],
                        "cached": True,
                        "expires_at": cache_data["expires_at"].isoformat()
                    })
        
        # Get fresh data from Salesforce
        result = await salesforce_enhanced_service.list_custom_objects(user_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error listing custom objects: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

@salesforce_enhanced_bp.route("/api/salesforce/custom-objects/<object_name>/metadata", methods=["GET"])
async def get_custom_object_metadata(object_name: str):
    """Get metadata for a specific custom object"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "missing_user_id",
                "message": "user_id parameter is required"
            }), 400
        
        result = await salesforce_enhanced_service.get_custom_object_metadata(user_id, object_name)
        
        if result.get("ok"):
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"Error getting custom object metadata: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

@salesforce_enhanced_bp.route("/api/salesforce/custom-objects/<object_name>/query", methods=["POST"])
async def query_custom_object(object_name: str):
    """Query a custom object with SOQL"""
    try:
        data = request.get_json()
        
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "missing_user_id",
                "message": "user_id is required"
            }), 400
        
        fields = data.get("fields")
        where_clause = data.get("where_clause")
        limit = data.get("limit", 25)
        offset = data.get("offset", 0)
        
        # Validate parameters
        if limit > 2000:  # Maximum records per query
            return jsonify({
                "ok": False,
                "error": "limit_too_large",
                "message": "Maximum limit is 2000 records"
            }), 400
        
        result = await salesforce_enhanced_service.query_custom_object(
            user_id=user_id,
            object_name=object_name,
            fields=fields,
            where_clause=where_clause,
            limit=limit,
            offset=offset
        )
        
        if result.get("ok"):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error querying custom object: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

# ============================================
# ENHANCED ANALYTICS ENDPOINTS
# ============================================

@salesforce_enhanced_bp.route("/api/salesforce/analytics/enhanced", methods=["GET"])
async def get_enhanced_analytics():
    """Get enhanced analytics with advanced insights"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "missing_user_id",
                "message": "user_id parameter is required"
            }), 400
        
        analytics_type = request.args.get("type", "comprehensive")
        date_range = request.args.get("date_range", "30d")
        
        # Validate parameters
        valid_types = ["comprehensive", "pipeline", "leads", "accounts"]
        valid_ranges = ["7d", "30d", "90d", "1y"]
        
        if analytics_type not in valid_types:
            return jsonify({
                "ok": False,
                "error": "invalid_type",
                "message": f"Invalid type. Valid types: {valid_types}"
            }), 400
        
        if date_range not in valid_ranges:
            return jsonify({
                "ok": False,
                "error": "invalid_date_range",
                "message": f"Invalid date_range. Valid ranges: {valid_ranges}"
            }), 400
        
        # Check cache first
        use_cache = request.args.get("cache", "true").lower() == "true"
        if use_cache:
            async with salesforce_enhanced_service.db_pool.acquire() as conn:
                cache_data = await conn.fetchrow(
                    """
                    SELECT cache_data, generated_at 
                    FROM salesforce_analytics_cache 
                    WHERE user_id = $1 AND analytics_type = $2 
                    AND date_range = $3 AND expires_at > CURRENT_TIMESTAMP
                    """,
                    user_id, analytics_type, date_range
                )
                
                if cache_data:
                    return jsonify({
                        "ok": True,
                        "analytics": cache_data["cache_data"],
                        "cached": True,
                        "generated_at": cache_data["generated_at"].isoformat(),
                        "type": analytics_type,
                        "date_range": date_range
                    })
        
        # Generate fresh analytics
        result = await salesforce_enhanced_service.get_enhanced_analytics(
            user_id=user_id,
            analytics_type=analytics_type,
            date_range=date_range
        )
        
        # Cache the result for future requests
        if result.get("ok"):
            try:
                async with salesforce_enhanced_service.db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO salesforce_analytics_cache
                        (user_id, analytics_type, date_range, cache_data, 
                         generated_at, expires_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (user_id, analytics_type, date_range) 
                        DO UPDATE SET
                            cache_data = EXCLUDED.cache_data,
                            generated_at = EXCLUDED.generated_at,
                            expires_at = EXCLUDED.expires_at
                        """,
                        user_id,
                        analytics_type,
                        date_range,
                        result["analytics"],
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc) + timedelta(hours=1)  # Cache for 1 hour
                    )
            except Exception as e:
                logger.warning(f"Failed to cache analytics result: {e}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting enhanced analytics: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

@salesforce_enhanced_bp.route("/api/salesforce/analytics/realtime", methods=["GET"])
async def get_realtime_metrics():
    """Get real-time metrics and activity"""
    try:
        user_id = request.args.get("user_id")
        
        # Get real-time metrics
        async with salesforce_enhanced_service.db_pool.acquire() as conn:
            # Get last 24 hours of metrics
            metrics = await conn.fetch(
                """
                SELECT metric_type, SUM(metric_value) as total_value,
                       COUNT(*) as event_count
                FROM salesforce_realtime_analytics
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                GROUP BY metric_type
                ORDER BY total_value DESC
                """
            )
            
            # Get recent webhook events
            webhook_events = await conn.fetch(
                """
                SELECT event_type, object_type, change_type, created_at
                FROM salesforce_webhook_events
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                ORDER BY created_at DESC
                LIMIT 50
                """
            )
            
            # Get recent bulk jobs
            bulk_jobs = await conn.fetch(
                """
                SELECT job_id, operation, object_type, status, 
                       total_records, successful_records, created_at
                FROM salesforce_bulk_jobs
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                ORDER BY created_at DESC
                LIMIT 20
                """
            )
            
            # Get integration metrics for today
            integration_metrics = await conn.fetchrow(
                """
                SELECT api_calls, webhooks_received, bulk_jobs_created,
                       records_processed, errors_count, avg_response_time
                FROM salesforce_integration_metrics
                WHERE metric_date = CURRENT_DATE AND 
                (user_id = $1 OR user_id IS NULL)
                """,
                user_id
            )
        
        return jsonify({
            "ok": True,
            "realtime_metrics": {
                "last_24_hours": [dict(metric) for metric in metrics],
                "webhook_events": [dict(event) for event in webhook_events],
                "bulk_jobs": [dict(job) for job in bulk_jobs],
                "daily_integration_metrics": dict(integration_metrics) if integration_metrics else {}
            },
            "generated_at": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting real-time metrics: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

# ============================================
# ADMINISTRATION ENDPOINTS
# ============================================

@salesforce_enhanced_bp.route("/api/salesforce/admin/health", methods=["GET"])
def enhanced_health_check():
    """Health check for enhanced Salesforce features"""
    try:
        if not salesforce_enhanced_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "provider": "salesforce_enhanced"
            }), 503
        
        # Check database connectivity
        db_status = "disconnected"
        if salesforce_enhanced_service.db_pool:
            # Test database connection
            try:
                asyncio.get_event_loop().run_until_complete(
                    salesforce_enhanced_service.db_pool.fetch("SELECT 1")
                )
                db_status = "connected"
            except:
                db_status = "error"
        
        # Check configuration
        config_status = "valid"
        if not salesforce_enhanced_service.webhook_secret:
            config_status = "missing_webhook_secret"
        
        return jsonify({
            "ok": True,
            "provider": "salesforce_enhanced",
            "version": "1.0",
            "phase": "phase1",
            "features": {
                "webhooks": True,
                "bulk_api": True,
                "custom_objects": True,
                "enhanced_analytics": True
            },
            "database": db_status,
            "configuration": config_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": "health_check_failed",
            "message": str(e),
            "provider": "salesforce_enhanced"
        }), 500

@salesforce_enhanced_bp.route("/api/salesforce/admin/metrics", methods=["GET"])
async def get_integration_metrics():
    """Get integration performance metrics (admin only)"""
    try:
        # This endpoint should be protected by authentication/authorization
        date_from = request.args.get("date_from", (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"))
        date_to = request.args.get("date_to", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        
        async with salesforce_enhanced_service.db_pool.acquire() as conn:
            # Get daily metrics
            daily_metrics = await conn.fetch(
                """
                SELECT metric_date, SUM(api_calls) as total_api_calls,
                       SUM(webhooks_received) as total_webhooks,
                       SUM(bulk_jobs_created) as total_bulk_jobs,
                       SUM(records_processed) as total_records,
                       SUM(errors_count) as total_errors,
                       AVG(avg_response_time) as avg_response_time
                FROM salesforce_integration_metrics
                WHERE metric_date >= $1 AND metric_date <= $2
                GROUP BY metric_date
                ORDER BY metric_date DESC
                """,
                date_from, date_to
            )
            
            # Get top users by activity
            top_users = await conn.fetch(
                """
                SELECT user_id, SUM(api_calls) as total_api_calls,
                       SUM(webhooks_received) as total_webhooks,
                       SUM(bulk_jobs_created) as total_bulk_jobs
                FROM salesforce_integration_metrics
                WHERE metric_date >= $1 AND metric_date <= $2
                AND user_id IS NOT NULL
                GROUP BY user_id
                ORDER BY total_api_calls DESC
                LIMIT 10
                """,
                date_from, date_to
            )
            
            # Get error breakdown
            error_breakdown = await conn.fetch(
                """
                SELECT metric_date, SUM(errors_count) as daily_errors
                FROM salesforce_integration_metrics
                WHERE metric_date >= $1 AND metric_date <= $2
                GROUP BY metric_date
                ORDER BY metric_date DESC
                """,
                date_from, date_to
            )
        
        return jsonify({
            "ok": True,
            "period": {
                "from": date_from,
                "to": date_to
            },
            "daily_metrics": [dict(metric) for metric in daily_metrics],
            "top_users": [dict(user) for user in top_users],
            "error_breakdown": [dict(error) for error in error_breakdown],
            "generated_at": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting integration metrics: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error"
        }), 500

@salesforce_enhanced_bp.route("/api/salesforce/admin/cleanup", methods=["POST"])
async def cleanup_expired_data():
    """Clean up expired cache and old data (admin only)"""
    try:
        # This endpoint should be protected by authentication/authorization
        
        # Run cleanup function
        async with salesforce_enhanced_service.db_pool.acquire() as conn:
            cleanup_count = await conn.fetchval("SELECT cleanup_expired_cache()")
        
        return jsonify({
            "ok": True,
            "message": "Cleanup completed successfully",
            "records_cleaned": cleanup_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return jsonify({
            "ok": False,
            "error": "cleanup_failed",
            "message": f"Cleanup failed: {str(e)}"
        }), 500

# ============================================
# ERROR HANDLERS
# ============================================

@salesforce_enhanced_bp.errorhandler(400)
def bad_request(error):
    return jsonify({
        "ok": False,
        "error": "bad_request",
        "message": "Bad request"
    }), 400

@salesforce_enhanced_bp.errorhandler(401)
def unauthorized(error):
    return jsonify({
        "ok": False,
        "error": "unauthorized",
        "message": "Unauthorized"
    }), 401

@salesforce_enhanced_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        "ok": False,
        "error": "not_found",
        "message": "Resource not found"
    }), 404

@salesforce_enhanced_bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "ok": False,
        "error": "internal_error",
        "message": "Internal server error"
    }), 500

# ============================================
# MIDDLEWARE FOR REQUEST LOGGING
# ============================================

@salesforce_enhanced_bp.before_request
def log_request_info():
    """Log request information for monitoring"""
    logger.info(f"Salesforce Enhanced API Request: {request.method} {request.path} - IP: {request.remote_addr}")

@salesforce_enhanced_bp.after_request
def log_response_info(response):
    """Log response information for monitoring"""
    logger.info(f"Salesforce Enhanced API Response: {response.status_code} - Size: {len(response.get_data())}")
    return response