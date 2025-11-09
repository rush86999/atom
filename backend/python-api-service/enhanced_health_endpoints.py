#!/usr/bin/env python3
"""
Enhanced API Endpoints for Integration Health
Provides comprehensive health monitoring endpoints for all integrations
"""

from flask import Blueprint, jsonify, request
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from enhanced_health_monitor import health_monitor

# Create blueprint for health endpoints
health_bp = Blueprint('enhanced_health', __name__)
logger = logging.getLogger(__name__)

def async_route(f):
    """Decorator to run async functions in Flask routes"""
    import asyncio
    from functools import wraps
    
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    
    return wrapper

@health_bp.route('/health/all', methods=['GET'])
@async_route
async def get_all_integrations_health():
    """Get health status of all integrations"""
    try:
        user_id = request.args.get('user_id')
        
        # Get comprehensive health report
        health_reports = await health_monitor.check_all_integrations_health(user_id)
        
        # Calculate overall system health
        total_integrations = len(health_reports)
        healthy_integrations = sum(1 for report in health_reports.values() if report.overall_status == "healthy")
        degraded_integrations = sum(1 for report in health_reports.values() if report.overall_status == "degraded")
        unhealthy_integrations = sum(1 for report in health_reports.values() if report.overall_status == "unhealthy")
        
        overall_system_status = "healthy" if healthy_integrations == total_integrations else \
                                "degraded" if healthy_integrations + degraded_integrations > 0 else "unhealthy"
        
        # Prepare response
        response = {
            "system_health": {
                "status": overall_system_status,
                "total_integrations": total_integrations,
                "healthy_integrations": healthy_integrations,
                "degraded_integrations": degraded_integrations,
                "unhealthy_integrations": unhealthy_integrations
            },
            "integrations": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "2.0.0"
        }
        
        # Add individual integration reports
        for integration_name, report in health_reports.items():
            response["integrations"][integration_name] = {
                "name": report.integration_name,
                "status": report.overall_status,
                "connected_count": report.connected_count,
                "total_services": report.total_services,
                "services": [
                    {
                        "name": service.name,
                        "status": service.status,
                        "connected": service.connected,
                        "response_time": service.response_time,
                        "last_check": service.last_check,
                        "error": service.error,
                        "metadata": service.metadata
                    }
                    for service in report.services
                ],
                "timestamp": report.timestamp,
                "backend_connected": report.backend_connected
            }
        
        status_code = 200 if overall_system_status in ["healthy", "degraded"] else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Failed to get all integrations health: {e}")
        return jsonify({
            "error": "Failed to retrieve health information",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@health_bp.route('/health/hubspot', methods=['GET'])
@async_route
async def get_hubspot_health():
    """Get HubSpot integration health"""
    try:
        user_id = request.args.get('user_id')
        report = await health_monitor.check_hubspot_health(user_id)
        
        response = {
            "integration": report.integration_name,
            "status": report.overall_status,
            "connected_count": report.connected_count,
            "total_services": report.total_services,
            "services": [
                {
                    "name": service.name,
                    "status": service.status,
                    "connected": service.connected,
                    "response_time": service.response_time,
                    "last_check": service.last_check,
                    "error": service.error,
                    "metadata": service.metadata
                }
                for service in report.services
            ],
            "timestamp": report.timestamp,
            "version": "2.0.0"
        }
        
        status_code = 200 if report.overall_status in ["healthy", "degraded"] else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot health: {e}")
        return jsonify({
            "error": "Failed to retrieve HubSpot health information",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@health_bp.route('/health/slack', methods=['GET'])
@async_route
async def get_slack_health():
    """Get Slack integration health"""
    try:
        user_id = request.args.get('user_id')
        report = await health_monitor.check_slack_health(user_id)
        
        response = {
            "integration": report.integration_name,
            "status": report.overall_status,
            "connected_count": report.connected_count,
            "total_services": report.total_services,
            "services": [
                {
                    "name": service.name,
                    "status": service.status,
                    "connected": service.connected,
                    "response_time": service.response_time,
                    "last_check": service.last_check,
                    "error": service.error,
                    "metadata": service.metadata
                }
                for service in report.services
            ],
            "timestamp": report.timestamp,
            "version": "2.0.0"
        }
        
        status_code = 200 if report.overall_status in ["healthy", "degraded"] else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Failed to get Slack health: {e}")
        return jsonify({
            "error": "Failed to retrieve Slack health information",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@health_bp.route('/health/jira', methods=['GET'])
@async_route
async def get_jira_health():
    """Get Jira integration health"""
    try:
        user_id = request.args.get('user_id')
        report = await health_monitor.check_jira_health(user_id)
        
        response = {
            "integration": report.integration_name,
            "status": report.overall_status,
            "connected_count": report.connected_count,
            "total_services": report.total_services,
            "services": [
                {
                    "name": service.name,
                    "status": service.status,
                    "connected": service.connected,
                    "response_time": service.response_time,
                    "last_check": service.last_check,
                    "error": service.error,
                    "metadata": service.metadata
                }
                for service in report.services
            ],
            "timestamp": report.timestamp,
            "version": "2.0.0"
        }
        
        status_code = 200 if report.overall_status in ["healthy", "degraded"] else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Failed to get Jira health: {e}")
        return jsonify({
            "error": "Failed to retrieve Jira health information",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@health_bp.route('/health/linear', methods=['GET'])
@async_route
async def get_linear_health():
    """Get Linear integration health"""
    try:
        user_id = request.args.get('user_id')
        report = await health_monitor.check_linear_health(user_id)
        
        response = {
            "integration": report.integration_name,
            "status": report.overall_status,
            "connected_count": report.connected_count,
            "total_services": report.total_services,
            "services": [
                {
                    "name": service.name,
                    "status": service.status,
                    "connected": service.connected,
                    "response_time": service.response_time,
                    "last_check": service.last_check,
                    "error": service.error,
                    "metadata": service.metadata
                }
                for service in report.services
            ],
            "timestamp": report.timestamp,
            "version": "2.0.0"
        }
        
        status_code = 200 if report.overall_status in ["healthy", "degraded"] else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Failed to get Linear health: {e}")
        return jsonify({
            "error": "Failed to retrieve Linear health information",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@health_bp.route('/health/salesforce', methods=['GET'])
@async_route
async def get_salesforce_health():
    """Get Salesforce integration health"""
    try:
        user_id = request.args.get('user_id')
        report = await health_monitor.check_salesforce_health(user_id)
        
        response = {
            "integration": report.integration_name,
            "status": report.overall_status,
            "connected_count": report.connected_count,
            "total_services": report.total_services,
            "services": [
                {
                    "name": service.name,
                    "status": service.status,
                    "connected": service.connected,
                    "response_time": service.response_time,
                    "last_check": service.last_check,
                    "error": service.error,
                    "metadata": service.metadata
                }
                for service in report.services
            ],
            "timestamp": report.timestamp,
            "version": "2.0.0"
        }
        
        status_code = 200 if report.overall_status in ["healthy", "degraded"] else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Failed to get Salesforce health: {e}")
        return jsonify({
            "error": "Failed to retrieve Salesforce health information",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@health_bp.route('/health/xero', methods=['GET'])
@async_route
async def get_xero_health():
    """Get Xero integration health"""
    try:
        user_id = request.args.get('user_id')
        report = await health_monitor.check_xero_health(user_id)
        
        response = {
            "integration": report.integration_name,
            "status": report.overall_status,
            "connected_count": report.connected_count,
            "total_services": report.total_services,
            "services": [
                {
                    "name": service.name,
                    "status": service.status,
                    "connected": service.connected,
                    "response_time": service.response_time,
                    "last_check": service.last_check,
                    "error": service.error,
                    "metadata": service.metadata
                }
                for service in report.services
            ],
            "timestamp": report.timestamp,
            "version": "2.0.0"
        }
        
        status_code = 200 if report.overall_status in ["healthy", "degraded"] else 503
        return jsonify(response), status_code
        
    except Exception as e:
        logger.error(f"Failed to get Xero health: {e}")
        return jsonify({
            "error": "Failed to retrieve Xero health information",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@health_bp.route('/health/summary', methods=['GET'])
@async_route
async def get_health_summary():
    """Get a summary of all integration health"""
    try:
        user_id = request.args.get('user_id')
        
        # Get all health reports
        health_reports = await health_monitor.check_all_integrations_health(user_id)
        
        # Create summary
        summary = {
            "summary": {
                "total_integrations": len(health_reports),
                "healthy_count": sum(1 for report in health_reports.values() if report.overall_status == "healthy"),
                "degraded_count": sum(1 for report in health_reports.values() if report.overall_status == "degraded"),
                "unhealthy_count": sum(1 for report in health_reports.values() if report.overall_status == "unhealthy"),
                "overall_status": "healthy" if all(report.overall_status == "healthy" for report in health_reports.values()) else \
                                 "degraded" if any(report.overall_status in ["healthy", "degraded"] for report in health_reports.values()) else "unhealthy"
            },
            "integrations": {}
        }
        
        for integration_name, report in health_reports.items():
            summary["integrations"][integration_name] = {
                "status": report.overall_status,
                "connected_services": report.connected_count,
                "total_services": report.total_services
            }
        
        summary["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        return jsonify(summary), 200
        
    except Exception as e:
        logger.error(f"Failed to get health summary: {e}")
        return jsonify({
            "error": "Failed to retrieve health summary",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500