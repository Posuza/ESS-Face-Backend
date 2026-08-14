"""Create only the Job Assigner tables registered in SQLAlchemy metadata."""

from app.core.db.engine import Base, engine
from app.job_assigner.models import Job, JobWorkflowHistory
from app.models import employees  # noqa: F401 - registers the referenced table


if __name__ == "__main__":
    Base.metadata.create_all(
        bind=engine,
        tables=[Job.__table__, JobWorkflowHistory.__table__],
        checkfirst=True,
    )
    print("Job Assigner tables are ready")
