"""Error visibility and debugging service for developers.

Formats errors with enhanced context, stack traces, and actionable suggestions.
Helps developers quickly understand and fix issues in agent execution.
"""

import os
import traceback
import logging
from datetime import datetime
from typing import Optional, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger("aic.errors")


@dataclass
class ErrorContext:
    """Rich context around an error."""
    error_type: str
    error_message: str
    traceback: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Source code context
    source_lines: List[str] = field(default_factory=list)
    surrounding_context: Optional[str] = None
    
    # Execution context
    workspace_root: Optional[str] = None
    task_description: Optional[str] = None
    agent_role: Optional[str] = None
    
    # Suggestions for fixes
    suggestions: List[str] = field(default_factory=list)


@dataclass
class FormattedError:
    """Human-readable formatted error for UI display."""
    id: str
    title: str
    severity: str  # "critical", "error", "warning", "info"
    message: str
    detailed_message: str
    stack_trace: str
    file_location: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    remediation_steps: Optional[List[str]] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def generate_error_id() -> str:
    """Generate unique error ID."""
    import uuid
    return f"ERR-{uuid.uuid4().hex[:8].upper()}"


def extract_error_context(
    exc: BaseException,
    workspace_root: str = ".",
    task_description: Optional[str] = None,
    agent_role: Optional[str] = None
) -> ErrorContext:
    """Extract rich context from an exception."""
    tb = traceback.extract_tb(exc.__traceback__)
    
    # Get last frame (where error occurred)
    if tb:
        last_frame = tb[-1]
        file_path = last_frame.filename
        line_number = last_frame.lineno
        function_name = last_frame.name
        
        # Read surrounding source lines
        source_lines: List[str] = []
        start_line = None
        end_line = None
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    start_line = max(0, line_number - 5)
                    end_line = min(len(all_lines), line_number + 5)
                    source_lines = [l.rstrip() for l in all_lines[start_line:end_line]]
            except Exception:
                logger.debug("error-viewer context read failed", exc_info=True)
        
        # Create surrounding context description
        surrounding = None
        if source_lines and start_line is not None:
            surrounding = "\n".join(
                f"{i+start_line+1}: {line}" 
                for i, line in enumerate(source_lines)
            )
        
        return ErrorContext(
            error_type=type(exc).__name__,
            error_message=str(exc),
            traceback=traceback.format_exc(),
            file_path=file_path,
            line_number=line_number,
            function_name=function_name,
            source_lines=source_lines,
            surrounding_context=surrounding,
            workspace_root=workspace_root,
            task_description=task_description,
            agent_role=agent_role,
        )
    
    return ErrorContext(
        error_type=type(exc).__name__,
        error_message=str(exc),
        traceback=traceback.format_exc(),
    )


def generate_fix_suggestions(error_ctx: ErrorContext) -> List[str]:
    """Generate actionable fix suggestions based on error type and context."""
    suggestions: List[str] = []
    error_lower = error_ctx.error_message.lower()
    
    # File system errors
    if 'no such file' in error_lower or 'file not found' in error_lower:
        suggestions.append(f"Ensure the file exists at: {error_ctx.file_path}")
        suggestions.append("Check if the workspace root is correctly configured")
    
    if 'permission denied' in error_lower:
        suggestions.append("Check file permissions on: " + (error_ctx.file_path or "target file"))
        suggestions.append("Run with appropriate user privileges")
    
    # Import errors
    elif 'no module named' in error_lower or 'import' in error_lower:
        suggestions.append("Install missing dependencies:")
        suggestions.append("  pip install <missing-module>")
        suggestions.append("Verify your virtual environment is activated")
    
    # Database errors
    elif 'database' in error_lower or 'sqlite' in error_lower or 'query' in error_lower:
        suggestions.append("Check database connection settings")
        suggestions.append("Verify SQLite file has read/write permissions")
        suggestions.append("Run migration if schema has changed")
    
    # Network errors
    elif 'connection' in error_lower or 'timeout' in error_lower or 'network' in error_lower:
        suggestions.append("Check network connectivity")
        suggestions.append("Verify proxy settings if behind firewall")
        suggestions.append("Increase timeout values if needed")
    
    # Syntax errors
    elif 'syntax error' in error_lower:
        suggestions.append("Review code syntax at line " + (str(error_ctx.line_number) if error_ctx.line_number else ""))
        suggestions.append("Check for missing colons, parentheses, or indentation")
    
    # Type errors
    elif 'type' in error_lower and ('not' in error_lower or 'expected' in error_lower):
        suggestions.append("Check variable types before operation")
        suggestions.append("Add type validation or casting")
    
    # Context-related errors (for agents)
    if error_ctx.task_description:
        suggestions.append(f"Task context: {error_ctx.task_description[:200]}...")
    
    if error_ctx.agent_role:
        suggestions.append(f"Agent role: {error_ctx.agent_role}")
    
    # Add general debugging tips
    if not suggestions:
        suggestions.extend([
            "Review the stack trace above for more details",
            "Enable debug logging for more verbose output",
            "Check logs at: /tmp/aic-data/logs/"
        ])
    
    return suggestions[:5]  # Top 5 most relevant suggestions


