"""
MO Report PDF Export Worker

หนึ่ง process ทำงานสอง job โดยแยกเป็น class เพื่อให้เห็นชัดเจนว่า
แต่ละ class รับผิดชอบอะไร และมีตัวแปร / ฟังก์ชันของตัวเอง:
- PdfExportJobRunner  -> สร้างไฟล์ PDF ตามคิว export (loop)
- SweepJobRunner      -> ลบไฟล์ PDF ที่หมดอายุ (loop ตาม interval)
- run_worker / main   -> ตัวรันหลัก เริ่ม thread ของทั้งสอง job ใน process เดียว
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.models.mo_report_export_job import MoReportExportJob
from app.services.pdf.mo_report_pdf_builder import (
    MoReportPdfBuilder,
    MoReportPdfBuildError,
    MoReportPdfCancelledError,
    MoReportPdfNoDataError,
)
from app.services.pdf.mo_report_pdf_export import MoReportPdfExport

logger = logging.getLogger("mo_report_export_worker")


@dataclass(frozen=True)
class ClaimedMoExportJob:
    mo_report_export_job_id: int
    report_type: str
    filters_json: dict


# ==========================================================================
# Generic helpers shared by both jobs (not specific to PDF or sweep logic)
# ==========================================================================

@contextmanager
def db_session() -> Iterator[Session]:
    session_generator = get_db()
    db = next(session_generator)
    try:
        yield db
    finally:
        session_generator.close()


def now_local() -> datetime:
    return datetime.now()


def env_required_positive_float(name: str) -> float:
    raw_value = os.getenv(name)
    if not raw_value:
        raise RuntimeError(f"Required environment variable {name} is not set")

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be a number greater than 0"
        ) from exc

    if value <= 0:
        raise RuntimeError(f"Environment variable {name} must be greater than 0")
    return value


def env_required_positive_int(name: str) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        raise RuntimeError(f"Required environment variable {name} is not set")

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be an integer greater than 0"
        ) from exc

    if value <= 0:
        raise RuntimeError(f"Environment variable {name} must be greater than 0")
    return value


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


def remove_file_if_exists(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        logger.warning("Could not remove file: %s", path, exc_info=True)


# ==========================================================================
# Job 1: PDF export job — constants / variables / functions เฉพาะ PDF
# ==========================================================================

class PdfExportJobRunner:
    """สร้างไฟล์ PDF ตามคิว MO report export."""

    logger = logging.getLogger("mo_report_export_worker.pdf_job")

    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    POLL_SECONDS_ENV = "MO_REPORT_EXPORT_WORKER_POLL_SECONDS"
    RETENTION_MINUTES_ENV = "MO_REPORT_EXPORT_RETENTION_MINUTES"

    def __init__(
        self,
        *,
        poll_seconds: float,
        retention_minutes: int,
        stop_event: threading.Event,
    ) -> None:
        self.poll_seconds = poll_seconds
        self.retention_minutes = retention_minutes
        self.stop_event = stop_event

    # -- public entry points -------------------------------------------------

    def run(self) -> None:
        self.logger.info(
            "MO PDF job started. poll_seconds=%s retention_minutes=%s",
            self.poll_seconds,
            self.retention_minutes,
        )

        while not self.stop_event.is_set():
            try:
                processed = self.process_one()
            except Exception:
                self.logger.exception("MO PDF job loop error")
                processed = False

            if not processed:
                self.stop_event.wait(self.poll_seconds)

        self.logger.info("MO PDF job stopped.")

    def run_once(self) -> None:
        self.process_one()

    def process_one(self) -> bool:
        claimed_job = self._claim_next_job()
        if claimed_job is None:
            return False

        self.logger.info(
            "MO PDF job claimed: job_id=%s type=%s",
            claimed_job.mo_report_export_job_id,
            claimed_job.report_type,
        )
        self._process_claimed_job(claimed_job)
        return True

    # -- export root / file naming -------------------------------------------

    def _get_export_root(self) -> Path:
        export_root = MoReportPdfExport._get_export_root()
        export_root.mkdir(parents=True, exist_ok=True)
        return export_root.resolve()

    def _build_relative_output_path(
        self,
        mo_report_export_job_id: int,
        report_type: str,
    ) -> Path:
        generated_at = now_local()
        safe_report_type = (
            MoReportPdfBuilder.REPORT_TYPE_SUMMARY
            if report_type == MoReportPdfBuilder.REPORT_TYPE_SUMMARY
            else MoReportPdfBuilder.REPORT_TYPE_DIVISION
        )
        filename = (
            f"{safe_report_type}_job_{mo_report_export_job_id}_"
            f"{generated_at:%Y%m%d_%H%M%S}.pdf"
        )
        return (
            Path("mo_reports")
            / safe_report_type
            / f"{generated_at:%Y}"
            / f"{generated_at:%m}"
            / filename
        )

    # -- DB: claim / progress / finalize -------------------------------------

    def _claim_next_job(self) -> ClaimedMoExportJob | None:
        with db_session() as db:
            with db.begin():
                statement = (
                    select(MoReportExportJob)
                    .where(
                        MoReportExportJob.report_type.in_(
                            [
                                MoReportPdfBuilder.REPORT_TYPE_SUMMARY,
                                MoReportPdfBuilder.REPORT_TYPE_DIVISION,
                            ]
                        ),
                        MoReportExportJob.job_status == self.STATUS_QUEUED,
                        MoReportExportJob.mark_flag.is_(False),
                    )
                    .order_by(
                        MoReportExportJob.created_at.asc(),
                        MoReportExportJob.mo_report_export_job_id.asc(),
                    )
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )

                export_job = db.scalar(statement)
                if export_job is None:
                    return None

                export_job.job_status = self.STATUS_PROCESSING
                export_job.progress_current = 0
                export_job.progress_total = 0
                export_job.file_relative_path = None
                export_job.download_filename = None
                export_job.file_size_bytes = None
                export_job.error_message = None
                export_job.started_at = now_local()
                export_job.completed_at = None
                export_job.expires_at = None

                db.flush()

                return ClaimedMoExportJob(
                    mo_report_export_job_id=export_job.mo_report_export_job_id,
                    report_type=export_job.report_type,
                    filters_json=dict(export_job.filters_json or {}),
                )

    def _is_job_cancelled(self, mo_report_export_job_id: int) -> bool:
        with db_session() as db:
            result = db.execute(
                select(
                    MoReportExportJob.job_status,
                    MoReportExportJob.mark_flag,
                ).where(
                    MoReportExportJob.mo_report_export_job_id
                    == mo_report_export_job_id,
                )
            ).one_or_none()

            if result is None:
                return True

            job_status, mark_flag = result
            return bool(mark_flag) or job_status == self.STATUS_CANCELLED

    def _update_progress(
        self,
        mo_report_export_job_id: int,
        *,
        current: int,
        total: int,
    ) -> None:
        safe_current = max(0, int(current))
        safe_total = max(0, int(total))
        if safe_total > 0:
            safe_current = min(safe_current, safe_total)

        with db_session() as db:
            statement = (
                update(MoReportExportJob)
                .where(
                    MoReportExportJob.mo_report_export_job_id
                    == mo_report_export_job_id,
                    MoReportExportJob.job_status == self.STATUS_PROCESSING,
                    MoReportExportJob.mark_flag.is_(False),
                )
                .values(
                    progress_current=safe_current,
                    progress_total=safe_total,
                )
            )
            db.execute(statement)
            db.commit()

    def _finish_completed_job(
        self,
        claimed_job: ClaimedMoExportJob,
        *,
        output_file: Path,
        relative_output_path: Path,
        download_filename: str,
        file_size_bytes: int,
    ) -> bool:
        with db_session() as db:
            with db.begin():
                export_job = db.scalar(
                    select(MoReportExportJob)
                    .where(
                        MoReportExportJob.mo_report_export_job_id
                        == claimed_job.mo_report_export_job_id,
                    )
                    .with_for_update()
                )

                if (
                    export_job is None
                    or export_job.mark_flag
                    or export_job.job_status == self.STATUS_CANCELLED
                ):
                    remove_file_if_exists(output_file)
                    return False

                if export_job.job_status != self.STATUS_PROCESSING:
                    remove_file_if_exists(output_file)
                    self.logger.warning(
                        "Job %s changed status during finalize: %s",
                        claimed_job.mo_report_export_job_id,
                        export_job.job_status,
                    )
                    return False

                export_job.job_status = self.STATUS_COMPLETED
                if export_job.progress_total > 0:
                    export_job.progress_current = export_job.progress_total
                else:
                    export_job.progress_current = 0
                export_job.file_relative_path = relative_output_path.as_posix()
                export_job.download_filename = download_filename
                export_job.file_size_bytes = max(0, int(file_size_bytes))
                export_job.error_message = None
                export_job.completed_at = now_local()
                export_job.expires_at = now_local() + timedelta(
                    minutes=self.retention_minutes
                )

        return True

    def _mark_job_failed(
        self,
        claimed_job: ClaimedMoExportJob,
        *,
        safe_error_message: str,
    ) -> None:
        with db_session() as db:
            with db.begin():
                export_job = db.scalar(
                    select(MoReportExportJob)
                    .where(
                        MoReportExportJob.mo_report_export_job_id
                        == claimed_job.mo_report_export_job_id,
                    )
                    .with_for_update()
                )

                if export_job is None or export_job.mark_flag:
                    return

                if export_job.job_status == self.STATUS_CANCELLED:
                    return

                export_job.job_status = self.STATUS_FAILED
                export_job.error_message = safe_error_message[:2000]
                export_job.completed_at = now_local()

    # -- build orchestration --------------------------------------------------

    def _process_claimed_job(self, claimed_job: ClaimedMoExportJob) -> None:
        relative_output_path = self._build_relative_output_path(
            claimed_job.mo_report_export_job_id,
            claimed_job.report_type,
        )
        output_file = self._get_export_root() / relative_output_path

        try:
            with db_session() as db:
                build_result = MoReportPdfBuilder.build_mo_report_pdf(
                    db=db,
                    filters=claimed_job.filters_json,
                    output_path=output_file,
                    report_type=claimed_job.report_type,
                    progress_callback=lambda current, total: self._update_progress(
                        claimed_job.mo_report_export_job_id,
                        current=current,
                        total=total,
                    ),
                    is_cancelled=lambda: self._is_job_cancelled(
                        claimed_job.mo_report_export_job_id,
                    ),
                )

            finalized = self._finish_completed_job(
                claimed_job,
                output_file=output_file,
                relative_output_path=relative_output_path,
                download_filename=build_result.download_filename,
                file_size_bytes=build_result.file_size_bytes,
            )

            if finalized:
                self.logger.info(
                    "MO PDF completed: job_id=%s rows=%s size=%s bytes",
                    claimed_job.mo_report_export_job_id,
                    build_result.report_row_count,
                    build_result.file_size_bytes,
                )

        except MoReportPdfCancelledError:
            remove_file_if_exists(output_file)
            self.logger.info(
                "MO PDF cancelled: job_id=%s",
                claimed_job.mo_report_export_job_id,
            )

        except MoReportPdfNoDataError as exc:
            remove_file_if_exists(output_file)
            self.logger.info(
                "No MO report data: job_id=%s",
                claimed_job.mo_report_export_job_id,
            )
            self._mark_job_failed(claimed_job, safe_error_message=str(exc))

        except MoReportPdfBuildError:
            remove_file_if_exists(output_file)
            self.logger.exception(
                "MO PDF build failed: job_id=%s",
                claimed_job.mo_report_export_job_id,
            )
            self._mark_job_failed(
                claimed_job,
                safe_error_message="ไม่สามารถสร้างไฟล์ PDF รายงาน MO ได้ กรุณาลองใหม่อีกครั้ง",
            )

        except Exception:
            remove_file_if_exists(output_file)
            self.logger.exception(
                "Unexpected MO PDF worker error: job_id=%s",
                claimed_job.mo_report_export_job_id,
            )
            self._mark_job_failed(
                claimed_job,
                safe_error_message="เกิดข้อผิดพลาดระหว่างสร้างไฟล์รายงาน MO",
            )


# ==========================================================================
# Job 2: sweep job — constants / variables / functions เฉพาะ sweep
# ==========================================================================

class SweepJobRunner:
    """ลบไฟล์ PDF ที่หมดอายุ (expires_at ผ่านไปแล้ว)."""

    logger = logging.getLogger("mo_report_export_worker.sweep_job")

    SWEEP_INTERVAL_MINUTES_ENV = "MO_REPORT_EXPORT_SWEEP_INTERVAL_MINUTES"

    def __init__(
        self,
        *,
        sweep_interval_minutes: float,
        stop_event: threading.Event,
    ) -> None:
        self.sweep_interval_minutes = sweep_interval_minutes
        self.stop_event = stop_event

    def run(self) -> None:
        self.logger.info(
            "MO sweep job started. sweep_interval_minutes=%s",
            self.sweep_interval_minutes,
        )

        while not self.stop_event.is_set():
            self.sweep_once()
            self.stop_event.wait(self.sweep_interval_minutes * 60)

        self.logger.info("MO sweep job stopped.")

    def run_once(self) -> None:
        self.sweep_once()

    def sweep_once(self) -> None:
        try:
            with db_session() as db:
                removed = MoReportPdfExport.sweep_expired_files(db=db)
            if removed:
                self.logger.info(
                    "Sweep removed %s expired PDF file(s)",
                    removed,
                )
        except Exception:
            self.logger.exception("MO sweep job error")


# ==========================================================================
# Main runner: เริ่มทั้งสอง job เป็น thread ใน process เดียว
# ==========================================================================

def run_worker(
    *,
    poll_seconds: float,
    retention_minutes: int,
    sweep_interval_minutes: float,
    stop_event: threading.Event,
) -> None:
    logger.info(
        "MO report export worker starting. poll_seconds=%s retention_minutes=%s "
        "sweep_interval_minutes=%s",
        poll_seconds,
        retention_minutes,
        sweep_interval_minutes,
    )

    pdf_job = PdfExportJobRunner(
        poll_seconds=poll_seconds,
        retention_minutes=retention_minutes,
        stop_event=stop_event,
    )
    sweep_job = SweepJobRunner(
        sweep_interval_minutes=sweep_interval_minutes,
        stop_event=stop_event,
    )

    pdf_thread = threading.Thread(
        target=pdf_job.run,
        name="mo-pdf-job",
        daemon=True,
    )
    sweep_thread = threading.Thread(
        target=sweep_job.run,
        name="mo-sweep-job",
        daemon=True,
    )

    pdf_thread.start()
    sweep_thread.start()

    try:
        # รอจนกว่าจะสั่งหยุด หรือ pdf thread ตาย
        while pdf_thread.is_alive() and not stop_event.is_set():
            pdf_thread.join(timeout=0.5)

        # ถ้า pdf thread ตายเองโดยไม่ได้สั่งหยุด → ออกจาก process
        # เพื่อให้ service manager รีสตาร์ท (ไม่งั้น PDF จะเงียบไปโดยไม่มีใครรู้)
        if not stop_event.is_set() and not pdf_thread.is_alive():
            logger.error("MO PDF job thread died unexpectedly. Exiting worker for restart.")
            stop_event.set()
    finally:
        stop_event.set()
        sweep_thread.join()
        pdf_thread.join()

    logger.info("MO report export worker stopped.")


# ==========================================================================
# CLI
# ==========================================================================

def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GUTS-ESS MO Report PDF Export Worker",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued PDF job, then stop (no sweep thread).",
    )

    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=env_required_positive_float(PdfExportJobRunner.POLL_SECONDS_ENV),
        help=f"Sleep time when no job is available (from {PdfExportJobRunner.POLL_SECONDS_ENV}).",
    )

    parser.add_argument(
        "--retention-minutes",
        type=int,
        default=env_required_positive_int(PdfExportJobRunner.RETENTION_MINUTES_ENV),
        help=f"PDF file retention in minutes after completion (from {PdfExportJobRunner.RETENTION_MINUTES_ENV}).",
    )

    parser.add_argument(
        "--sweep-minutes",
        type=float,
        default=env_required_positive_float(SweepJobRunner.SWEEP_INTERVAL_MINUTES_ENV),
        help=(
            f"Delete expired PDF files every N minutes "
            f"(from {SweepJobRunner.SWEEP_INTERVAL_MINUTES_ENV})."
        ),
    )

    parser.add_argument(
        "--log-level",
        default=os.getenv("MO_REPORT_EXPORT_WORKER_LOG_LEVEL", "INFO"),
        help="DEBUG, INFO, WARNING, ERROR",
    )

    return parser


def main() -> int:
    args = build_argument_parser().parse_args()

    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds must be greater than 0")
    if args.retention_minutes <= 0:
        raise SystemExit("--retention-minutes must be greater than 0")
    if args.sweep_minutes <= 0:
        raise SystemExit("--sweep-minutes must be greater than 0")

    configure_logging(args.log_level)

    if args.once:
        PdfExportJobRunner(
            poll_seconds=args.poll_seconds,
            retention_minutes=args.retention_minutes,
            stop_event=threading.Event(),
        ).run_once()
        return 0

    stop_event = threading.Event()

    def request_stop(signum: int, _frame: object) -> None:
        logger.info("Received signal %s. Requesting worker shutdown.", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    run_worker(
        poll_seconds=args.poll_seconds,
        retention_minutes=args.retention_minutes,
        sweep_interval_minutes=args.sweep_minutes,
        stop_event=stop_event,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
