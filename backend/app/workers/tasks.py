import logging
from app.workers.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def generate_trip_plan(self, trip_id: int):
    """Async Celery task to generate a full trip plan."""
    db = SessionLocal()
    try:
        from app.services.generation_service import generate_plan_sync
        generate_plan_sync(trip_id, db)
        # generate_plan_sync records the failure and returns so it can be used
        # by synchronous callers. A Celery task must raise here so transient
        # provider errors (for example Gemini 503) are retried.
        from app.models.trip import Trip, TripStatus
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if trip and trip.status == TripStatus.FAILED:
            raise RuntimeError(f"Trip {trip_id} generation failed; retrying")
        logger.info(f"Celery: Trip {trip_id} generated successfully")
        return {"status": "created", "trip_id": trip_id}
    except Exception as exc:
        logger.error(f"Celery: Trip {trip_id} generation failed: {exc}")
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            from app.models.trip import Trip, TripStatus
            trip = db.query(Trip).filter(Trip.id == trip_id).first()
            if trip:
                trip.status = TripStatus.FAILED
                db.commit()
            return {"status": "failed", "trip_id": trip_id}
    finally:
        db.close()
