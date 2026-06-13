from app.worker.settings import WorkerSettings


def test_worker_settings_has_redis_and_functions():
    assert hasattr(WorkerSettings, "functions")
    assert isinstance(WorkerSettings.functions, list)
    assert WorkerSettings.redis_settings is not None
