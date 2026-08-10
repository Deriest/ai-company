"""Role-based authentication and authorization."""

from enum import Enum
from typing import List, Optional, Set
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import select
from backend.database.session import AsyncSessionLocal


class Role(str, Enum):
    """User role hierarchy (lowest to highest)."""
    USER = "user"         # Can view own resources, minimal actions
    EDITOR = "editor"     # Can create/edit/delete own content
    ADMIN = "admin"       # Full system access
    SUPERUSER = "superuser"  # Superadmin with all privileges


# Define resource type constants for ownership validation
RESOURCE_TYPES = {
    "task": "Task",
    "conversation": "Conversation", 
    "project": "Project",
    "workflow": "Workflow",
    "job": "Job",
    "memory": "Memory",
    "document": "Document",
    "plugin": "Plugin",
    "skill": "Skill",
    "message": "Message",
}


def require_roles(*allowed_roles: Role):
    """
    Authorization decorator requiring user has one of allowed roles.
    
    Usage:
        @router.post("/tasks", dependencies=[Depends(require_roles(Role.ADMIN))])
        
    Args:
        *allowed_roles: Variable list of allowed Role enum values
        
    Returns:
        Dependency function that checks user roles
    """
    async def role_checker(
        current_user: str = Depends(get_current_user),
        user_id: str = Depends(get_current_user_id)
    ) -> str:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # In production: fetch user's actual roles from database
        # For now, authenticated users are assumed to have at least USER role
        user_roles = await fetch_user_roles(user_id)
        
        # Check if user has any of the required roles
        for req_role in allowed_roles:
            if req_role in user_roles or req_role == Role.SUPERUSER:
                return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required role(s): {', '.join([r.value for r in allowed_roles])}",
        )
    
    return role_checker


async def get_current_user(request: Request) -> Optional[str]:
    """Extract current user from auth token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header[7:]
    
    # Decode token (using existing JWT logic)
    try:
        from auth.security import decode_access_token
        payload = decode_access_token(token)
        return payload.get("sub") if payload else None
    except Exception:
        return None


async def get_current_user_id(request: Request) -> Optional[str]:
    """Get current user ID from request (falls back to testing mode)."""
    user = await get_current_user(request)
    
    if user:
        return user
    
    # Test mode fallback - AIC_TESTING=1 allows requests without real auth
    if os.environ.get("AIC_TESTING") == "1":
        return "test-user-id"
    
    return None


async def fetch_user_roles(user_id: str) -> Set[Role]:
    """
    Fetch user's assigned roles from database.
    
    This should query UserRoles table or similar permission store.
    Implementation depends on your actual data model.
    """
    # Placeholder implementation - returns USER role for authenticated users
    # Replace with actual database query when UserRoles model exists
    return {Role.USER}


async def validate_resource_ownership(
    db: AsyncSession,
    resource_id: str,
    resource_type: str,
    user_id: str,
) -> bool:
    """
    Validate that user owns the specified resource.
    
    Args:
        db: Database session
        resource_id: ID of resource to validate
        resource_type: Type identifier (task, conversation, project, etc.)
        user_id: Current user's ID
        
    Returns:
        True if user owns resource
        
    Raises:
        HTTPException 403 if user doesn't own resource
    """
    import importlib
    models_module = importlib.import_module(f"backend.models.{resource_type.lower()}s" if resource_type != "message" else "storage.models")
    ResourceModel = getattr(models_module, resource_type.capitalize(), None)
    
    if not ResourceModel:
        # Fallback to common models
        if resource_type == "task":
            from storage.models import Task
            ResourceModel = Task
        elif resource_type == "conversation":
            from storage.models import Conversation
            ResourceModel = Conversation
        elif resource_type == "project":
            from storage.models import Project
            ResourceModel = Project
        elif resource_type == "workflow":
            from backend.models.schema import Workflow
            ResourceModel = Workflow
        elif resource_type == "job":
            from backend.models.jobs import Job
            ResourceModel = Job
        elif resource_type == "memory":
            from backend.models.memory import MemoryEntry
            ResourceModel = MemoryEntry
        elif resource_type == "document":
            from backend.models.rag import RAGDocument
            ResourceModel = RAGDocument
        else:
            return True  # Skip validation for unknown types
    
    try:
        query = select(ResourceModel).where(
            ResourceModel.id == resource_id,
            getattr(ResourceModel, 'created_by', None) == user_id or
            getattr(ResourceModel, 'user_id', None) == user_id
        )
        
        result = await db.execute(query)
        record = result.scalar_one_or_none()
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to modify this {resource_type}",
            )
        
        return True
    except AttributeError:
        # Model doesn't have created_by/user_id field
        # Skip ownership check for this resource type
        return True
