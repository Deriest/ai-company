"""AIC Platform — Context & Knowledge Intelligence (v2.3.7).

Provides persistent engineering memory and context to all engines.
"""

from context.config import context_config, ContextConfig
from context.models import ProjectContext, KnowledgeEntry, DecisionRecord

__all__ = [
    "context_config",
    "ContextConfig",
    "ProjectContext",
    "KnowledgeEntry",
    "DecisionRecord",
]
