from .celery_app import app
import httpx
from celery import group

@app.task
def execute_http_request(action):
    with httpx.Client() as client:
        response = client.request(action['method'], action['url'])
        return response.status_code

@app.task
def execute_workflow(workflow):
    actions = workflow['definition']['nodes']
    # Filter out the 'input' node
    actions = [action for action in actions if action['type'] != 'input']

    # Create a group of tasks to be executed in parallel
    task_group = group(execute_http_request.s(action['data']) for action in actions)
    result = task_group.apply_async()
    return result.id
