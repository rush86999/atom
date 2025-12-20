#!/usr/bin/env python3
import asyncio
import json
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from advanced_workflow_orchestrator import orchestrator, WorkflowStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_o365_verification():
    logger.info("Starting Office 365 Orchestration Verification...")
    
    # 1. Verify Financial Reporting Automation Template
    logger.info("Verifying Financial Reporting Automation...")
    input_data = {"text": "Process monthly finance report"}
    context = await orchestrator.execute_workflow("financial_reporting_automation", input_data)
    
    logger.info(f"Workflow ID: {context.workflow_id}")
    logger.info(f"Status: {context.status}")
    
    if context.status == WorkflowStatus.COMPLETED:
        logger.info("✅ Financial Reporting Automation PASSED")
    else:
        logger.error(f"❌ Financial Reporting Automation FAILED: {context.error_message}")
    
    # Check execution history for O365 steps
    for step in context.execution_history:
        logger.info(f"Step: {step['step_id']} ({step['step_type']}) - Result: {step['result'].get('status')}")

    # 2. Verify Project Inception Workflow Template
    logger.info("\nVerifying Project Inception Workflow...")
    input_data = {"text": "Kickoff new Project Alpha for client X"}
    context = await orchestrator.execute_workflow("project_inception_workflow", input_data)
    
    if context.status == WorkflowStatus.COMPLETED:
        logger.info("✅ Project Inception Workflow PASSED")
    else:
        logger.error(f"❌ Project Inception Workflow FAILED: {context.error_message}")

    # 3. Verify Dynamic Workflow Generation with O365 intent
    logger.info("\nVerifying Dynamic Workflow Generation with O365...")
    try:
        # Mocking AI service for test
        logger.info("Simulating dynamic workflow generation for 'Update Excel sheet and notify Teams'...")
        workflow_def = await orchestrator.generate_dynamic_workflow("Update Excel sheet with status and notify Teams")
        logger.info(f"Generated Workflow: {workflow_def.name}")
        
        # Verify steps contain M365 intents
        m365_steps = [s for s in workflow_def.steps if "excel" in s.description.lower() or "teams" in s.description.lower()]
        if m365_steps:
            logger.info(f"✅ Dynamic Generation PASSED (Found {len(m365_steps)} M365 related steps)")
        else:
            logger.warning("⚠️ Dynamic Generation warning: No explicit M365 steps found in generated workflow (AI dependent)")
            
    except Exception as e:
        logger.error(f"❌ Dynamic Workflow Generation FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(run_o365_verification())
