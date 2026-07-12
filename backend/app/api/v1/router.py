from fastapi import APIRouter

from backend.app.api.v1.endpoints import auth, documents, health, knowledge_bases, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(health.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(users.router)
