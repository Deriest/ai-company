"""Task Graph Engine — Dependency Analysis.

Identifies dependencies between tasks and detects parallelism.
"""

import logging
from taskgraph.models import TaskNode, TaskEdge

logger = logging.getLogger("aic.taskgraph.dependency")


class DependencyAnalyzer:
    """Analyzes dependencies between tasks."""

    @classmethod
    def analyze_dependencies(cls, nodes: list[TaskNode]) -> list[TaskEdge]:
        """Analyze dependencies between nodes.

        Args:
            nodes: List of task nodes

        Returns:
            List of dependency edges
        """
        edges = []

        # Build dependency graph based on worker types and task types
        for i, node in enumerate(nodes):
            # Testing depends on implementation
            if node.task_type == "testing":
                for other in nodes:
                    if other.node_id != node.node_id and other.task_type == "coding":
                        edges.append(TaskEdge(
                            from_node=other.node_id,
                            to_node=node.node_id,
                            dependency_type="blocks",
                            required=True,
                        ))

            # Documentation depends on implementation
            if node.task_type == "documentation":
                for other in nodes:
                    if other.node_id != node.node_id and other.task_type == "coding":
                        edges.append(TaskEdge(
                            from_node=other.node_id,
                            to_node=node.node_id,
                            dependency_type="blocks",
                            required=True,
                        ))

            # Review depends on implementation
            if node.task_type == "review":
                for other in nodes:
                    if other.node_id != node.node_id and other.task_type == "coding":
                        edges.append(TaskEdge(
                            from_node=other.node_id,
                            to_node=node.node_id,
                            dependency_type="blocks",
                            required=True,
                        ))

        # Add explicit dependencies from node definitions
        for node in nodes:
            for dep_id in node.dependencies:
                if dep_id in [n.node_id for n in nodes]:
                    edges.append(TaskEdge(
                        from_node=dep_id,
                        to_node=node.node_id,
                        dependency_type="blocks",
                        required=True,
                    ))

        # Deduplicate edges
        edges = cls._deduplicate_edges(edges)

        return edges

    @classmethod
    def detect_parallelism(
        cls,
        nodes: list[TaskNode],
        edges: list[TaskEdge],
    ) -> list[list[str]]:
        """Detect tasks that can run in parallel.

        Returns:
            List of parallel groups (each group can run concurrently)
        """
        # Build adjacency list
        depends_on: dict[str, set[str]] = {n.node_id: set() for n in nodes}
        for edge in edges:
            depends_on[edge.to_node].add(edge.from_node)

        # Topological sort with parallelism detection
        visited = set()
        parallel_groups = []

        while len(visited) < len(nodes):
            # Find nodes with all dependencies satisfied
            ready = []
            for node in nodes:
                if node.node_id in visited:
                    continue
                deps = depends_on[node.node_id]
                if deps.issubset(visited):
                    ready.append(node.node_id)

            if not ready:
                # Deadlock detected
                logger.warning("Deadlock detected in dependency graph")
                break

            # Add ready nodes as a parallel group
            parallel_groups.append(ready)
            visited.update(ready)

        return parallel_groups

    @classmethod
    def find_critical_path(
        cls,
        nodes: list[TaskNode],
        edges: list[TaskEdge],
    ) -> list[str]:
        """Find the critical path through the graph.

        Returns:
            List of node_ids on the critical path
        """
        if not nodes:
            return []

        # Build adjacency list
        adj: dict[str, list[str]] = {n.node_id: [] for n in nodes}
        for edge in edges:
            adj[edge.from_node].append(edge.to_node)

        # Find longest path (critical path)
        # Use topological order
        in_degree: dict[str, int] = {n.node_id: 0 for n in nodes}
        for edge in edges:
            in_degree[edge.to_node] += 1

        # BFS to find longest path
        dist: dict[str, int] = {n.node_id: 0 for n in nodes}
        parent: dict[str, str | None] = {n.node_id: None for n in nodes}
        queue = [n.node_id for n in nodes if in_degree[n.node_id] == 0]

        while queue:
            node_id = queue.pop(0)
            for neighbor in adj[node_id]:
                if dist[neighbor] < dist[node_id] + 1:
                    dist[neighbor] = dist[node_id] + 1
                    parent[neighbor] = node_id
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Find node with maximum distance
        end_node = max(dist.items(), key=lambda x: x[1])[0]

        # Reconstruct path
        path = []
        current = end_node
        while current is not None:
            path.append(current)
            current = parent[current]

        path.reverse()
        return path

    @classmethod
    def _deduplicate_edges(cls, edges: list[TaskEdge]) -> list[TaskEdge]:
        """Remove duplicate edges."""
        seen = set()
        unique = []

        for edge in edges:
            key = (edge.from_node, edge.to_node)
            if key not in seen:
                seen.add(key)
                unique.append(edge)

        return unique
