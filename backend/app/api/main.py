from fastapi import APIRouter

from app.api.routes import (
    audit,
    contacts,
    dashboard,
    imports,
    jobs,
    login,
    operations,
    users,
)

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(imports.router)
api_router.include_router(jobs.router)
api_router.include_router(contacts.router)
api_router.include_router(audit.router)
api_router.include_router(operations.router)
