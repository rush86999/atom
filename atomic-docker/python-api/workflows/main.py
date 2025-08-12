from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from . import models, database
from .database import engine
from uuid import UUID
from .tasks import execute_workflow
from celery.result import AsyncResult

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/workflows/", response_model=models.Workflow)
def create_workflow(workflow: models.WorkflowCreate, db: Session = Depends(database.get_db)):
    # This is a placeholder for the user_id. In a real application, this would come from the auth system.
    user_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    db_workflow = models.Workflow(**workflow.dict(), user_id=user_id)
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@app.get("/workflows/", response_model=List[models.Workflow])
def read_workflows(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    # This is a placeholder for the user_id.
    user_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    workflows = db.query(models.Workflow).filter(models.Workflow.user_id == user_id).offset(skip).limit(limit).all()
    return workflows

@app.get("/workflows/{workflow_id}", response_model=models.Workflow)
def read_workflow(workflow_id: UUID, db: Session = Depends(database.get_db)):
    # This is a placeholder for the user_id.
    user_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    db_workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id).first()
    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return db_workflow

@app.put("/workflows/{workflow_id}", response_model=models.Workflow)
def update_workflow(workflow_id: UUID, workflow: models.WorkflowCreate, db: Session = Depends(database.get_db)):
    # This is a placeholder for the user_id.
    user_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    db_workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id).first()
    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    for key, value in workflow.dict().items():
        setattr(db_workflow, key, value)

    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@app.delete("/workflows/{workflow_id}", response_model=models.Workflow)
def delete_workflow(workflow_id: UUID, db: Session = Depends(database.get_db)):
    # This is a placeholder for the user_id.
    user_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    db_workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id).first()
    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    db.delete(db_workflow)
    db.commit()
    return db_workflow

@app.post("/workflows/{workflow_id}/trigger")
def trigger_workflow(workflow_id: UUID, db: Session = Depends(database.get_db)):
    user_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    db_workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id).first()
    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    task = execute_workflow.delay(str(workflow_id))
    db_workflow.celery_task_id = task.id
    db.commit()

    return {"message": "Workflow triggered successfully", "task_id": task.id}

@app.post("/workflows/{workflow_id}/untrigger")
def untrigger_workflow(workflow_id: UUID, db: Session = Depends(database.get_db)):
    user_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    db_workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id).first()
    if db_workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if db_workflow.celery_task_id:
        AsyncResult(db_workflow.celery_task_id).revoke(terminate=True)
        db_workflow.celery_task_id = None
        db.commit()

    return {"message": "Workflow untriggered successfully"}
