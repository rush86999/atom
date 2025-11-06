#!/usr/bin/env python3
"""
🚀 Enhanced Salesforce API
Enterprise-grade Salesforce integration with advanced business intelligence
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List

from flask import Blueprint, request, jsonify

from salesforce_core_service import get_salesforce_core_service

logger = logging.getLogger(__name__)

# Create Flask blueprint for enhanced Salesforce API
salesforce_enhanced_bp = Blueprint("salesforce_enhanced", __name__)

# Global service instance
salesforce_service = None

def init_salesforce_enhanced_service(db_pool):
    """Initialize enhanced Salesforce service with database pool"""
    global salesforce_service
    salesforce_service = get_salesforce_core_service(db_pool)

# ==============================================================================
# ACCOUNT MANAGEMENT ENDPOINTS
# ==============================================================================

@salesforce_enhanced_bp.route("/accounts/list", methods=["POST"])
def list_salesforce_accounts():
    """List Salesforce accounts with advanced filtering"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        query = data.get("query")
        fields = data.get("fields")
        limit = data.get("limit", 25)
        offset = data.get("offset", 0)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Call service
        result = asyncio.run(salesforce_service.list_accounts(
            user_id=user_id,
            username=username,
            query=query,
            fields=fields,
            limit=limit,
            offset=offset
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in list_salesforce_accounts: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@salesforce_enhanced_bp.route("/accounts/create", methods=["POST"])
def create_salesforce_account():
    """Create new Salesforce account"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        account_data = data.get("account_data")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        if not account_data:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "account_data is required"
            }), 400
        
        # Validate required fields for account
        if not account_data.get("Name"):
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "Account name is required"
            }), 400
        
        # Call service
        result = asyncio.run(salesforce_service.create_account(
            user_id=user_id,
            username=username,
            account_data=account_data
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in create_salesforce_account: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@salesforce_enhanced_bp.route("/accounts/get", methods=["POST"])
def get_salesforce_account():
    """Get specific Salesforce account"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        account_id = data.get("account_id")
        username = data.get("username")
        fields = data.get("fields")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        if not account_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "account_id is required"
            }), 400
        
        # Call service
        result = asyncio.run(salesforce_service.get_account(
            user_id=user_id,
            account_id=account_id,
            username=username,
            fields=fields
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_salesforce_account: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

# ==============================================================================
# CONTACT MANAGEMENT ENDPOINTS
# ==============================================================================

@salesforce_enhanced_bp.route("/contacts/list", methods=["POST"])
def list_salesforce_contacts():
    """List Salesforce contacts with filtering options"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        account_id = data.get("account_id")
        query = data.get("query")
        fields = data.get("fields")
        limit = data.get("limit", 25)
        offset = data.get("offset", 0)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Call service
        result = asyncio.run(salesforce_service.list_contacts(
            user_id=user_id,
            username=username,
            account_id=account_id,
            query=query,
            fields=fields,
            limit=limit,
            offset=offset
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in list_salesforce_contacts: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

# ==============================================================================
# OPPORTUNITY MANAGEMENT ENDPOINTS
# ==============================================================================

@salesforce_enhanced_bp.route("/opportunities/list", methods=["POST"])
def list_salesforce_opportunities():
    """List Salesforce opportunities with sales pipeline filtering"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        account_id = data.get("account_id")
        stage = data.get("stage")
        query = data.get("query")
        fields = data.get("fields")
        limit = data.get("limit", 25)
        offset = data.get("offset", 0)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Call service
        result = asyncio.run(salesforce_service.list_opportunities(
            user_id=user_id,
            username=username,
            account_id=account_id,
            stage=stage,
            query=query,
            fields=fields,
            limit=limit,
            offset=offset
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in list_salesforce_opportunities: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

# ==============================================================================
# LEAD MANAGEMENT ENDPOINTS
# ==============================================================================

@salesforce_enhanced_bp.route("/leads/list", methods=["POST"])
def list_salesforce_leads():
    """List Salesforce leads with lead management filtering"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        status = data.get("status")
        source = data.get("source")
        query = data.get("query")
        fields = data.get("fields")
        limit = data.get("limit", 25)
        offset = data.get("offset", 0)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Call service
        result = asyncio.run(salesforce_service.list_leads(
            user_id=user_id,
            username=username,
            status=status,
            source=source,
            query=query,
            fields=fields,
            limit=limit,
            offset=offset
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in list_salesforce_leads: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

# ==============================================================================
# ADVANCED ANALYTICS ENDPOINTS
# ==============================================================================

@salesforce_enhanced_bp.route("/analytics/pipeline", methods=["POST"])
def get_sales_pipeline_analytics():
    """Get comprehensive sales pipeline analytics"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Get opportunities across all stages
        all_opportunities = []
        stages = [
            "Prospecting", "Qualification", "Needs Analysis", 
            "Value Proposition", "Proposal/Quote", "Negotiation/Review",
            "Closed Won", "Closed Lost"
        ]
        
        for stage in stages:
            result = asyncio.run(salesforce_service.list_opportunities(
                user_id=user_id,
                username=username,
                stage=stage,
                limit=100,  # Higher limit for analytics
                fields=["Id", "Name", "Amount", "StageName", "Probability", "CloseDate", "CreatedDate"]
            ))
            
            if result.get("ok"):
                all_opportunities.extend(result.get("opportunities", []))
        
        # Calculate analytics
        total_pipeline = sum(opp.get("Amount", 0) for opp in all_opportunities)
        weighted_pipeline = sum(
            opp.get("Amount", 0) * (opp.get("Probability", 0) / 100) 
            for opp in all_opportunities
        )
        
        # Group by stage
        stage_analytics = {}
        for stage in stages:
            stage_opps = [opp for opp in all_opportunities if opp.get("StageName") == stage]
            stage_total = sum(opp.get("Amount", 0) for opp in stage_opps)
            stage_count = len(stage_opps)
            
            stage_analytics[stage] = {
                "count": stage_count,
                "total_amount": stage_total,
                "opportunities": stage_opps[:5]  # Show first 5 for preview
            }
        
        # Time-based analytics (current quarter)
        current_quarter_start = datetime.now(timezone.utc).replace(
            day=1, month=(datetime.now(timezone.utc).month - 1) // 3 * 3 + 1
        )
        current_quarter_opps = [
            opp for opp in all_opportunities
            if datetime.fromisoformat(
                opp.get("CloseDate", "").replace("Z", "+00:00")
            ) >= current_quarter_start
        ]
        
        current_quarter_value = sum(opp.get("Amount", 0) for opp in current_quarter_opps)
        
        return jsonify({
            "ok": True,
            "analytics": {
                "total_pipeline_value": total_pipeline,
                "weighted_pipeline_value": weighted_pipeline,
                "current_quarter_value": current_quarter_value,
                "total_opportunities": len(all_opportunities),
                "current_quarter_opportunities": len(current_quarter_opps),
                "stage_breakdown": stage_analytics,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error in get_sales_pipeline_analytics: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@salesforce_enhanced_bp.route("/analytics/leads", methods=["POST"])
def get_leads_analytics():
    """Get comprehensive lead management analytics"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Get leads across all statuses
        all_leads = []
        statuses = [
            "Open - Not Contacted", "Working - Contacted", 
            "Closed - Converted", "Closed - Not Converted"
        ]
        
        for status in statuses:
            result = asyncio.run(salesforce_service.list_leads(
                user_id=user_id,
                username=username,
                status=status,
                limit=100,
                fields=["Id", "FirstName", "LastName", "Email", "Company", "Status", "LeadSource", "Rating", "CreatedDate", "ConvertedDate"]
            ))
            
            if result.get("ok"):
                all_leads.extend(result.get("leads", []))
        
        # Calculate analytics
        converted_leads = sum(1 for lead in all_leads if lead.get("ConvertedDate"))
        total_leads = len(all_leads)
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        # Group by status
        status_analytics = {}
        for status in statuses:
            status_leads = [lead for lead in all_leads if lead.get("Status") == status]
            status_count = len(status_leads)
            
            status_analytics[status] = {
                "count": status_count,
                "percentage": (status_count / total_leads * 100) if total_leads > 0 else 0,
                "leads": status_leads[:5]  # Show first 5 for preview
            }
        
        # Group by lead source
        source_analytics = {}
        for lead in all_leads:
            source = lead.get("LeadSource", "Unknown")
            if source not in source_analytics:
                source_analytics[source] = {"count": 0, "converted": 0}
            source_analytics[source]["count"] += 1
            if lead.get("ConvertedDate"):
                source_analytics[source]["converted"] += 1
        
        # Calculate conversion rates by source
        for source, data in source_analytics.items():
            conversion_rate = (data["converted"] / data["count"] * 100) if data["count"] > 0 else 0
            data["conversion_rate"] = round(conversion_rate, 2)
        
        # Time-based analytics (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_leads = [
            lead for lead in all_leads
            if datetime.fromisoformat(
                lead.get("CreatedDate", "").replace("Z", "+00:00")
            ) >= thirty_days_ago
        ]
        
        recent_converted = sum(1 for lead in recent_leads if lead.get("ConvertedDate"))
        
        return jsonify({
            "ok": True,
            "analytics": {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "overall_conversion_rate": round(conversion_rate, 2),
                "recent_leads_30_days": len(recent_leads),
                "recent_converted_30_days": recent_converted,
                "status_breakdown": status_analytics,
                "source_breakdown": source_analytics,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error in get_leads_analytics: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

# ==============================================================================
# UTILITY ENDPOINTS
# ==============================================================================

@salesforce_enhanced_bp.route("/query", methods=["POST"])
def execute_soql_query():
    """Execute custom SOQL query"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        soql_query = data.get("query")
        limit = data.get("limit", 50)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        if not soql_query:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "SOQL query is required"
            }), 400
        
        # Basic SOQL validation
        soql_upper = soql_query.upper().strip()
        forbidden_keywords = ["DELETE", "DROP", "TRUNCATE", "UPDATE", "INSERT"]
        
        for keyword in forbidden_keywords:
            if keyword in soql_upper:
                return jsonify({
                    "ok": False,
                    "error": "validation_error",
                    "message": f"Forbidden keyword '{keyword}' in SOQL query"
                }), 400
        
        # Call service
        result = asyncio.run(salesforce_service.execute_soql_query(
            user_id=user_id,
            username=username,
            soql_query=soql_query,
            limit=limit
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in execute_soql_query: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@salesforce_enhanced_bp.route("/user/info", methods=["POST"])
def get_salesforce_user_info():
    """Get Salesforce user information"""
    try:
        if not salesforce_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        username = data.get("username")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Call service
        result = asyncio.run(salesforce_service.get_user_info(
            user_id=user_id,
            username=username
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_salesforce_user_info: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

# ==============================================================================
# HEALTH AND STATUS ENDPOINTS
# ==============================================================================

@salesforce_enhanced_bp.route("/health", methods=["GET", "POST"])
def salesforce_enhanced_health():
    """Health check for enhanced Salesforce API"""
    try:
        health_status = {
            "ok": True,
            "service": "salesforce_enhanced",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0"
        }
        
        # Check service initialization
        if not salesforce_service:
            health_status["service_initialized"] = False
            health_status["status"] = "degraded"
            health_status["message"] = "Salesforce service not initialized"
            return jsonify(health_status), 503
        
        health_status["service_initialized"] = True
        
        # Check database connectivity
        if salesforce_service.db_pool:
            health_status["database"] = "connected"
        else:
            health_status["database"] = "disconnected"
            health_status["status"] = "degraded"
            health_status["message"] = "Database not connected"
        
        # Check environment variables
        required_vars = ["SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            health_status["configuration"] = "incomplete"
            health_status["missing_variables"] = missing_vars
            health_status["status"] = "degraded"
            health_status["message"] = f"Missing environment variables: {', '.join(missing_vars)}"
        else:
            health_status["configuration"] = "complete"
        
        # Final status determination
        if health_status["status"] == "degraded":
            return jsonify(health_status), 503
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error in salesforce_enhanced_health: {e}")
        return jsonify({
            "ok": False,
            "service": "salesforce_enhanced",
            "status": "error",
            "message": f"Health check failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@salesforce_enhanced_bp.route("/status", methods=["GET"])
def salesforce_enhanced_status():
    """Get detailed status of enhanced Salesforce service"""
    try:
        status = {
            "ok": True,
            "service": "salesforce_enhanced",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "features": {
                "account_management": True,
                "contact_management": True,
                "opportunity_management": True,
                "lead_management": True,
                "sales_analytics": True,
                "lead_analytics": True,
                "soql_queries": True,
                "user_info": True
            },
            "endpoints": {
                "accounts": {
                    "list": "/accounts/list",
                    "create": "/accounts/create",
                    "get": "/accounts/get"
                },
                "contacts": {
                    "list": "/contacts/list"
                },
                "opportunities": {
                    "list": "/opportunities/list"
                },
                "leads": {
                    "list": "/leads/list"
                },
                "analytics": {
                    "pipeline": "/analytics/pipeline",
                    "leads": "/analytics/leads"
                },
                "utilities": {
                    "query": "/query",
                    "user_info": "/user/info"
                }
            },
            "support": {
                "salesforce_api_version": "56.0",
                "authentication": "OAuth 2.0",
                "database": "PostgreSQL",
                "caching": "Redis (optional)"
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error in salesforce_enhanced_status: {e}")
        return jsonify({
            "ok": False,
            "error": "status_check_failed",
            "message": f"Failed to get status: {str(e)}"
        }), 500