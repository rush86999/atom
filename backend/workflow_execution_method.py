# This method should be added to the AutomationEngine class in automation_engine.py
# Add this as a method after the execute_workflow method

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


async def execute_workflow_definition(self, workflow_def: Dict[str, Any], input_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Execute a workflow from its definition (as stored in workflows.json)

    Args:
        workflow_def: Workflow definition with nodes and connections
        input_data: Optional input data for the workflow

    Returns:
        List of execution results for each node
    """
    results = []
    input_data = input_data or {}

    logger.info(f"Executing workflow: {workflow_def.get('name')}")

    # Execute each node in order
    for node in workflow_def.get('nodes', []):
        node_result = {
            "node_id": node['id'],
            "node_type": node['type'],
            "node_title": node['title'],
            "status": "pending",
            "output": None,
            "error": None
        }

        try:
            if node['type'] == 'action':
                node_result = await self._execute_action_node(node, node_result, input_data)

            elif node['type'] == 'trigger':
                node_result['status'] = "success"
                node_result['output'] = "Trigger node (manual execution)"

            elif node['type'] == 'condition':
                node_result = await self._execute_condition_node(node, node_result, input_data)

            elif node['type'] == 'delay':
                node_result = await self._execute_delay_node(node, node_result)

            elif node['type'] == 'http_request':
                node_result = await self._execute_http_request_node(node, node_result, input_data)

            elif node['type'] == 'transform':
                node_result = await self._execute_transform_node(node, node_result, input_data)

            else:
                node_result['status'] = "skipped"
                node_result['output'] = f"Node type '{node['type']}' not yet implemented"

        except Exception as e:
            logger.error(f"Error executing node {node['id']}: {e}")
            node_result['status'] = "failed"
            node_result['error'] = str(e)

        results.append(node_result)

    logger.info(f"Workflow execution complete with {len(results)} nodes processed")
    return results


async def _execute_action_node(self, node: Dict[str, Any], node_result: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute action node (email, slack, etc.)"""
    config = node.get('config', {})
    action_type = config.get('actionType')
    integration_id = config.get('integrationId')

    logger.info(f"Executing action node: {node['title']} (action: {action_type}, integration: {integration_id})")

    # Execute based on action type and integration
    if action_type == 'send_email' and integration_id == 'gmail':
        # Execute Gmail send email
        gmail_service = get_gmail_service()
        result = gmail_service.send_message(
            to=config.get('to', ''),
            subject=config.get('subject', 'No Subject'),
            body=config.get('body', '')
        )
        node_result['output'] = result
        node_result['status'] = "success"

    elif action_type == 'notify' and integration_id == 'slack':
        # Execute Slack notification
        result = await self.slack_service.send_message(
            channel=config.get('channel', '#general'),
            message=config.get('message', '')
        )
        node_result['output'] = result
        node_result['status'] = "success"

    else:
        node_result['status'] = "skipped"
        node_result['output'] = f"Action type '{action_type}' with integration '{integration_id}' not yet implemented"

    return node_result


async def _execute_condition_node(self, node: Dict[str, Any], node_result: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate condition/branching logic"""
    config = node.get('config', {})
    condition_type = config.get('conditionType', 'equals')  # equals, contains, greater_than, less_than, etc.
    field = config.get('field', '')
    expected_value = config.get('value', '')

    logger.info(f"Evaluating condition node: {node['title']} (field: {field}, condition: {condition_type})")

    # Get the actual value from input data
    actual_value = input_data.get(field, '')

    # Evaluate condition
    condition_met = False
    if condition_type == 'equals':
        condition_met = str(actual_value) == str(expected_value)
    elif condition_type == 'not_equals':
        condition_met = str(actual_value) != str(expected_value)
    elif condition_type == 'contains':
        condition_met = str(expected_value) in str(actual_value)
    elif condition_type == 'greater_than':
        try:
            condition_met = float(actual_value) > float(expected_value)
        except (ValueError, TypeError):
            condition_met = False
    elif condition_type == 'less_than':
        try:
            condition_met = float(actual_value) < float(expected_value)
        except (ValueError, TypeError):
            condition_met = False
    elif condition_type == 'exists':
        condition_met = field in input_data and actual_value is not None and actual_value != ''
    elif condition_type == 'not_exists':
        condition_met = field not in input_data or actual_value is None or actual_value == ''

    node_result['status'] = "success"
    node_result['output'] = {
        "condition_met": condition_met,
        "field": field,
        "actual_value": actual_value,
        "expected_value": expected_value,
        "condition_type": condition_type
    }

    logger.info(f"Condition result: {condition_met} ({field}={actual_value} {condition_type} {expected_value})")
    return node_result


async def _execute_delay_node(self, node: Dict[str, Any], node_result: Dict[str, Any]) -> Dict[str, Any]:
    """Wait for specified delay"""
    config = node.get('config', {})
    delay_seconds = config.get('delaySeconds', 0)
    delay_ms = config.get('delayMs', 0)

    # Calculate total delay (ms takes precedence, fallback to seconds)
    total_delay = delay_ms / 1000 if delay_ms else delay_seconds

    logger.info(f"Delay node: {node['title']} - waiting {total_delay}s")

    if total_delay > 0:
        await asyncio.sleep(total_delay)

    node_result['status'] = "success"
    node_result['output'] = {"delayed_seconds": total_delay}
    return node_result


async def _execute_http_request_node(self, node: Dict[str, Any], node_result: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Make HTTP request to external API"""
    config = node.get('config', {})
    url = config.get('url', '')
    method = config.get('method', 'GET').upper()
    headers = config.get('headers', {})
    body = config.get('body', {})
    timeout = config.get('timeout', 30)

    # Replace placeholders in URL with input data
    for key, value in input_data.items():
        url = str(url).replace(f'{{{key}}}', str(value))

    logger.info(f"HTTP request node: {node['title']} - {method} {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method in ['GET', 'HEAD']:
                response = await client.request(method, url, headers=headers)
            else:
                # POST, PUT, PATCH, DELETE
                response = await client.request(
                    method,
                    url,
                    json=body if method in ['POST', 'PUT', 'PATCH'] else None,
                    headers=headers
                )

            node_result['status'] = "success"
            node_result['output'] = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text if response.text else response.content,
                "url": str(response.url)
            }

            logger.info(f"HTTP request completed: {response.status_code}")

    except httpx.TimeoutException:
        node_result['status'] = "failed"
        node_result['error'] = f"Request timeout after {timeout}s"
        logger.error(f"HTTP request timeout: {url}")
    except httpx.HTTPError as e:
        node_result['status'] = "failed"
        node_result['error'] = f"HTTP error: {str(e)}"
        logger.error(f"HTTP request error: {e}")
    except Exception as e:
        node_result['status'] = "failed"
        node_result['error'] = f"Request error: {str(e)}"
        logger.error(f"Request error: {e}")

    return node_result


async def _execute_transform_node(self, node: Dict[str, Any], node_result: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform/modify data"""
    config = node.get('config', {})
    transform_type = config.get('transformType', 'map')  # map, filter, merge, rename, format
    mappings = config.get('mappings', {})  # For map/rename: {"old_key": "new_key"}
    filter_field = config.get('filterField', '')  # For filter: field to check
    filter_value = config.get('filterValue', '')  # For filter: value to match
    template = config.get('template', '')  # For format: string template with {placeholders}

    logger.info(f"Transform node: {node['title']} (type: {transform_type})")

    try:
        if transform_type == 'map':
            # Map/rename fields
            result = {}
            for old_key, new_key in mappings.items():
                if old_key in input_data:
                    result[new_key] = input_data[old_key]
            node_result['output'] = result

        elif transform_type == 'filter':
            # Filter data based on field value
            if isinstance(input_data, list):
                result = [item for item in input_data if str(item.get(filter_field, '')) == str(filter_value)]
            else:
                result = input_data if str(input_data.get(filter_field, '')) == str(filter_value) else {}
            node_result['output'] = result

        elif transform_type == 'merge':
            # Merge additional data with input
            additional_data = config.get('data', {})
            result = {**input_data, **additional_data}
            node_result['output'] = result

        elif transform_type == 'format':
            # Format string template with input data
            result = template.format(**input_data)
            node_result['output'] = result

        elif transform_type == 'extract':
            # Extract specific fields
            fields_to_extract = config.get('fields', [])
            if isinstance(input_data, dict):
                result = {k: input_data.get(k) for k in fields_to_extract if k in input_data}
            else:
                result = input_data
            node_result['output'] = result

        else:
            node_result['status'] = "skipped"
            node_result['output'] = f"Transform type '{transform_type}' not yet implemented"
            return node_result

        node_result['status'] = "success"
        logger.info(f"Transform completed: {transform_type}")

    except Exception as e:
        node_result['status'] = "failed"
        node_result['error'] = f"Transform error: {str(e)}"
        logger.error(f"Transform error: {e}")

    return node_result