def format_error_for_ui(
    error_ctx: ErrorContext,
    include_stack_trace: bool = True
) -> FormattedError:
    """Format error for developer-friendly UI display."""
    
    # Determine severity
    severity = "warning"
    if 'critical' in error_ctx.error_message.lower() or 'fatal' in error_ctx.error_message.lower():
        severity = "critical"
    elif 'error' in error_ctx.error_type.lower() or 'exception' in error_ctx.error_message.lower():
        severity = "error"
    elif 'warn' in error_ctx.error_type.lower():
        severity = "warning"
    
    # Generate title
    title = f"{error_ctx.error_type} in {error_ctx.function_name or 'unknown'}"
    if error_ctx.file_path:
        rel_path = error_ctx.file_path
        if error_ctx.workspace_root:
            try:
                rel_path = os.path.relpath(error_ctx.file_path, error_ctx.workspace_root)
            except ValueError:
                pass
        title = f"{title} - {rel_path}"
    
    # Generate detailed message
    detailed_messages: List[str] = [f"{error_ctx.error_type}: {error_ctx.error_message}"]
    if error_ctx.surrounding_context:
        detailed_messages.append("\n\nSource context:")
        detailed_messages.append(error_ctx.surrounding_context)
    
    # Add remediation steps
    remediation: List[str] = []
    if error_ctx.file_path and error_ctx.line_number:
        remediation.append(f"1. Open file: {error_ctx.file_path}")
        remediation.append(f"2. Go to line {error_ctx.line_number}")
        remediation.append("3. Review the code context")
    
    if error_ctx.task_description:
        remediation.append(f"4. Check task context: {error_ctx.task_description[:100]}...")
    
    remediation.extend(error_ctx.suggestions)
    
    # Format stack trace
    stack_trace = error_ctx.traceback if include_stack_trace else f"{error_ctx.error_type}: {error_ctx.error_message}"
    
    return FormattedError(
        id=generate_error_id(),
        title=title,
        severity=severity,
        message=error_ctx.error_message,
        detailed_message="\n".join(detailed_messages),
        stack_trace=stack_trace,
        file_location=f"{error_ctx.file_path}:{error_ctx.line_number}" if error_ctx.file_path and error_ctx.line_number else None,
        suggestions=error_ctx.suggestions,
        remediation_steps=remediation,
    )


