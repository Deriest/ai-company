"""Final E2E test of AIC Platform."""
import httpx
import asyncio

BASE = "http://localhost:8000"

async def test():
    results = []
    async with httpx.AsyncClient(timeout=120) as c:
        # Login
        r = await c.post(f"{BASE}/api/auth/login", json={"username":"admin","password":"admin123"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        results.append(("LOGIN", "PASS", ""))

        # 1. Health
        r = await c.get(f"{BASE}/health")
        results.append(("HEALTH", "PASS" if r.status_code == 200 else "FAIL", r.json().get("llm_configured")))

        # 2. Providers
        r = await c.get(f"{BASE}/api/llm/providers", headers=h)
        providers = r.json()
        results.append(("PROVIDERS", "PASS" if providers else "FAIL", f"{len(providers)} providers"))

        # 3. Model fetch
        pid = providers[0]["id"]
        r = await c.get(f"{BASE}/api/llm/providers/{pid}/models", headers=h)
        mc = r.json().get("count", 0)
        results.append(("MODEL_FETCH", "PASS" if mc > 0 else "WARN", f"{mc} models"))

        # 4. Chat hello (should use LLM)
        r = await c.post(f"{BASE}/api/conversations", json={"title":"Final E2E"}, headers=h)
        cid = r.json()["id"]
        r = await c.post(f"{BASE}/api/conversations/{cid}/messages", json={"content":"hello"}, headers=h)
        d = r.json()
        intent = d.get("intent", "?")
        resp = d.get("response", "")[:80]
        results.append(("CHAT_HELLO", "PASS" if r.status_code == 200 else "FAIL", f"intent={intent} | {resp}"))

        # 5. Task creation
        r = await c.post(f"{BASE}/api/conversations/{cid}/messages",
            json={"content":"Create task to build a calculator app for developers with React UI and unit tests deployed on local server."}, headers=h)
        d = r.json()
        intent = d.get("intent", "?")
        resp = d.get("response", "")[:100]
        is_task_created = "task" in resp.lower() or "TASK-" in resp or bool(d.get("meta", {}).get("task_id"))
        results.append(("CHAT_TASK", "PASS" if is_task_created else "FAIL", f"intent={intent} | {resp}"))

        # 6. Dashboard
        r = await c.get(f"{BASE}/api/dashboard/overview", headers=h)
        ov = r.json()
        results.append(("DASHBOARD", "PASS" if r.status_code == 200 else "FAIL",
            f"tasks={ov['tasks']['total']} workers={ov['workers']['total']}"))

        # 7. Tasks list
        r = await c.get(f"{BASE}/api/tasks", headers=h)
        tasks = r.json()
        results.append(("TASKS_LIST", "PASS" if r.status_code == 200 else "FAIL", f"{len(tasks)} tasks"))

        # 8. Workers list
        r = await c.get(f"{BASE}/api/workers", headers=h)
        workers = r.json()
        results.append(("WORKERS_LIST", "PASS" if r.status_code == 200 else "FAIL", f"{len(workers)} workers"))

        # 9. Approvals
        r = await c.get(f"{BASE}/api/approvals", headers=h)
        results.append(("APPROVALS", "PASS" if r.status_code == 200 else "FAIL", f"{len(r.json())} pending"))

        # 10. Users
        r = await c.get(f"{BASE}/api/users", headers=h)
        results.append(("USERS", "PASS" if r.status_code == 200 else "FAIL", f"{len(r.json())} users"))

        # 11. Dispatch a task
        created = [t for t in tasks if t["status"] == "created"]
        if created:
            tid = created[0]["id"]
            r = await c.post(f"{BASE}/api/tasks/{tid}/dispatch", headers=h)
            results.append(("DISPATCH", "PASS" if r.status_code == 200 else "FAIL", r.json().get("message", "")))
            # Wait for background execution
            await asyncio.sleep(10)
            r = await c.get(f"{BASE}/api/tasks/{tid}", headers=h)
            t = r.json()
            results.append(("POST_DISPATCH", "PASS" if t["status"] != "created" else "WARN",
                f"status={t['status']} progress={t['progress']}"))
        else:
            results.append(("DISPATCH", "SKIP", "no created tasks"))

    # Print results
    print("\n" + "=" * 60)
    print("AIC PLATFORM — FINAL E2E REPORT")
    print("=" * 60)
    passed = 0
    for name, status, detail in results:
        symbol = "PASS" if status == "PASS" else ("!!" if status == "WARN" else "FAIL")
        print(f"  [{symbol:4}] {name:20} {detail}")
        if status == "PASS":
            passed += 1
    print(f"\n  Result: {passed}/{len(results)} passed")
    print("=" * 60)

asyncio.run(test())
