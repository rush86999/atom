# This method should be added to the AutomationEngine class in automation_engine.py
# Add this as a method after the execute_workflow method

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
                # Get node configuration
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
                    # Unsupported action type
                    node_result['status'] = "skipped"
                    node_result['output'] = f"Action type '{action_type}' with integration '{integration_id}' not yet implemented"
                    
            elif node['type'] == 'trigger':
                # Trigger nodes don't execute, they just define when the workflow runs
                node_result['status'] = "success"
                node_result['output'] = "Trigger node (manual execution)"
                
            else:
                # Other node types (condition, delay, etc.)
                node_result['status'] = "skipped"
                node_result['output'] = f"Node type '{node['type']}' not yet implemented"
                
        except Exception as e:
            logger.error(f"Error executing node {node['id']}: {e}")
            node_result['status'] = "failed"
            node_result['error'] = str(e)
            
        results.append(node_result)
        
    logger.info(f"Workflow execution complete with {len(results)} nodes processed")
    return results
