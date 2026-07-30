"""AIC Platform — Engineering Discovery Engine (EDE).

Transforms natural language engineering requests into structured Engineering Briefs
before any planning or execution begins. This is the mandatory first stage of every
engineering workflow.

Version: 2.3.2
Status: Production-ready
"""

from discovery.config import discovery_config, DiscoveryConfig
from discovery.states import DiscoveryState, can_transition, is_terminal
from discovery.domains import DomainRegistry, Domain

__all__ = [
    "discovery_config",
    "DiscoveryConfig",
    "DiscoveryState",
    "can_transition",
    "is_terminal",
    "DomainRegistry",
    "Domain",
]
