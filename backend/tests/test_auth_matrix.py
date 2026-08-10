"""Authentication Matrix Test

Automatically discovers ALL backend routes and verifies they require authentication.
Uses httpx ASGITransport to simulate requests without Authorization header.

Requirements:
- Public endpoints (allowlist): GET /health, POST/GET /auth/login, GET /auth/me, GET /docs → expect 200
- All other endpoints: expect 401 (Unauthorized) or 405 (Method Not Allowed)
- Skip OPTIONS preflight checks
- Track pass/fail counts and list failing endpoints
- Save results to JSON for CI integration
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

# Setup environment before imports — AIC_TESTING=1 is needed for the localhost
# middleware to allow the httpx ASGITransport "test" host.  We will DISABLE
# the auth fail-open after import (see below) so that authentication is
# properly enforced during this matrix test.
os.environ['AIC_TESTING'] = '1'
os.environ['AIC_IDENTITY_USERNAME'] = 'testuser'
os.environ['AIC_IDENTITY_PASSWORD'] = 'testpass'

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.main import app  # noqa: E402
import backend.api.dependencies as _auth_deps  # noqa: E402

# ── CRITICAL: Disable the auth fail-open ──────────────────────────
# backend.api.dependencies reads AIC_TESTING at import time and sets
# _AIC_TESTING = True, which makes get_optional_current_user return
# "test-user" for missing tokens.  We patch it to False AFTER import so
# that the localhost middleware still allows the test client (it read the
# env var at import time and already added "test"/"testserver" to its
# allowlists) while authentication is properly enforced (missing token →
# None → require_current_user raises 401).
_auth_deps._AIC_TESTING = False


# ── Path-parameter substitution ──────────────────────────────────
# Replace {param} placeholders with a valid value so the route matches
# and the auth dependency runs before any resource lookup.
_PATH_PARAM_RE = re.compile(r'\{[^}]+\}')


def _substitute_path_params(path: str) -> str:
    """Replace OpenAPI path params like {id} with a concrete value."""
    return _PATH_PARAM_RE.sub('1', path)


class AuthenticationMatrixTest:
    """Test that all protected endpoints return 401 without authentication."""

    # PUBLIC ENDPOINTS ALLOWLIST — these should return 200 even without auth
    # GET endpoints
    _PUBLIC_GET_PATHS = frozenset({
        "/health",
        "/docs",
        "/redoc",
        "/readiness",
        "/metrics",
        "/openapi.json",
        "/auth/login",      # GET form / info
        "/auth/me",         # token validation endpoint
    })
    # POST endpoints
    _PUBLIC_POST_PATHS = frozenset({
        "/auth/login",      # login endpoint
    })

    def __init__(self):
        self.results: dict[str, Any] = {
            "total_routes": 0,
            "options_skipped": 0,
            "tested": 0,
            "passed": 0,
            "failed": [],
            "by_path": {},
            "protected_passed": {},
            "public_checked": [],
            "summary": "",
        }

    def _is_public_endpoint(self, method: str, path: str) -> bool:
        """Check if endpoint is publicly accessible (allowlisted)."""
        path_stripped = path.rstrip('/').lower()

        if method == "GET":
            return path_stripped in self._PUBLIC_GET_PATHS
        elif method == "POST":
            return path_stripped in self._PUBLIC_POST_PATHS
        return False

    def _get_expected_status(self, method: str, path: str) -> set[int]:
        """Get expected status codes for a route."""
        if self._is_public_endpoint(method, path):
            # Public endpoints should return 200
            return {200}
        else:
            # Protected endpoints should return:
            #   401 Unauthorized — properly guarded with auth dependency
            #   405 Method Not Allowed — method not supported on this path
            return {401, 405}

    def discover_routes_from_openapi(self) -> list[dict[str, str]]:
        """
        Parse OpenAPI schema to get all API routes with methods.
        This captures routes from all included routers automatically.
        """
        routes = []

        try:
            openapi_schema = app.openapi()
        except Exception as e:
            print(f"Warning: Could not generate OpenAPI schema: {e}")
            return []

        paths = openapi_schema.get("paths", {})

        for path, methods in paths.items():
            for method in methods:
                # method is lowercase: get, post, put, patch, delete
                if method in ("get", "post", "put", "patch", "delete"):
                    routes.append({
                        "path": path,
                        "method": method.upper(),
                    })

        return routes

    async def make_unauthenticated_request(
        self, method: str, base_url: str, path: str
    ) -> tuple[int, Any]:
        """
        Make request WITHOUT Authorization header.
        Returns (status_code, response_body).
        """
        concrete_path = _substitute_path_params(path)
        full_url = f"{base_url}{concrete_path}"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            follow_redirects=False,
            timeout=10.0,
        ) as client:
            try:
                response = await client.request(
                    method=method,
                    url=full_url,
                    headers={"Accept": "application/json"},
                )
                # Try to parse JSON response
                try:
                    body: Any = response.json()
                except Exception:
                    body = response.text[:200] if response.text else None
                return response.status_code, body
            except Exception as e:
                # Network or connection error
                return -1, str(e)

    async def test_all_routes(self) -> dict[str, Any]:
        """
        Run authentication test against all discovered routes.
        Groups by path + method for clear reporting.
        """
        routes = self.discover_routes_from_openapi()
        self.results["total_routes"] = len(routes)

        base_url = "http://test"
        failures: list[dict] = []
        passed_count = 0
        options_skipped = 0

        async def test_route(route_info: dict) -> None:
            nonlocal passed_count, options_skipped

            method = route_info["method"]
            path = route_info["path"]

            # Skip OPTIONS preflight checks (they return 200/307 normally)
            if method == "OPTIONS":
                options_skipped += 1
                return

            self.results["tested"] += 1

            expected_statuses = self._get_expected_status(method, path)
            status_code, body = await self.make_unauthenticated_request(
                method, base_url, path
            )

            if status_code in expected_statuses:
                passed_count += 1
                # Track successful protection
                if path not in self.results["protected_passed"]:
                    self.results["protected_passed"][path] = []
                self.results["protected_passed"][path].append({
                    "method": method,
                    "status_code": status_code,
                    "is_public": self._is_public_endpoint(method, path),
                })
                # Track public endpoint checks
                if self._is_public_endpoint(method, path):
                    self.results["public_checked"].append({
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                    })
            else:
                # FAILING: endpoint doesn't return expected status
                failure = {
                    "path": path,
                    "method": method,
                    "actual_status_code": status_code,
                    "expected_status_codes": sorted(expected_statuses),
                    "response_detail": (
                        body.get("detail")
                        if isinstance(body, dict) and "detail" in body
                        else (str(body)[:100] if body else None)
                    ),
                }
                failures.append(failure)

                # Track by path
                if path not in self.results["by_path"]:
                    self.results["by_path"][path] = []
                self.results["by_path"][path].append(failure)

        # Run all tests concurrently
        tasks = [test_route(r) for r in routes]
        await asyncio.gather(*tasks)

        self.results["passed"] = passed_count
        self.results["failed"] = failures
        self.results["options_skipped"] = options_skipped

        total_tested = self.results["tested"]
        self.results["summary"] = f"PASS: {passed_count}/{total_tested}"

        return self.results

    def print_summary(self, results: dict) -> int:
        """Print formatted summary of test results."""

        total = results["total_routes"]
        tested = results["tested"]
        passed = results["passed"]
        failed = len(results["failed"])
        options_skipped = results["options_skipped"]

        print("\n" + "=" * 80)
        print("AUTHENTICATION MATRIX TEST RESULTS")
        print("=" * 80)

        print(f"\n  SUMMARY")
        print(f"   Total routes discovered from OpenAPI: {total}")
        print(f"   OPTIONS skipped (preflight):          {options_skipped}")
        print(f"   Routes tested:                        {tested}")
        print(f"   PASSED (properly protected/public):    {passed}")
        print(f"   FAILED (unprotected):                  {failed}")

        print(f"\n{'=' * 80}")
        print(f"  PASS: {passed}/{tested}")
        print(f"{'=' * 80}")

        # Show public endpoints that were checked
        public_checked = results.get("public_checked", [])
        if public_checked:
            print(f"\n  PUBLIC ENDPOINTS CHECKED (expect 200): {len(public_checked)}")
            for pub in sorted(public_checked, key=lambda x: x["path"]):
                status_icon = "OK" if pub["status_code"] == 200 else "!!"
                print(f"      [{status_icon}] {pub['method']:6s} {pub['path']:40s} → {pub['status_code']}")

        # Show failing endpoints grouped by path
        if failed > 0:
            print("\n" + "-" * 80)
            print("  SECURITY ALERT: UNPROTECTED ENDPOINTS FOUND")
            print("-" * 80)

            # Group failures by path
            failures_by_path: dict[str, list] = {}
            for failure in results["failed"]:
                path = failure["path"]
                if path not in failures_by_path:
                    failures_by_path[path] = []
                failures_by_path[path].append(failure)

            for path in sorted(failures_by_path.keys()):
                failures = failures_by_path[path]
                details = []
                for f in failures:
                    detail_str = f"{f['method']} (got {f['actual_status_code']}, expected {f['expected_status_codes']})"
                    if f.get("response_detail"):
                        detail_str += f" — {str(f['response_detail'])[:60]}"
                    details.append(detail_str)

                print(f"\n  {path}")
                for d in details:
                    print(f"      {d}")
        else:
            print("\n  ALL PROTECTED ENDPOINTS RETURN 401 UNAUTHORIZED!")

        print("\n" + "=" * 80)

        return failed

    def save_results_json(self, output_path: str = "test_results.json") -> None:
        """Save test results to JSON for CI integration."""
        output_file = Path(output_path)

        tested = self.results["tested"]
        passed = self.results["passed"]

        clean_results = {
            "timestamp": datetime.now().isoformat(),
            "app_title": app.title,
            "total_routes": self.results["total_routes"],
            "options_skipped": self.results["options_skipped"],
            "routes_tested": tested,
            "passed": passed,
            "failed": len(self.results["failed"]),
            "pass_rate": round(passed / tested * 100, 2) if tested > 0 else 0,
            "public_endpoints_checked": self.results.get("public_checked", []),
            "failures": self.results["failed"],
            "summary_line": self.results["summary"],
        }

        with open(output_file, "w") as f:
            json.dump(clean_results, f, indent=2)

        print(f"\n  Results saved to: {output_file.absolute()}")


async def run_authentication_matrix():
    """Main entry point to run the authentication matrix test."""
    print("\n  Running Authentication Matrix Test...")
    print(f"  Testing app: {app.title}")
    print(f"  Auth fail-open: DISABLED (proper 401 enforcement)")

    test_instance = AuthenticationMatrixTest()

    # Run the test suite
    results = await test_instance.test_all_routes()

    # Print summary
    failed_count = test_instance.print_summary(results)

    # Save JSON results
    test_instance.save_results_json()

    return failed_count


def test_authentication_matrix():
    """Pytest wrapper for the authentication matrix test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        failed_count = loop.run_until_complete(run_authentication_matrix())

        if failed_count > 0:
            pytest.fail(
                f"Found {failed_count} unprotected endpoints. "
                f"See summary above for details."
            )
        else:
            print("\n  AUTHENTICATION MATRIX: ALL TESTS PASSED!")
    finally:
        loop.close()


if __name__ == "__main__":
    import time

    start_time = time.time()
    failed_count = asyncio.run(run_authentication_matrix())
    elapsed = time.time() - start_time

    print(f"\n  Test completed in {elapsed:.2f}s")

    sys.exit(1 if failed_count > 0 else 0)
