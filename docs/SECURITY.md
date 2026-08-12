# Security Guide

## Current Security Posture

### v2.6.6 Hardening (Latest)

✅ **Bare `except:` clauses fixed** - Replaced with specific exception handling + logging:
- `checkpoint_service.py` - OSError/IOError/JSONDecodeError handlers
- `error_recovery.py` - psutil.NoSuchProcess/AccesDenied + shutdown signal preservation
- `tool_executor.py` - PermissionError/UnicodeDecodeError handlers

✅ **Database transaction safety verified** - Proper rollback patterns throughout

✅ **Input validation** - Pydantic models for API payloads

## Security Architecture

### Runtime Isolation
- Agent execution in isolated Python environments
- File system access controlled via permissions
- Network calls sandboxed

### Authentication
- Local file-based profile storage
- No cloud authentication required
- Token generation for local sessions

### Data Protection
- SQLite database encryption (at rest)
- Attachment store with path validation
- No external data transmission by default

## Known Limitations

⚠️ **No multi-user support** - Single-user desktop application only  
⚠️ **Code signing** - Test builds without signing certificate  
⚠️ **Network isolation** - MCP tools can make network calls if configured

## Best Practices

### For Developers
1. Always use specific exceptions, never bare `except:`
2. Validate all user inputs with Pydantic schemas
3. Log errors with full stack traces for debugging
4. Use transactions for database operations

### For Users
1. Review tool permissions before execution
2. Don't grant MCP tools unrestricted network access
3. Keep dependencies updated
4. Report security issues via GitHub issues

## Incident Response

If you discover a security vulnerability:
1. Document findings with reproduction steps
2. Create GitHub issue (mark as "Security")
3. Do not disclose publicly until fixed
4. Provide patch if possible

## Compliance Notes

- No third-party data collection
- No telemetry by default
- Open source codebase for auditability
- GPL-compatible licensing
