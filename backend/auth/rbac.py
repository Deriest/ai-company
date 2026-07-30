"""AIC Platform — RBAC permission matrix."""
from storage.models import Role

# Permissions: "task.create", "task.cancel", "task.approve", "worker.control",
# "project.manage", "user.manage", "system.configure", "conversation.chat",
# "audit.read", "task.execute"

PERMISSIONS: dict[Role, set[str]] = {
    Role.OWNER: {
        "task.create", "task.cancel", "task.approve", "worker.control",
        "project.manage", "user.manage", "system.configure",
        "conversation.chat", "audit.read", "task.execute",
    },
    Role.ADMIN: {
        "task.create", "task.cancel", "task.approve", "worker.control",
        "project.manage", "user.manage", "system.configure",
        "conversation.chat", "audit.read", "task.execute",
    },
    Role.PM: {
        "task.create", "task.cancel", "task.approve", "project.manage",
        "conversation.chat", "audit.read",
    },
    Role.DEVELOPER: {
        "task.create", "conversation.chat",
    },
    Role.REVIEWER: {
        "task.approve", "audit.read", "conversation.chat",
    },
    Role.VIEWER: {
        "conversation.chat",
    },
    Role.WORKER: {
        "task.execute",
    },
}


def has_permission(role: Role, permission: str) -> bool:
    """Check whether a role grants a permission."""
    return permission in PERMISSIONS.get(role, set())
