import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def delay_execution(self, duration_seconds: int = 60) -> Dict[str, Any]:
    """
    Delay workflow execution for a specified duration

    Args:
        duration_seconds: Number of seconds to delay

    Returns:
        Dictionary with delay information
    """
    try:
        logger.info(f"Delaying execution for {duration_seconds} seconds")

        # Simulate delay
        time.sleep(duration_seconds)

        return {
            "status": "completed",
            "delay_duration": duration_seconds,
            "completed_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in delay execution: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def flatten_list(self, nested_list: List[Any]) -> Dict[str, Any]:
    """
    Flatten a nested list into a single list

    Args:
        nested_list: Nested list to flatten

    Returns:
        Dictionary with flattened list
    """
    try:
        logger.info(f"Flattening list with {len(nested_list)} items")

        def _flatten(items):
            flattened = []
            for item in items:
                if isinstance(item, list):
                    flattened.extend(_flatten(item))
                else:
                    flattened.append(item)
            return flattened

        flattened = _flatten(nested_list)

        return {
            "original_length": len(nested_list),
            "flattened_length": len(flattened),
            "flattened_list": flattened,
            "nested_levels_reduced": True if any(isinstance(item, list) for item in nested_list) else False
        }

    except Exception as e:
        logger.error(f"Error flattening list: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def filter_with_llm(self, items: List[Any], condition: str) -> Dict[str, Any]:
    """
    Filter items using natural language condition with AI

    Args:
        items: List of items to filter
        condition: Natural language condition for filtering

    Returns:
        Dictionary with filtered results
    """
    try:
        logger.info(f"Filtering {len(items)} items with condition: {condition}")

        # Placeholder implementation - would use AI for natural language filtering
        # For now, we'll simulate filtering based on simple conditions

        filtered_items = []
        for item in items:
            # Simple simulation - in real implementation, this would use AI
            if isinstance(item, str) and condition.lower() in ["contains text", "has text"]:
                if len(item) > 5:  # Simple heuristic
                    filtered_items.append(item)
            elif isinstance(item, (int, float)) and condition.lower() in ["greater than", "larger than"]:
                if item > 10:  # Simple heuristic
                    filtered_items.append(item)
            else:
                # Default: include all items for demonstration
                filtered_items.append(item)

        return {
            "original_count": len(items),
            "filtered_count": len(filtered_items),
            "filtered_items": filtered_items,
            "condition_applied": condition,
            "filtering_method": "ai_simulation"
        }

    except Exception as e:
        logger.error(f"Error filtering with LLM: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def batch_process_items(self, items: List[Any], batch_size: int = 10) -> Dict[str, Any]:
    """
    Process items in batches

    Args:
        items: List of items to process
        batch_size: Number of items per batch

    Returns:
        Dictionary with batch processing results
    """
    try:
        logger.info(f"Processing {len(items)} items in batches of {batch_size}")

        batches = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batches.append({
                "batch_number": len(batches) + 1,
                "items": batch,
                "batch_size": len(batch),
                "processed_at": datetime.now().isoformat()
            })

        return {
            "total_items": len(items),
            "total_batches": len(batches),
            "batch_size": batch_size,
            "batches": batches,
            "processing_complete": True
        }

    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def transform_data(self, data: Any, transformation_type: str, **kwargs) -> Dict[str, Any]:
    """
    Apply various data transformations

    Args:
        data: Data to transform
        transformation_type: Type of transformation to apply
        **kwargs: Additional transformation parameters

    Returns:
        Dictionary with transformation results
    """
    try:
        logger.info(f"Applying {transformation_type} transformation to data")

        result = None

        if transformation_type == "uppercase" and isinstance(data, str):
            result = data.upper()

        elif transformation_type == "lowercase" and isinstance(data, str):
            result = data.lower()

        elif transformation_type == "trim" and isinstance(data, str):
            result = data.strip()

        elif transformation_type == "reverse" and isinstance(data, str):
            result = data[::-1]

        elif transformation_type == "json_stringify":
            result = json.dumps(data)

        elif transformation_type == "json_parse" and isinstance(data, str):
            try:
                result = json.loads(data)
            except json.JSONDecodeError:
                result = {"error": "Invalid JSON"}

        elif transformation_type == "timestamp_to_date" and isinstance(data, (int, float)):
            result = datetime.fromtimestamp(data).isoformat()

        else:
            result = data  # No transformation applied

        return {
            "transformation_type": transformation_type,
            "original_data": data,
            "transformed_data": result,
            "transformation_applied": result != data,
            "parameters": kwargs
        }

    except Exception as e:
        logger.error(f"Error in data transformation: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def conditional_branch(self, condition: bool, true_branch_data: Any, false_branch_data: Any) -> Dict[str, Any]:
    """
    Conditional branching in workflows

    Args:
        condition: Boolean condition to evaluate
        true_branch_data: Data to return if condition is True
        false_branch_data: Data to return if condition is False

    Returns:
        Dictionary with branch selection and data
    """
    try:
        logger.info(f"Evaluating conditional branch: {condition}")

        selected_branch = "true" if condition else "false"
        selected_data = true_branch_data if condition else false_branch_data

        return {
            "condition_evaluated": condition,
            "selected_branch": selected_branch,
            "selected_data": selected_data,
            "evaluated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in conditional branch: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def aggregate_data(self, items: List[Any], aggregation_type: str) -> Dict[str, Any]:
    """
    Aggregate data with various methods

    Args:
        items: List of items to aggregate
        aggregation_type: Type of aggregation to perform

    Returns:
        Dictionary with aggregation results
    """
    try:
        logger.info(f"Aggregating {len(items)} items with {aggregation_type}")

        result = None

        if aggregation_type == "sum" and all(isinstance(item, (int, float)) for item in items):
            result = sum(items)

        elif aggregation_type == "average" and all(isinstance(item, (int, float)) for item in items):
            result = sum(items) / len(items) if items else 0

        elif aggregation_type == "count":
            result = len(items)

        elif aggregation_type == "min" and all(isinstance(item, (int, float)) for item in items):
            result = min(items) if items else None

        elif aggregation_type == "max" and all(isinstance(item, (int, float)) for item in items):
            result = max(items) if items else None

        elif aggregation_type == "concatenate" and all(isinstance(item, str) for item in items):
            result = "".join(items)

        elif aggregation_type == "join" and all(isinstance(item, str) for item in items):
            separator = " "  # Default separator
            result = separator.join(items)

        else:
            result = items  # Return original if aggregation not applicable

        return {
            "aggregation_type": aggregation_type,
            "input_items": items,
            "result": result,
            "items_processed": len(items),
            "aggregation_applied": result != items
        }

    except Exception as e:
        logger.error(f"Error in data aggregation: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def workflow_logger(self, message: str, level: str = "INFO", data: Optional[Any] = None) -> Dict[str, Any]:
    """
    Log messages and data during workflow execution

    Args:
        message: Log message
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        data: Additional data to log

    Returns:
        Dictionary with logging information
    """
    try:
        # Log based on level
        log_level = level.upper()
        if log_level == "DEBUG":
            logger.debug(f"Workflow Log: {message}")
        elif log_level == "INFO":
            logger.info(f"Workflow Log: {message}")
        elif log_level == "WARNING":
            logger.warning(f"Workflow Log: {message}")
        elif log_level == "ERROR":
            logger.error(f"Workflow Log: {message}")
        elif log_level == "CRITICAL":
            logger.critical(f"Workflow Log: {message}")
        else:
            logger.info(f"Workflow Log: {message}")

        return {
            "logged_message": message,
            "log_level": log_level,
            "logged_data": data,
            "timestamp": datetime.now().isoformat(),
            "logging_successful": True
        }

    except Exception as e:
        logger.error(f"Error in workflow logging: {e}")
        raise self.retry(exc=e, countdown=30)
