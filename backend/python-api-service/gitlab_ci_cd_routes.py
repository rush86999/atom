#!/usr/bin/env python3
"""
🚀 GITLAB CI/CD ROUTES
API endpoints for GitLab CI/CD integration with advanced workflow automation
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

# Import the GitLab CI/CD integration
try:
    from gitlab_ci_cd_integration import (
        GitLabCICDIntegration,
        GitLabProject,
        GitLabPipeline,
        GitLabJob,
        PipelineStatus,
        JobStatus,
        PipelineMetrics,
    )

    GITLAB_CI_CD_AVAILABLE = True
except ImportError as e:
    GITLAB_CI_CD_AVAILABLE = False
    logging.warning(f"GitLab CI/CD Integration not available: {e}")

# Create blueprint for GitLab CI/CD routes
gitlab_ci_cd_routes = Blueprint("gitlab_ci_cd_routes", __name__)

# Global instance of the GitLab CI/CD integration
gitlab_integration = None


def get_gitlab_integration():
    """Get or initialize the GitLab CI/CD integration"""
    global gitlab_integration
    if gitlab_integration is None and GITLAB_CI_CD_AVAILABLE:
        gitlab_integration = GitLabCICDIntegration()
        # Initialize asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(gitlab_integration.initialize())
    return gitlab_integration


@gitlab_ci_cd_routes.route("/api/v2/gitlab/status", methods=["GET"])
def get_gitlab_status():
    """Get status of GitLab CI/CD integration"""
    try:
        integration = get_gitlab_integration()
        if not integration:
            return jsonify(
                {
                    "success": False,
                    "available": False,
                    "message": "GitLab CI/CD Integration not available",
                }
            ), 503

        return jsonify(
            {
                "success": True,
                "available": True,
                "initialized": integration.initialized,
                "project_count": len(integration.projects),
                "pipeline_count": len(integration.pipelines),
                "job_count": len(integration.jobs),
                "integration_status": "active" if integration.initialized else "initializing",
                "mock_mode": integration.access_token is None or integration.access_token.startswith(("mock_", "YOUR_")),
            }
        )

    except Exception as e:
        logging.error(f"Error getting GitLab status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gitlab_ci_cd_routes.route("/api/v2/gitlab/projects", methods=["GET"])
def get_gitlab_projects():
    """Get all accessible GitLab projects"""
    try:
        integration = get_gitlab_integration()
        if not integration:
            return jsonify(
                {
                    "success": False,
                    "error": "GitLab CI/CD Integration not available",
                }
            ), 503

        # Get projects asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        projects = loop.run_until_complete(integration.get_projects())

        projects_data = []
        for project in projects:
            projects_data.append(
                {
                    "project_id": project.project_id,
                    "name": project.name,
                    "description": project.description,
                    "web_url": project.web_url,
                    "ssh_url": project.ssh_url,
                    "http_url": project.http_url,
                    "namespace": project.namespace,
                    "created_at": project.created_at.isoformat(),
                    "last_activity_at": project.last_activity_at.isoformat(),
                }
            )

        return jsonify(
            {
                "success": True,
                "projects": projects_data,
                "total_projects": len(projects_data),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting GitLab projects: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gitlab_ci_cd_routes.route("/api/v2/gitlab/projects/<int:project_id>/pipelines", methods=["GET"])
def get_project_pipelines(project_id):
    """Get pipelines for a specific GitLab project"""
    try:
        integration = get_gitlab_integration()
        if not integration:
            return jsonify(
                {
                    "success": False,
                    "error": "GitLab CI/CD Integration not available",
                }
            ), 503

        # Get limit parameter
        limit = request.args.get("limit", 20, type=int)

        # Get pipelines asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pipelines = loop.run_until_complete(integration.get_project_pipelines(project_id, limit))

        pipelines_data = []
        for pipeline in pipelines:
            pipelines_data.append(
                {
                    "pipeline_id": pipeline.pipeline_id,
                    "project_id": pipeline.project_id,
                    "status": pipeline.status.value,
                    "ref": pipeline.ref,
                    "sha": pipeline.sha,
                    "web_url": pipeline.web_url,
                    "created_at": pipeline.created_at.isoformat(),
                    "updated_at": pipeline.updated_at.isoformat(),
                    "started_at": pipeline.started_at.isoformat() if pipeline.started_at else None,
                    "finished_at": pipeline.finished_at.isoformat() if pipeline.finished_at else None,
                    "duration": pipeline.duration,
                }
            )

        return jsonify(
            {
                "success": True,
                "project_id": project_id,
                "pipelines": pipelines_data,
                "total_pipelines": len(pipelines_data),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting GitLab pipelines for project {project_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gitlab_ci_cd_routes.route("/api/v2/gitlab/projects/<int:project_id>/pipelines/<int:pipeline_id>/jobs", methods=["GET"])
def get_pipeline_jobs(project_id, pipeline_id):
    """Get jobs for a specific GitLab pipeline"""
    try:
        integration = get_gitlab_integration()
        if not integration:
            return jsonify(
                {
                    "success": False,
                    "error": "GitLab CI/CD Integration not available",
                }
            ), 503

        # Get jobs asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        jobs = loop.run_until_complete(integration.get_pipeline_jobs(project_id, pipeline_id))

        jobs_data = []
        for job in jobs:
            jobs_data.append(
                {
                    "job_id": job.job_id,
                    "pipeline_id": job.pipeline_id,
                    "project_id": job.project_id,
                    "name": job.name,
                    "stage": job.stage,
                    "status": job.status.value,
                    "ref": job.ref,
                    "created_at": job.created_at.isoformat(),
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                    "duration": job.duration,
                    "web_url": job.web_url,
                }
            )

        return jsonify(
            {
                "success": True,
                "project_id": project_id,
                "pipeline_id": pipeline_id,
                "jobs": jobs_data,
                "total_jobs": len(jobs_data),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting GitLab jobs for pipeline {pipeline_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gitlab_ci_cd_routes.route("/api/v2/gitlab/projects/<int:project_id>/pipelines/trigger", methods=["POST"])
def trigger_pipeline(project_id):
    """Trigger a new pipeline for a GitLab project"""
    try:
        integration = get_gitlab_integration()
        if not integration:
            return jsonify(
                {
                    "success": False,
                    "error": "GitLab CI/CD Integration not available",
                }
            ), 503

        data = request.get_json() or {}
        ref = data.get("ref", "main")
        variables = data.get("variables", {})

        # Trigger pipeline asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pipeline = loop.run_until_complete(integration.trigger_pipeline(project_id, ref, variables))

        if not pipeline:
            return jsonify({"success": False, "error": "Failed to trigger pipeline"}), 400

        pipeline_data = {
            "pipeline_id": pipeline.pipeline_id,
            "project_id": pipeline.project_id,
            "status": pipeline.status.value,
            "ref": pipeline.ref,
            "sha": pipeline.sha,
            "web_url": pipeline.web_url,
            "created_at": pipeline.created_at.isoformat(),
            "updated_at": pipeline.updated_at.isoformat(),
            "started_at": pipeline.started_at.isoformat() if pipeline.started_at else None,
            "finished_at": pipeline.finished_at.isoformat() if pipeline.finished_at else None,
            "duration": pipeline.duration,
        }

        return jsonify(
            {
                "success": True,
                "message": f"Pipeline triggered successfully for project {project_id}",
                "pipeline": pipeline_data,
                "timestamp": datetime.now().isoformat(),
            }
        ), 201

    except Exception as e:
        logging.error(f"Error triggering GitLab pipeline for project {project_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gitlab_ci_cd_routes.route("/api/v2/gitlab/pipelines/<int:pipeline_id>/metrics", methods=["GET"])
def get_pipeline_metrics(pipeline_id):
    """Get performance metrics for a specific pipeline"""
    try:
        integration = get_gitlab_integration()
        if not integration:
            return jsonify(
                {
                    "success": False,
                    "error": "GitLab CI/CD Integration not available",
                }
            ), 503

        # Get metrics asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        metrics = loop.run_until_complete(integration.get_pipeline_metrics(pipeline_id))

        if not metrics:
            return jsonify({"success": False, "error": "Pipeline metrics not available"}), 404

        metrics_data = {
            "pipeline_id": metrics.pipeline_id,
            "total_jobs": metrics.total_jobs,
            "successful_jobs": metrics.successful_jobs,
            "failed_jobs": metrics.failed_jobs,
            "total_duration": metrics.total_duration,
            "average_job_duration": metrics.average_job_duration,
            "success_rate": metrics.success_rate,
            "timestamp": metrics.timestamp.isoformat(),
        }

        return jsonify(
            {
                "success": True,
                "pipeline_id": pipeline_id,
                "metrics": metrics_data,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting metrics for pipeline {pipeline_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gitlab_ci_cd_routes.route("/api/v2/gitlab/analytics", methods=["GET"])
def get_gitlab_analytics():
    """Get comprehensive analytics for GitLab CI/CD"""
    try:
        integration = get_gitlab_integration()
        if not integration:
            return jsonify(
                {
                    "success": False,
                    "error": "GitLab CI/CD Integration not available",
                }
            ), 503

        # Calculate analytics from existing data
        total_pipelines = len(integration.pipelines)
        successful_pipelines = len([p for p in integration.pipelines.values() if p.status == PipelineStatus.SUCCESS])
        failed_pipelines = len([p for p in integration.pipelines.values() if p.status == PipelineStatus.FAILED])
        running_pipelines = len([p for p in integration.pipelines.values() if p.status == PipelineStatus.RUNNING])

        total_jobs = len(integration.jobs)
        successful_jobs = len([j for j in integration.jobs.values() if j.status == JobStatus.SUCCESS])
        failed_jobs = len([j for j in integration.jobs.values() if j.status == JobStatus.FAILED])

        # Calculate average pipeline duration
        completed_pipelines = [p for p in integration.pipelines.values() if p.duration is not None]
        avg_pipeline_duration = sum(p.duration for p in completed_pipelines) / len(completed_pipelines) if completed_pipelines else 0

        # Calculate average job duration
        completed_jobs = [j for j in integration.jobs.values() if j.duration is not None]
        avg_job_duration = sum(j.duration for j in completed_jobs) / len(completed_jobs) if completed_jobs else 0

        analytics = {
            "project_count": len(integration.projects),
            "pipeline_count": total_pipelines,
            "job_count": total_jobs,
            "pipeline_success_rate": (successful_pipelines / total_pipelines * 100) if total_pipelines > 0 else 0,
            "job_success_rate": (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0,
            "running_pipelines": running_pipelines,
            "failed_pipelines": failed_pipelines,
            "failed_jobs": failed_jobs,
            "average_pipeline_duration": avg_pipeline_duration,
            "average_job_duration": avg_job_duration,
            "total_projects_with_pipelines": len(set(p.project_id for p in integration.pipelines.values())),
        }

        return jsonify(
            {
                "success": True,
                "analytics": analytics,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting GitLab analytics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gitlab_ci_cd_routes.route("/api/v2/gitlab/webhook", methods=["POST"])
def handle_gitlab_webhook():
    """Handle GitLab webhook events"""
    try:
        integration = get_gitlab_integration()
        if not integration:
            return jsonify(
                {
                    "success": False,
                    "error": "GitLab CI/CD Integration not available",
                }
            ), 503

        webhook_data = request.get_json()
        if not webhook_data:
            return jsonify({"success": False, "error": "No webhook data provided"}), 400

        # Extract webhook information
        event_type = request.headers.get("X-Gitlab-Event", "unknown")
        object_kind = webhook_data.get("object_kind", "unknown")

        logger.info(f"📨 GitLab webhook received: {event_type} - {object_kind}")

        # Process different webhook types
        if object_kind == "pipeline":
            await _process_pipeline_webhook(webhook_data)
        elif object_kind == "job":
            await _process_job_webhook(webhook_data)
        elif object_kind == "push":
            await _process_push_webhook(webhook_data)
        else:
            logger.info(f"Unhandled GitLab webhook type: {object_kind}")

        return jsonify(
            {
                "success": True,
                "message": f"Webhook processed: {event_type} - {object_kind}",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error processing GitLab webhook: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


async def _process_pipeline_webhook(webhook_data: Dict[str, Any]):
    """Process pipeline webhook events"""
    try:
        pipeline_data = webhook_data.get("object_attributes", {})
        pipeline_id = pipeline_data.get("id")
        status = pipeline_data.get("status")
        ref = pipeline_data.get("ref")
        project_id = webhook_data.get("project", {}).get("id")

        logger.info(f"🔄 Processing pipeline webhook: {pipeline_id} - {status} - {ref}")

        # In production, this would trigger workflows or notifications
        # For now, just log the event
        if status == "success":
            logger.info(f"✅ Pipeline {pipeline_id} completed successfully")
        elif status == "failed":
            logger.info(f"❌ Pipeline {pipeline_id} failed")
        elif status == "running":
            logger.info(f"🔄 Pipeline {pipeline_id} started running")

    except Exception as e:
        logger.error(f"Error processing pipeline webhook: {e}")


async def _process_job_webhook(webhook_data: Dict[str, Any]):
    """Process job webhook events"""
    try:
        job_data = webhook_data.get("build", {})
        job_id = job_data.get("id")
        status = job_data.get("status")
        job_name = job_data.get("name")
        stage = job_data.get("stage")

        logger.info(f"🔄 Processing job webhook: {job_id} - {job_name} - {stage} - {status}")

        # In production, this would trigger specific actions based on job status
        if status == "success":
            logger.info(f"✅ Job {job_name} completed successfully")
        elif status == "failed":
            logger.info(f"❌ Job {job_name} failed")

    except Exception as e:
        logger.error(f"Error processing job webhook: {e}")


async def _process_push_webhook(webhook_data: Dict[str, Any]):
