import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import datetime
import uuid

class WorkflowsHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == '/healthz':
            self._get_health()
        elif path == '/workflows':
            self._get_workflows()
        elif path.startswith('/workflows/'):
            workflow_id = path.split('/')[-1]
            self._get_workflow(workflow_id)
        elif path == '/instances':
            self._get_instances()
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == '/workflows':
            self._create_workflow()
        elif path.startswith('/workflows/') and path.endswith('/execute'):
            workflow_id = path.split('/')[-2]
            self._execute_workflow(workflow_id)
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def do_PUT(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path.startswith('/workflows/'):
            workflow_id = path.split('/')[-1]
            self._update_workflow(workflow_id)
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def do_DELETE(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path.startswith('/workflows/'):
            workflow_id = path.split('/')[-1]
            self._delete_workflow(workflow_id)
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def _get_health(self):
        self._set_headers(200)
        response = {
            'status': 'ok',
            'version': '1.0.0',
            'timestamp': datetime.datetime.now().isoformat(),
            'active_workflows': len([w for w in workflows.values() if w.get('enabled', True)])
        }
        self.wfile.write(json.dumps(response).encode())

    def _get_workflows(self):
        self._set_headers(200)
        response = {
            'workflows': list(workflows.values()),
            'total': len(workflows)
        }
        self.wfile.write(json.dumps(response).encode())

    def _get_workflow(self, workflow_id):
        if workflow_id not in workflows:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Workflow not found'}).encode())
            return

        self._set_headers(200)
        self.wfile.write(json.dumps(workflows[workflow_id]).encode())

    def _get_instances(self):
        self._set_headers(200)
        response = {
            'instances': list(instances.values()),
            'total': len(instances)
        }
        self.wfile.write(json.dumps(response).encode())

    def _create_workflow(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            workflow_data = json.loads(post_data.decode())
            workflow_id = str(uuid.uuid4())

            workflow = {
                'id': workflow_id,
                'name': workflow_data.get('name', 'Unnamed Workflow'),
                'description': workflow_data.get('description', ''),
                'trigger_type': workflow_data.get('trigger_type', 'manual'),
                'trigger_config': workflow_data.get('trigger_config', {}),
                'tasks': workflow_data.get('tasks', []),
                'enabled': workflow_data.get('enabled', True),
                'created_at': datetime.datetime.now().isoformat(),
                'updated_at': datetime.datetime.now().isoformat()
            }

            workflows[workflow_id] = workflow

            self._set_headers(201)
            self.wfile.write(json.dumps({
                'id': workflow_id,
                'message': 'Workflow created successfully'
            }).encode())

        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode())

    def _update_workflow(self, workflow_id):
        if workflow_id not in workflows:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Workflow not found'}).encode())
            return

        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            workflow_data = json.loads(post_data.decode())

            # Update existing workflow
            workflows[workflow_id].update({
                'name': workflow_data.get('name', workflows[workflow_id]['name']),
                'description': workflow_data.get('description', workflows[workflow_id]['description']),
                'trigger_type': workflow_data.get('trigger_type', workflows[workflow_id]['trigger_type']),
                'trigger_config': workflow_data.get('trigger_config', workflows[workflow_id]['trigger_config']),
                'tasks': workflow_data.get('tasks', workflows[workflow_id]['tasks']),
                'enabled': workflow_data.get('enabled', workflows[workflow_id]['enabled']),
                'updated_at': datetime.datetime.now().isoformat()
            })

            self._set_headers(200)
            self.wfile.write(json.dumps({
                'message': 'Workflow updated successfully'
            }).encode())

        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode())

    def _delete_workflow(self, workflow_id):
        if workflow_id not in workflows:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Workflow not found'}).encode())
            return

        del workflows[workflow_id]
        self._set_headers(200)
        self.wfile.write(json.dumps({
            'message': 'Workflow deleted successfully'
        }).encode())

    def _execute_workflow(self, workflow_id):
        if workflow_id not in workflows:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Workflow not found'}).encode())
            return

        workflow = workflows[workflow_id]
        if not workflow.get('enabled', True):
            self._set_headers(400)
            self.wfile.write(json.dumps({'error': 'Workflow is disabled'}).encode())
            return

        instance_id = str(uuid.uuid4())
        instance = {
            'instance_id': instance_id,
            'workflow_id': workflow_id,
            'status': 'running',
            'current_task': 0,
            'total_tasks': len(workflow.get('tasks', [])),
            'start_time': datetime.datetime.now().isoformat(),
            'end_time': None,
            'error_message': None,
            'results': {}
        }

        instances[instance_id] = instance

        self._set_headers(202)
        self.wfile.write(json.dumps({
            'instance_id': instance_id,
            'message': 'Workflow execution started',
            'status': 'running'
        }).encode())

# In-memory storage for development
workflows = {}
instances = {}

def run_server(port=8003):
    server_address = ('', port)
    httpd = HTTPServer(server_address, WorkflowsHandler)
    print(f'Starting workflows development server on port {port}...')
    print(f'Health check: http://localhost:{port}/healthz')
    print(f'Workflows API: http://localhost:{port}/workflows')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