def analyze_error_pattern(errors: List[FormattedError]) -> dict[str, Any]:
    """Analyze multiple errors to identify patterns and recurring issues."""
    patterns: dict[str, Any] = {
        "total_errors": len(errors),
        "by_severity": {},
        "by_type": {},
        "by_file": {},
        "common_patterns": [],
    }
    
    for err in errors:
        # Count by severity
        patterns["by_severity"][err.severity] = patterns["by_severity"].get(err.severity, 0) + 1
        
        # Count by error type
        error_type = err.title.split()[0] if err.title else "Unknown"
        patterns["by_type"][error_type] = patterns["by_type"].get(error_type, 0) + 1
        
        # Group by file
        if err.file_location:
            file_part = err.file_location.split(':')[0]
            patterns["by_file"][file_part] = patterns["by_file"].get(file_part, 0) + 1
    
    # Identify common patterns
    for error_type, count in patterns["by_type"].items():
        if count >= 3:
            patterns["common_patterns"].append({
                "pattern": error_type,
                "occurrences": count,
                "recommendation": f"Address {error_type} systematically - appears {count} times"
            })
    
    return patterns


class ErrorHistory:
    """Track and manage error history for debugging."""
    
    def __init__(self, max_errors: int = 100):
        self.max_errors = max_errors
        self.errors: List[ErrorContext] = []
        self.formatted_errors: List[FormattedError] = []
    
    def record(self, exc: BaseException, **context_kwargs) -> FormattedError:
        """Record a new error with context."""
        error_ctx = extract_error_context(exc, **context_kwargs)
        error_ctx.suggestions = generate_fix_suggestions(error_ctx)
        
        self.errors.append(error_ctx)
        
        # Maintain max size
        if len(self.errors) > self.max_errors:
            self.errors = self.errors[-self.max_errors:]
        
        # Format for UI
        formatted = format_error_for_ui(error_ctx)
        self.formatted_errors.append(formatted)
        
        logger.warning(
            f"Error recorded: {formatted.id} - {formatted.title}",
            extra={
                "error_id": formatted.id,
                "severity": formatted.severity,
            }
        )
        
        return formatted
    
    def get_recent_errors(self, limit: int = 10) -> List[FormattedError]:
        """Get recent formatted errors."""
        return self.formatted_errors[-limit:]
    
    def get_analysis(self) -> dict[str, Any]:
        """Get pattern analysis of recorded errors."""
        return analyze_error_pattern(self.formatted_errors)
    
    def clear(self):
        """Clear all recorded errors."""
        self.errors.clear()
        self.formatted_errors.clear()


# Global error history instance
_global_error_history: Optional[ErrorHistory] = None


def get_error_history(max_errors: int = 100) -> ErrorHistory:
    """Get or create the global error history instance."""
    global _global_error_history
    
    if _global_error_history is None:
        _global_error_history = ErrorHistory(max_errors)
    
    return _global_error_history


def handle_agent_error(
    exc: BaseException,
    workspace_root: str = ".",
    task_description: Optional[str] = None,
    agent_role: Optional[str] = None
) -> FormattedError:
    """Handle an agent error and return formatted error for display."""
    history = get_error_history()
    return history.record(exc, 
                         workspace_root=workspace_root,
                         task_description=task_description,
                         agent_role=agent_role)

# Convenience class for error handling with auto-formatting
class ErrorViewer:
    '''High-level error viewing with suggestions'''
    
    def __init__(self):
        self.viewer = ErrorContextFormatter()
    
    def format_error(self, error_type: str, message: str, code_location: str = "") -> str:
        return self.viewer.format_error(error_type, message, code_location)
    
    def get_suggestion(self, error_type: str) -> Optional[str]:
        return self.viewer.get_suggestion(error_type)

class ErrorContextFormatter:
    """Format errors with context and suggestions"""
    
    def format_error(self, error_type: str, message: str, code_location: str = "") -> str:
        lines = [f"[{error_type}] {message}"]
        if code_location:
            lines.append(f"  at {code_location}")
        return "\n".join(lines)
    
    def get_suggestion(self, error_type: str) -> Optional[str]:
        suggestions = {
            "ValueError": "Check input values and data types",
            "KeyError": "Verify key exists in dictionary",
            "TypeError": "Ensure correct types are used",
            "FileNotFoundError": "Check file path exists",
            "ConnectionError": "Verify network connection is available",
        }
        return suggestions.get(error_type, "Review error message for details")

