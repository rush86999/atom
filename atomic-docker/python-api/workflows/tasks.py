from .celery_app import celery_app
from . import database, models
from sqlalchemy.orm import Session
import json
import time

@celery_app.task
def execute_workflow(workflow_id: str):
    db: Session = next(database.get_db())
    workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if not workflow:
        print(f"Workflow with id {workflow_id} not found")
        return

    print(f"Executing workflow: {workflow.name}")
    definition = workflow.definition
    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    # For the PoC, we'll just print the nodes and edges
    print("Nodes:")
    for node in nodes:
        print(f"  - {node['id']}: {node['type']}")

    print("Edges:")
    for edge in edges:
        print(f"  - {edge['source']} -> {edge['target']}")

    # Simulate a long-running task
    time.sleep(10)

    print(f"Workflow {workflow.name} executed successfully")
