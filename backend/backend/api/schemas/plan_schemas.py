"""Task plan schemas for multi-phase agent execution."""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Subtask:
    """A single subtask within a larger plan."""
    id: str
    title: str
    description: str
    status: str = "pending"  # pending, in_progress, done, blocked
    dependencies: List[str] = field(default_factory=list)  # IDs of required subtasks
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subtask":
        return cls(**data)


@dataclass
class TaskPlan:
    """Structured task decomposition plan."""
    task_id: str
    description: str
    subtasks: List[Subtask] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    current_subtask_index: int = 0
    is_complete: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_subtask_index": self.current_subtask_index,
            "is_complete": self.is_complete,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPlan":
        subtasks = [Subtask.from_dict(s) for s in data.get("subtasks", [])]
        return cls(
            task_id=data["task_id"],
            description=data["description"],
            subtasks=subtasks,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            current_subtask_index=data.get("current_subtask_index", 0),
            is_complete=data.get("is_complete", False),
        )

    def mark_subtask_done(self, subtask_id: str) -> bool:
        """Mark a subtask as complete."""
        for i, subtask in enumerate(self.subtasks):
            if subtask.id == subtask_id:
                self.subtasks[i].status = "done"
                self.subtasks[i].completed_at = datetime.now().isoformat()
                # Move to next available subtask
                self._advance_subtask_index()
                return True
        return False

    def _advance_subtask_index(self):
        """Find first non-done subtask."""
        for i, subtask in enumerate(self.subtasks):
            if subtask.status != "done":
                self.current_subtask_index = i
                break
        else:
            self.is_complete = True
            self.current_subtask_index = len(self.subtasks) - 1

    def get_current_subtask(self) -> Optional[Subtask]:
        """Get currently active subtask."""
        if self.current_subtask_index < len(self.subtasks):
            return self.subtasks[self.current_subtask_index]
        return None


@dataclass
class PlanCheckpoint:
    """Saved state for resuming agent execution."""
    checkpoint_id: str
    task_plan: TaskPlan
    messages_history: List[Dict[str, Any]]
    iteration_count: int
    saved_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_results_summary: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_plan": self.task_plan.to_dict(),
            "messages_history": self.messages_history,
            "iteration_count": self.iteration_count,
            "saved_at": self.saved_at,
            "tool_results_summary": self.tool_results_summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanCheckpoint":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            task_plan=TaskPlan.from_dict(data["task_plan"]),
            messages_history=data["messages_history"],
            iteration_count=data["iteration_count"],
            saved_at=data.get("saved_at", ""),
            tool_results_summary=data.get("tool_results_summary", []),
        )
