from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    auth,
    conversations,
    documents,
    health,
    knowledge_bases,
    rag,
    users,
    workspace_templates,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(documents.router)
api_router.include_router(documents.workspace_router)
api_router.include_router(health.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(knowledge_bases.workspace_router)
api_router.include_router(rag.router)
api_router.include_router(rag.workspace_router)
api_router.include_router(users.router)
api_router.include_router(workspaces.router)
api_router.include_router(workspace_templates.router)
