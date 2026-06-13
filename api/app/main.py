from fastapi import FastAPI

from app.controllers import auth, health, kb, org


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Wiki API")
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(org.router, prefix="/api")
    app.include_router(kb.router, prefix="/api")
    return app


app = create_app()
