"""Advanced Observability — Diagnostics and performance correlation.

Provides:
- Performance diagnostics
- System health checks
- Resource monitoring
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("aic.observability.diagnostics")


@dataclass
class SystemHealth:
    """System health status."""
    status: str = "ok"  # ok, degraded, critical
    uptime_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_pct: float = 0.0
    active_connections: int = 0
    pending_tasks: int = 0
    issues: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class PerformanceMetric:
    """Performance metric."""
    name: str
    value: float
    unit: str
    threshold: float | None = None
    is_critical: bool = False
    timestamp: float = field(default_factory=time.time)


class DiagnosticsService:
    """Service for system diagnostics and performance monitoring."""

    def __init__(self):
        self._metrics: dict[str, list[PerformanceMetric]] = {}
        self._start_time = time.time()

    def get_system_health(self) -> SystemHealth:
        """Get current system health.

        Returns:
            SystemHealth status
        """
        import psutil

        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_pct = process.cpu_percent(interval=0.1)
        except Exception:
            memory_info = None
            cpu_pct = 0.0

        issues = []
        status = "ok"

        # Check memory
        if memory_info and memory_info.rss > 1024 * 1024 * 1024:  # > 1GB
            issues.append("High memory usage")
            status = "degraded"

        # Check CPU
        if cpu_pct > 80:
            issues.append("High CPU usage")
            status = "degraded"

        if cpu_pct > 95:
            status = "critical"

        return SystemHealth(
            status=status,
            uptime_seconds=time.time() - self._start_time,
            memory_usage_mb=memory_info.rss / (1024 * 1024) if memory_info else 0.0,
            cpu_usage_pct=cpu_pct,
            issues=issues,
        )

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str,
        threshold: float | None = None,
    ) -> PerformanceMetric:
        """Record a performance metric.

        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            threshold: Warning threshold

        Returns:
            PerformanceMetric
        """
        is_critical = threshold is not None and value > threshold

        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            threshold=threshold,
            is_critical=is_critical,
        )

        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(metric)

        # Keep only last 1000 metrics per name
        if len(self._metrics[name]) > 1000:
            self._metrics[name] = self._metrics[name][-1000:]

        if is_critical:
            logger.warning(f"Critical metric: {name}={value}{unit} (threshold={threshold})")

        return metric

    def get_metrics(
        self,
        name: str | None = None,
        limit: int = 100,
    ) -> list[PerformanceMetric]:
        """Get performance metrics.

        Args:
            name: Optional metric name filter
            limit: Maximum metrics to return

        Returns:
            List of metrics
        """
        if name:
            metrics = self._metrics.get(name, [])
            return metrics[-limit:]

        all_metrics = []
        for metrics in self._metrics.values():
            all_metrics.extend(metrics)
        all_metrics.sort(key=lambda m: m.timestamp, reverse=True)
        return all_metrics[:limit]

    def get_metric_summary(self) -> dict[str, Any]:
        """Get summary of all metrics.

        Returns:
            Metric summary
        """
        summary = {}
        for name, metrics in self._metrics.items():
            if not metrics:
                continue

            values = [m.value for m in metrics]
            summary[name] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "latest": values[-1],
                "critical_count": sum(1 for m in metrics if m.is_critical),
            }

        return summary

    def clear_metrics(self, name: str | None = None) -> None:
        """Clear metrics.

        Args:
            name: Optional metric name to clear
        """
        if name:
            self._metrics.pop(name, None)
        else:
            self._metrics.clear()


# Global diagnostics instance
_diagnostics = DiagnosticsService()


def get_diagnostics() -> DiagnosticsService:
    """Get the global diagnostics service."""
    return _diagnostics
