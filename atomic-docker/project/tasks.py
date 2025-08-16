from .celery_app import app
import httpx
from celery import group

SERVICE_URLS = {
    'dropbox': 'http://dropbox-api:5001',
    # Add other services here
}

@app.task
def execute_http_request(method, url, json_data):
    with httpx.Client() as client:
        response = client.request(method, url, json=json_data)
        return response.status_code, response.json()

@app.task
def execute_workflow(workflow):
    nodes = workflow['definition']['nodes']
    edges = workflow['definition']['edges']

    # For simplicity, we will still execute all actions in parallel for now.
    # A full implementation would traverse the graph.

    tasks = []
    for node in nodes:
        if node['type'] == 'genericNode':
            service = node['data']['service']
            # e.g., 'Save File' -> 'save-file'
            action_name = node['data']['name'].lower().replace(' ', '-')

            if service in SERVICE_URLS:
                url = f"{SERVICE_URLS[service]}/{action_name}"
                method = 'POST' # Assuming all actions are POST for now
                params = node['data']['values']
                tasks.append(execute_http_request.s(method, url, params))

    if tasks:
        task_group = group(tasks)
        result = task_group.apply_async()
        return result.id

    return None
