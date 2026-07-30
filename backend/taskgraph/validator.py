"""Task Graph Engine — Graph Validation.

Validates DAG structure and detects cycles.
"""

import logging
from taskgraph.models import TaskNode, TaskEdge, GraphValidation

logger = logging.getLogger("aic.taskgraph.validator")


class GraphValidator:
    """Validates task graphs."""

    @classmethod
    def validate(
        cls,
        nodes: list[TaskNode],
        edges: list[TaskEdge],
    ) -> GraphValidation:
        """Validate a task graph.

        Args:
            nodes: List of task nodes
            edges: List of dependency edges

        Returns:
            GraphValidation with is_valid, errors, warnings
        """
        errors = []
        warnings = []
        cycles = []

        # Check for empty graph
        if not nodes:
            errors.append("Graph has no nodes")
            return GraphValidation(is_valid=False, errors=errors)

        # Check for duplicate node IDs
        node_ids = [n.node_id for n in nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("Duplicate node IDs detected")

        # Check for invalid edge references
        valid_ids = set(node_ids)
        for edge in edges:
            if edge.from_node not in valid_ids:
                errors.append(f"Edge references invalid node: {edge.from_node}")
            if edge.to_node not in valid_ids:
                errors.append(f"Edge references invalid node: {edge.to_node}")

        # Detect cycles
        cycles = cls._detect_cycles(nodes, edges)
        if cycles:
            errors.append(f"Cycles detected: {len(cycles)}")
            for cycle in cycles:
                logger.warning(f"Cycle: {' -> '.join(cycle)}")

        # Check for isolated nodes (no edges)
        connected = set()
        for edge in edges:
            connected.add(edge.from_node)
            connected.add(edge.to_node)
        isolated = [n.node_id for n in nodes if n.node_id not in connected]
        if isolated and len(nodes) > 1:
            warnings.append(f"Isolated nodes: {len(isolated)}")

        # Check for nodes with too many dependencies
        for node in nodes:
            if len(node.dependencies) > 10:
                warnings.append(f"Node {node.node_id} has {len(node.dependencies)} dependencies")

        return GraphValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cycles_detected=cycles,
        )

    @classmethod
    def _detect_cycles(
        cls,
        nodes: list[TaskNode],
        edges: list[TaskEdge],
    ) -> list[list[str]]:
        """Detect cycles in the graph using DFS.

        Returns:
            List of cycles (each cycle is a list of node_ids)
        """
        # Build adjacency list (only for valid nodes)
        valid_ids = {n.node_id for n in nodes}
        adj: dict[str, list[str]] = {n.node_id: [] for n in nodes}
        for edge in edges:
            if edge.from_node in valid_ids and edge.to_node in valid_ids:
                adj[edge.from_node].append(edge.to_node)

        # DFS-based cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n.node_id: WHITE for n in nodes}
        parent: dict[str, str | None] = {n.node_id: None for n in nodes}
        cycles: list[list[str]] = []

        def dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            for neighbor in adj[node_id]:
                if color[neighbor] == GRAY:
                    # Found cycle - reconstruct
                    cycle = [neighbor, node_id]
                    current = parent[node_id]
                    while current is not None and current != neighbor:
                        cycle.append(current)
                        current = parent[current]
                    cycle.reverse()
                    cycles.append(cycle)
                    return True
                if color[neighbor] == WHITE:
                    parent[neighbor] = node_id
                    if dfs(neighbor):
                        return True
            color[node_id] = BLACK
            return False

        for node in nodes:
            if color[node.node_id] == WHITE:
                dfs(node.node_id)

        return cycles
