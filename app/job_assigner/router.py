from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import active_employee_required
from app.core.db.engine import SessionLocal
from app.core.db.session import get_db
from app.job_assigner.schemas import (
    JobCreate,
    JobDetailResponse,
    JobResponse,
    JobTransitionRequest,
    WorkflowDefinitionResponse,
)
from app.job_assigner.websocket import job_connections
from app.job_assigner.models import Job
from app.job_assigner.workflow import ALLOWED_TRANSITIONS, JobWorkflowService, is_manager
from app.models.employees import Employee

router = APIRouter()


def _job_event(event_type: str, job) -> dict:
    return {
        "type": event_type,
        "job": JobResponse.model_validate(job).model_dump(mode="json"),
    }


@router.get("/workflow", response_model=WorkflowDefinitionResponse)
async def workflow_definition():
    return {"transitions": ALLOWED_TRANSITIONS}


@router.get("/", response_model=list[JobResponse])
@active_employee_required
async def list_jobs(
    request: Request,
    workflow_status: str | None = Query(default=None),
    assigned_to: str | None = Query(default=None, max_length=6),
    current_employee: Employee = None,
    db: Session = Depends(get_db),
):
    return JobWorkflowService.list_jobs(
        db, current_employee, workflow_status, assigned_to
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
@active_employee_required
async def get_job(
    job_id: int,
    request: Request,
    current_employee: Employee = None,
    db: Session = Depends(get_db),
):
    return JobWorkflowService.get_job(db, job_id, current_employee)


@router.post("/", response_model=JobResponse, status_code=201)
@active_employee_required
async def create_job(
    payload: JobCreate,
    request: Request,
    current_employee: Employee = None,
    db: Session = Depends(get_db),
):
    job = JobWorkflowService.create_job(db, payload, current_employee)
    await job_connections.broadcast(
        _job_event("job.created", job), assigned_to=job.assigned_to
    )
    return job


@router.post("/{job_id}/actions", response_model=JobResponse)
@active_employee_required
async def transition_job(
    job_id: int,
    payload: JobTransitionRequest,
    request: Request,
    current_employee: Employee = None,
    db: Session = Depends(get_db),
):
    existing_job = db.get(Job, job_id)
    previous_assignee = existing_job.assigned_to if existing_job else None
    job = JobWorkflowService.transition_job(db, job_id, payload, current_employee)
    await job_connections.broadcast(
        _job_event("job.updated", job), assigned_to=job.assigned_to
    )
    if previous_assignee and previous_assignee != job.assigned_to:
        await job_connections.broadcast(
            {"type": "job.removed", "job_id": job.id},
            recipients={previous_assignee},
        )
    return job


@router.websocket("/ws")
async def job_updates(websocket: WebSocket, employee_code: str = Query(...)):
    with SessionLocal() as db:
        employee = db.scalar(
            select(Employee).where(
                Employee.employee_code == employee_code,
                Employee.is_active.is_(True),
            )
        )
    if employee is None:
        await websocket.close(code=1008, reason="Invalid employee")
        return

    await job_connections.connect(websocket, employee_code, is_manager(employee))
    try:
        await websocket.send_json({"type": "connected"})
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await job_connections.disconnect(websocket)
    except Exception:
        await job_connections.disconnect(websocket)
        await websocket.close()
