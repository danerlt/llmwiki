from app.worker import tasks
from app.worker.settings import WorkerSettings


def test_ingest_task_registered():
    assert tasks.ingest_source in WorkerSettings.functions
    assert callable(tasks.ingest_source)
