from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.job_assigner.models import Job, JobWorkflowHistory
from app.job_assigner.schemas import JobCreate, JobTransitionRequest
from app.models.employees import Employee


ALLOWED_TRANSITIONS: dict[str, dict[str, str]] = {
    "NEW": {"ASSIGN": "ASSIGNED"},
    "ASSIGNED": {
        "ACCEPT": "ACCEPTED",
        "REJECT": "REJECTED",
        "REASSIGN": "ASSIGNED",
    },
    "ACCEPTED": {"START": "IN_PROGRESS", "REASSIGN": "ASSIGNED"},
    "IN_PROGRESS": {"HOLD": "ON_HOLD", "COMPLETE": "COMPLETED"},
    "ON_HOLD": {"RESUME": "IN_PROGRESS"},
    "COMPLETED": {"CLOSE": "CLOSED", "REOPEN": "IN_PROGRESS"},
    "REJECTED": {"ASSIGN": "ASSIGNED"},
    "CLOSED": {"REOPEN": "IN_PROGRESS"},
}

MANAGER_ACTIONS = {"ASSIGN", "REASSIGN", "CLOSE", "REOPEN"}
ASSIGNEE_ACTIONS = {"ACCEPT", "REJECT", "START", "HOLD", "RESUME", "COMPLETE"}
MANAGER_POSITION_IDS = {1, 2, 5, 6, 7}


def is_manager(employee: Employee) -> bool:
    role_name = getattr(getattr(employee, "role", None), "role_name", "")
    return (
        employee.position_id in MANAGER_POSITION_IDS
        or employee.role_id in {1, 9, 99}
        or str(role_name).strip().lower() in {"admin", "manager", "gm"}
    )


def _require_manager(employee: Employee) -> None:
    if not is_manager(employee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a manager can perform this job action",
        )


def _require_active_assignee(db: Session, employee_code: str) -> None:
    assignee = db.scalar(
        select(Employee).where(
            Employee.employee_code == employee_code,
            Employee.is_active.is_(True),
        )
    )
    if assignee is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Assigned employee does not exist or is inactive",
        )


class JobWorkflowService:
    @staticmethod
    def list_jobs(
        db: Session,
        actor: Employee,
        workflow_status: str | None = None,
        assigned_to: str | None = None,
    ) -> list[Job]:
        stmt = select(Job)
        if not is_manager(actor):
            stmt = stmt.where(Job.assigned_to == actor.employee_code)
        if workflow_status:
            stmt = stmt.where(Job.workflow_status == workflow_status)
        if assigned_to:
            stmt = stmt.where(Job.assigned_to == assigned_to)
        return list(db.scalars(stmt.order_by(Job.updated_at.desc(), Job.id.desc())).all())

    @staticmethod
    def get_job(db: Session, job_id: int, actor: Employee) -> Job:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if not is_manager(actor) and job.assigned_to != actor.employee_code:
            raise HTTPException(status_code=403, detail="You cannot access this job")
        return job

    @staticmethod
    def create_job(db: Session, payload: JobCreate, actor: Employee) -> Job:
        _require_manager(actor)
        if payload.assigned_to:
            _require_active_assignee(db, payload.assigned_to)

        initial_status = "ASSIGNED" if payload.assigned_to else "NEW"
        job = Job(
            title=payload.title,
            description=payload.description,
            assigned_to=payload.assigned_to,
            assigned_by=actor.employee_code if payload.assigned_to else None,
            workflow_status=initial_status,
            priority=payload.priority,
            due_date=payload.due_date,
            created_by=actor.employee_code,
        )
        db.add(job)
        db.flush()
        db.add(
            JobWorkflowHistory(
                job_id=job.id,
                from_status=None,
                to_status=initial_status,
                action="ASSIGN" if payload.assigned_to else "CREATE",
                changed_by=actor.employee_code,
                assigned_to=payload.assigned_to,
            )
        )
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def transition_job(
        db: Session,
        job_id: int,
        payload: JobTransitionRequest,
        actor: Employee,
    ) -> Job:
        job = JobWorkflowService.get_job(db, job_id, actor)
        action = payload.action
        new_status = ALLOWED_TRANSITIONS.get(job.workflow_status, {}).get(action)
        if new_status is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Action {action} is not allowed from {job.workflow_status}",
            )

        if action in MANAGER_ACTIONS:
            _require_manager(actor)
        elif action in ASSIGNEE_ACTIONS and job.assigned_to != actor.employee_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the assigned employee can perform this action",
            )

        previous_assignee = job.assigned_to
        if action in {"ASSIGN", "REASSIGN"}:
            _require_active_assignee(db, payload.assigned_to or "")
            job.assigned_to = payload.assigned_to
            job.assigned_by = actor.employee_code

        previous_status = job.workflow_status
        job.workflow_status = new_status
        db.add(
            JobWorkflowHistory(
                job_id=job.id,
                from_status=previous_status,
                to_status=new_status,
                action=action,
                changed_by=actor.employee_code,
                assigned_from=previous_assignee,
                assigned_to=job.assigned_to,
                comment=payload.comment,
            )
        )
        db.commit()
        db.refresh(job)
        return job
