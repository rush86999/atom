"""
Web App Storage API Endpoints - S3 Only for LanceDB Memory
Cloud-native storage configuration for web deployment
"""

import os
import json
import asyncio
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

# Import web app storage service
from webapp_storage_service import (
    create_web_app_storage_manager,
    S3LanceDBConfig
)

logger = logging.getLogger(__name__)

# Create blueprint
webapp_storage_bp = Blueprint('webapp_storage_bp', __name__)

# Global storage manager instance
_storage_manager = None

def get_storage_manager():
    """Get or create global storage manager"""
    global _storage_manager
    
    if _storage_manager is None:
        # Get configuration from environment
        s3_bucket = os.getenv('ATOM_S3_BUCKET')
        s3_region = os.getenv('ATOM_S3_REGION', 'us-west-2')
        lancedb_prefix = os.getenv('ATOM_LANCEDB_PREFIX', 'lancedb/')
        
        # AWS credentials (optional, can use IAM roles)
        access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        session_token = os.getenv('AWS_SESSION_TOKEN')
        
        # Maintenance settings
        auto_compact = os.getenv('ATOM_AUTO_COMPACT', 'true').lower() == 'true'
        compact_interval_hours = int(os.getenv('ATOM_COMPACT_INTERVAL_HOURS', '24'))
        
        if not s3_bucket:
            raise ValueError("ATOM_S3_BUCKET environment variable is required")
        
        # Create storage manager
        _storage_manager = create_web_app_storage_manager(
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            lancedb_prefix=lancedb_prefix,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            auto_compact=auto_compact,
            compact_interval_hours=compact_interval_hours
        )
        
        # Start maintenance service
        asyncio.create_task(_storage_manager.start_maintenance_service())
    
    return _storage_manager


# -------------------------------------------------------------------------
# Storage Configuration Endpoints
# -------------------------------------------------------------------------

