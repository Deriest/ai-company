# Testing Strategy

## Test Categories

### 1. Unit Tests (`tests/unit/`)
Tests isolated components with mocks:
- Service functions
- Utility helpers
- Schema validators
- Tool executor logic

```bash
pytest tests/unit/ -v --cov=backend
```

### 2. Integration Tests (`tests/integration/`)
Test API endpoints and workflows:
- REST API routes
- Database operations
- Agent orchestration flow
- Message persistence

```bash
pytest tests/integration/ -v
```

### 3. End-to-End Tests (`tests/e2e/`)
Full user flows:
- Chat session creation
- Real-time streaming
- Multi-agent task completion
- File uploads/downloads

```bash
npm run test:e2e
```

## Coverage Goals

| Category | Target | Current |
|----------|--------|---------|
| Backend Services | 80% | ~65% |
| API Routes | 75% | ~50% |
| Frontend Utils | 90% | ~85% |
| E2E Flows | 60% | ~40% |

## Key Test Scenarios

### Agent Workflow Validation
```python
async def test_multi_agent_flow():
    """Test orchestrator routing across multiple agents"""
    result = await dispatch_task("Search codebase", ["@explorer", "@fixer"])
    assert result.status == "completed"
    assert len(result.steps) >= 2
```

### Error Recovery Path
```python
async def test_exception_handling():
    """Verify proper error logging and recovery"""
    with pytest.raises(ToolError):
        await execute_tool("broken_operation")
    # Check logs contain structured error info
```

### Streaming Latency
```python
async def test_streaming_latency():
    """Verify SSE chunks arrive within threshold"""
    start = time.time()
    async for chunk in stream_response():
        process(chunk)
    elapsed = time.time() - start
    assert elapsed < 5.0  # 5 second SLA
```

## CI/CD Integration

### Automated Checks
- Run unit tests on every PR
- Integration tests on merge to main
- E2E tests nightly

### Performance Benchmarks
- Agent response time < 3 seconds (initial chunk)
- WebSocket latency < 200ms
- Database query time < 50ms (typical)

## Mocking Strategy

### External Dependencies
- HTTP clients → responses module
- Database → SQLite temp database
- File system → in-memory mock
- AI APIs → canned responses

### Agent Simulation
```python
class MockAgent:
    async def execute(self, task):
        return {"status": "success", "data": {}}
```

## Known Gaps

1. **Backend services** - Missing rollback scenario tests
2. **Streaming race conditions** - Partial coverage
3. **Input validation** - Weak Pydantic model tests
4. **Multi-user scenarios** - Not yet implemented
