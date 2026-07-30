"""AIC-ADE — Advanced Observability Tests."""

import pytest
from observability.diagnostics import (
    SystemHealth, PerformanceMetric, DiagnosticsService, get_diagnostics,
)


class TestSystemHealth:
    """Test SystemHealth dataclass."""

    def test_create_health(self):
        health = SystemHealth(
            status="ok",
            uptime_seconds=100.0,
            memory_usage_mb=512.0,
        )
        assert health.status == "ok"
        assert health.uptime_seconds == 100.0

    def test_health_defaults(self):
        health = SystemHealth()
        assert health.status == "ok"
        assert health.issues == []


class TestPerformanceMetric:
    """Test PerformanceMetric dataclass."""

    def test_create_metric(self):
        metric = PerformanceMetric(
            name="latency",
            value=100.0,
            unit="ms",
            threshold=500.0,
        )
        assert metric.name == "latency"
        assert metric.value == 100.0
        assert metric.is_critical is False

    def test_critical_metric(self):
        metric = PerformanceMetric(
            name="latency",
            value=600.0,
            unit="ms",
            threshold=500.0,
            is_critical=True,
        )
        assert metric.is_critical is True


class TestDiagnosticsService:
    """Test DiagnosticsService class."""

    def test_create_service(self):
        service = DiagnosticsService()
        assert service._start_time > 0

    def test_record_metric(self):
        service = DiagnosticsService()
        metric = service.record_metric("latency", 100.0, "ms", 500.0)
        assert metric.name == "latency"
        assert metric.value == 100.0

    def test_get_metrics(self):
        service = DiagnosticsService()
        service.record_metric("latency", 100.0, "ms")
        service.record_metric("latency", 200.0, "ms")
        metrics = service.get_metrics("latency")
        assert len(metrics) == 2

    def test_get_metrics_all(self):
        service = DiagnosticsService()
        service.record_metric("latency", 100.0, "ms")
        service.record_metric("cpu", 50.0, "%")
        metrics = service.get_metrics()
        assert len(metrics) == 2

    def test_get_metric_summary(self):
        service = DiagnosticsService()
        service.record_metric("latency", 100.0, "ms")
        service.record_metric("latency", 200.0, "ms")
        summary = service.get_metric_summary()
        assert "latency" in summary
        assert summary["latency"]["count"] == 2

    def test_clear_metrics(self):
        service = DiagnosticsService()
        service.record_metric("latency", 100.0, "ms")
        service.clear_metrics("latency")
        metrics = service.get_metrics("latency")
        assert len(metrics) == 0

    def test_clear_all_metrics(self):
        service = DiagnosticsService()
        service.record_metric("latency", 100.0, "ms")
        service.record_metric("cpu", 50.0, "%")
        service.clear_metrics()
        metrics = service.get_metrics()
        assert len(metrics) == 0


class TestGetDiagnostics:
    """Test get_diagnostics function."""

    def test_returns_service(self):
        service = get_diagnostics()
        assert isinstance(service, DiagnosticsService)