@webapp_storage_bp.route("/api/webapp/storage/config", methods=["GET"])
def get_storage_config():
    """Get web app storage configuration"""
    try:
        storage_manager = get_storage_manager()
        s3_config = storage_manager.s3_lancedb_manager.config
        
        config = {
            "s3_storage": {
                "bucket_name": s3_config.bucket_name,
                "region": s3_config.region,
                "lancedb_prefix": s3_config.lancedb_prefix,
                "storage_class": s3_config.storage_class,
                "cache_size_mb": s3_config.cache_size_mb
            },
            "maintenance": {
                "auto_compact_enabled": s3_config.auto_compact,
                "compact_interval_hours": s3_config.compact_interval_hours
            },
            "storage_type": "s3_lancedb_cloud",
            "deployment_type": "web"
        }
        
        return jsonify({
            "status": "success",
            "data": config
        })
        
    except Exception as e:
        logger.error(f"Error getting web app storage config: {e}")
        return jsonify({
            "error": f"Failed to get storage config: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Memory Table Management Endpoints
# -------------------------------------------------------------------------

@webapp_storage_bp.route("/api/webapp/memory/tables", methods=["GET"])
def list_memory_tables():
    """List all memory tables"""
    try:
        storage_manager = get_storage_manager()
        tables = storage_manager.list_memory_tables()
        
        return jsonify({
            "status": "success",
            "data": {
                "tables": tables,
                "table_count": len(tables)
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing memory tables: {e}")
        return jsonify({
            "error": f"Failed to list memory tables: {str(e)}",
            "success": False
        }), 500


@webapp_storage_bp.route("/api/webapp/memory/tables/<table_name>", methods=["GET"])
def get_memory_table_info(table_name):
    """Get memory table information"""
    try:
        storage_manager = get_storage_manager()
        table = asyncio.run(storage_manager.get_memory_table(table_name))
        
        if not table:
            return jsonify({
                "error": "Memory table not found",
                "success": False
            }), 404
        
        # Get table statistics
        table_stats = {
            "name": table_name,
            "schema": str(table.schema) if hasattr(table, 'schema') else None,
            "row_count": table.to_pandas().shape[0] if table else 0
        }
        
        return jsonify({
            "status": "success",
            "data": table_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting memory table info: {e}")
        return jsonify({
            "error": f"Failed to get memory table info: {str(e)}",
            "success": False
        }), 500


@webapp_storage_bp.route("/api/webapp/memory/tables", methods=["POST"])
def create_memory_table():
    """Create new memory table"""
    try:
        data = request.get_json()
        table_name = data.get('table_name')
        schema_data = data.get('schema')
        initial_data = data.get('initial_data')
        
        if not table_name:
            return jsonify({
                "error": "table_name is required",
                "success": False
            }), 400
        
        storage_manager = get_storage_manager()
        
        # Create table (schema and data would need proper Arrow implementation)
        success = asyncio.run(storage_manager.create_memory_table(
            table_name=table_name,
            schema=None,  # Would need Arrow schema conversion
            data=None    # Would need Arrow table conversion
        ))
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Memory table {table_name} created successfully",
                "data": {"table_name": table_name}
            })
        else:
            return jsonify({
                "error": "Failed to create memory table",
                "success": False
            }), 500
        
    except Exception as e:
        logger.error(f"Error creating memory table: {e}")
        return jsonify({
            "error": f"Failed to create memory table: {str(e)}",
            "success": False
        }), 500


@webapp_storage_bp.route("/api/webapp/memory/tables/<table_name>", methods=["DELETE"])
def delete_memory_table(table_name):
    """Delete memory table"""
    try:
        storage_manager = get_storage_manager()
        success = asyncio.run(storage_manager.delete_memory_table(table_name))
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Memory table {table_name} deleted successfully",
                "data": {"table_name": table_name}
            })
        else:
            return jsonify({
                "error": "Failed to delete memory table",
                "success": False
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting memory table: {e}")
        return jsonify({
            "error": f"Failed to delete memory table: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Memory Data Management Endpoints
# -------------------------------------------------------------------------

@webapp_storage_bp.route("/api/webapp/memory/tables/<table_name>/data", methods=["POST"])
def store_memory_data(table_name):
    """Store data in memory table"""
    try:
        data = request.get_json()
        memory_data = data.get('data', [])
        
        if not memory_data:
            return jsonify({
                "error": "data is required",
                "success": False
            }), 400
        
        storage_manager = get_storage_manager()
        success = asyncio.run(storage_manager.store_memory_data(
            table_name=table_name,
            data=memory_data
        ))
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Data stored in table {table_name} successfully",
                "data": {
                    "table_name": table_name,
                    "records_stored": len(memory_data) if isinstance(memory_data, list) else 1
                }
            })
        else:
            return jsonify({
                "error": "Failed to store memory data",
                "success": False
            }), 500
        
    except Exception as e:
        logger.error(f"Error storing memory data: {e}")
        return jsonify({
            "error": f"Failed to store memory data: {str(e)}",
            "success": False
        }), 500


@webapp_storage_bp.route("/api/webapp/memory/tables/<table_name>/search", methods=["POST"])
def search_memory(table_name):
    """Search memory table"""
    try:
        data = request.get_json()
        query_vector = data.get('query_vector')
        limit = min(data.get('limit', 10), 100)
        filter_expression = data.get('filter_expression')
        
        storage_manager = get_storage_manager()
        results = asyncio.run(storage_manager.search_memory(
            table_name=table_name,
            query_vector=query_vector,
            limit=limit,
            filter_expression=filter_expression
        ))
        
        return jsonify({
            "status": "success",
            "data": {
                "table_name": table_name,
                "results": results,
                "result_count": len(results),
                "search_params": {
                    "query_vector_provided": query_vector is not None,
                    "limit": limit,
                    "filter_expression": filter_expression
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching memory: {e}")
        return jsonify({
            "error": f"Failed to search memory: {str(e)}",
            "success": False
        }), 500


@webapp_storage_bp.route("/api/webapp/memory/tables/<table_name>/data", methods=["GET"])
def get_memory_data(table_name):
    """Get data from memory table"""
    try:
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        
        storage_manager = get_storage_manager()
        table = asyncio.run(storage_manager.get_memory_table(table_name))
        
        if not table:
            return jsonify({
                "error": "Memory table not found",
                "success": False
            }), 404
        
        # Get table data (convert to pandas for pagination)
        df = table.to_pandas()
        
        # Apply pagination
        total_rows = len(df)
        paginated_df = df.iloc[offset:offset + limit]
        
        return jsonify({
            "status": "success",
            "data": {
                "table_name": table_name,
                "records": paginated_df.to_dict('records'),
                "pagination": {
                    "total_rows": total_rows,
                    "limit": limit,
                    "offset": offset,
                    "returned_rows": len(paginated_df)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting memory data: {e}")
        return jsonify({
            "error": f"Failed to get memory data: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Storage Statistics Endpoints
# -------------------------------------------------------------------------

@webapp_storage_bp.route("/api/webapp/storage/stats", methods=["GET"])
def get_storage_stats():
    """Get comprehensive storage statistics"""
    try:
        storage_manager = get_storage_manager()
        stats = storage_manager.get_storage_stats()
        
        return jsonify({
            "status": "success",
            "data": stats
        })
        
    except Exception as e:
        logger.error(f"Error getting storage stats: {e}")
        return jsonify({
            "error": f"Failed to get storage stats: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Maintenance Endpoints
# -------------------------------------------------------------------------

@webapp_storage_bp.route("/api/webapp/storage/maintenance/compact", methods=["POST"])
def compact_storage():
    """Manually trigger storage compaction"""
    try:
        data = request.get_json() or {}
        table_name = data.get('table_name')
        
        storage_manager = get_storage_manager()
        
        if table_name:
            # Compact specific table
            success = asyncio.run(storage_manager.s3_lancedb_manager.compact_table(table_name))
            
            return jsonify({
                "status": "success" if success else "error",
                "message": f"Table {table_name} compaction {'completed' if success else 'failed'}",
                "data": {"table_name": table_name, "compacted": success}
            })
        else:
            # Compact all tables
            tables = storage_manager.list_memory_tables()
            results = {}
            
            for table in tables:
                try:
                    success = asyncio.run(storage_manager.s3_lancedb_manager.compact_table(table))
                    results[table] = success
                except Exception as e:
                    logger.error(f"Failed to compact table {table}: {e}")
                    results[table] = False
            
            return jsonify({
                "status": "success",
                "message": "Storage compaction completed",
                "data": {
                    "tables_compacted": sum(1 for success in results.values() if success),
                    "total_tables": len(results),
                    "results": results
                }
            })
        
    except Exception as e:
        logger.error(f"Error during storage compaction: {e}")
        return jsonify({
            "error": f"Failed to compact storage: {str(e)}",
            "success": False
        }), 500


@webapp_storage_bp.route("/api/webapp/storage/maintenance/status", methods=["GET"])
def get_maintenance_status():
    """Get maintenance service status"""
    try:
        storage_manager = get_storage_manager()
        
        status = {
            "auto_compact_enabled": storage_manager.auto_compact,
            "compact_interval_hours": storage_manager.compact_interval_seconds / 3600,
            "maintenance_running": storage_manager.compact_task is not None,
            "last_compaction": None  # Would need tracking
        }
        
        return jsonify({
            "status": "success",
            "data": status
        })
        
    except Exception as e:
        logger.error(f"Error getting maintenance status: {e}")
        return jsonify({
            "error": f"Failed to get maintenance status: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Health Check Endpoints
# -------------------------------------------------------------------------

@webapp_storage_bp.route("/api/webapp/storage/health", methods=["GET"])
def health_check():
    """Perform comprehensive health check on web app storage"""
    try:
        storage_manager = get_storage_manager()
        
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        # Check S3 connectivity
        try:
            storage_manager.s3_lancedb_manager.s3_client.head_bucket(
                Bucket=storage_manager.s3_lancedb_manager.config.bucket_name
            )
            
            s3_health = {
                "status": "healthy",
                "bucket_accessible": True,
                "bucket_name": storage_manager.s3_lancedb_manager.config.bucket_name
            }
            
        except Exception as e:
            s3_health = {
                "status": "unhealthy",
                "bucket_accessible": False,
                "error": str(e)
            }
            health_status["overall_status"] = "degraded"
        
        health_status["components"]["s3_storage"] = s3_health
        
        # Check LanceDB cache
        try:
            if storage_manager.s3_lancedb_manager.lancedb_local_cache:
                lancedb_health = {
                    "status": "healthy",
                    "cache_accessible": True,
                    "cache_path": str(storage_manager.s3_lancedb_manager.lancedb_local_cache.uri)
                }
            else:
                lancedb_health = {
                    "status": "unhealthy",
                    "cache_accessible": False
                }
                health_status["overall_status"] = "degraded"
            
        except Exception as e:
            lancedb_health = {
                "status": "unhealthy",
                "cache_accessible": False,
                "error": str(e)
            }
            health_status["overall_status"] = "degraded"
        
        health_status["components"]["lancedb_cache"] = lancedb_health
        
        # Check maintenance service
        maintenance_health = {
            "status": "healthy",
            "auto_compact_enabled": storage_manager.auto_compact,
            "maintenance_running": storage_manager.compact_task is not None
        }
        
        health_status["components"]["maintenance_service"] = maintenance_health
        
        # Get storage stats for additional health info
        try:
            stats = storage_manager.get_storage_stats()
            health_status["storage_info"] = stats
        except Exception as e:
            health_status["storage_info"] = {
                "error": str(e),
                "status": "unavailable"
            }
        
        return jsonify({
            "status": "success",
            "data": health_status
        })
        
    except Exception as e:
        logger.error(f"Error in web app storage health check: {e}")
        return jsonify({
            "error": f"Health check failed: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Advanced Management Endpoints
# -------------------------------------------------------------------------

@webapp_storage_bp.route("/api/webapp/storage/migrate", methods=["POST"])
def migrate_storage():
    """Migrate storage to new S3 bucket"""
    try:
        data = request.get_json()
        new_bucket = data.get('new_bucket')
        new_region = data.get('new_region', 'us-west-2')
        
        if not new_bucket:
            return jsonify({
                "error": "new_bucket is required",
                "success": False
            }), 400
        
        # This is a placeholder for storage migration functionality
        # In a complete implementation, this would:
        # 1. Create new S3 LanceDB manager
        # 2. Copy all tables to new location
        # 3. Update configuration
        # 4. Switch to new storage
        # 5. Verify integrity
        # 6. Clean up old storage
        
        return jsonify({
            "status": "not_implemented",
            "message": "S3 storage migration requires implementation",
            "requested_migration": {
                "new_bucket": new_bucket,
                "new_region": new_region
            }
        })
        
    except Exception as e:
        logger.error(f"Error in S3 storage migration: {e}")
        return jsonify({
            "error": f"S3 storage migration failed: {str(e)}",
            "success": False
        }), 500


@webapp_storage_bp.route("/api/webapp/storage/export", methods=["GET"])
def export_storage_manifest():
    """Export storage manifest"""
    try:
        storage_manager = get_storage_manager()
        tables = storage_manager.list_memory_tables()
        stats = storage_manager.get_storage_stats()
        
        manifest = {
            "export_timestamp": datetime.now().isoformat(),
            "deployment_type": "web",
            "storage_type": "s3_lancedb",
            "total_tables": len(tables),
            "tables": tables,
            "storage_stats": stats,
            "configuration": {
                "bucket_name": storage_manager.s3_lancedb_manager.config.bucket_name,
                "region": storage_manager.s3_lancedb_manager.config.region,
                "lancedb_prefix": storage_manager.s3_lancedb_manager.config.lancedb_prefix
            }
        }
        
        return jsonify({
            "status": "success",
            "data": manifest
        })
        
    except Exception as e:
        logger.error(f"Error exporting storage manifest: {e}")
        return jsonify({
            "error": f"Failed to export storage manifest: {str(e)}",
            "success": False
        }), 500


@webapp_storage_bp.route("/api/webapp/storage/optimize", methods=["POST"])
def optimize_storage():
    """Optimize storage performance"""
    try:
        data = request.get_json() or {}
        optimization_type = data.get('type', 'full')
        
        storage_manager = get_storage_manager()
        
        results = {}
        
        if optimization_type in ['full', 'compact']:
            # Compact all tables
            tables = storage_manager.list_memory_tables()
            compact_results = {}
            
            for table in tables:
                try:
                    success = asyncio.run(storage_manager.s3_lancedb_manager.compact_table(table))
                    compact_results[table] = success
                except Exception as e:
                    logger.error(f"Failed to compact table {table}: {e}")
                    compact_results[table] = False
            
            results['compact_tables'] = {
                'tables_compacted': sum(1 for success in compact_results.values() if success),
                'total_tables': len(compact_results),
                'results': compact_results
            }
        
        if optimization_type in ['full', 'cache']:
            # Clear and rebuild cache if needed
            # This would need implementation
            results['cache_optimization'] = {
                'status': 'not_implemented',
                'message': 'Cache optimization requires implementation'
            }
        
        return jsonify({
            "status": "success",
            "message": "Storage optimization completed",
            "data": {
                "optimization_type": optimization_type,
                "results": results
            }
        })
        
    except Exception as e:
        logger.error(f"Error optimizing storage: {e}")
        return jsonify({
            "error": f"Failed to optimize storage: {str(e)}",
            "success": False
        }), 500


logger.info("Web app storage API endpoints registered successfully")