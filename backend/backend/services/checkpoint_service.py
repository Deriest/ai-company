"""Checkpoint service for saving/resuming agent execution state."""
import logging
import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from backend.api.schemas.plan_schemas import TaskPlan, PlanCheckpoint


logger = logging.getLogger("aic.checkpoint_service")


class CheckpointService:
    """Save and restore agent execution checkpoints for pause/resume capability."""
    
    def __init__(self, checkpoint_dir: str = ".aic/checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def create_checkpoint(
        self,
        task_plan: TaskPlan,
        messages_history: List[Dict[str, Any]],
        iteration_count: int,
        tool_results_summary: Optional[List[Dict[str, Any]]] = None,
    ) -> PlanCheckpoint:
        """Create a new checkpoint with current agent state."""
        checkpoint_id = f"ckpt_{uuid.uuid4().hex[:8]}"
        
        checkpoint = PlanCheckpoint(
            checkpoint_id=checkpoint_id,
            task_plan=task_plan,
            messages_history=messages_history,
            iteration_count=iteration_count,
            saved_at=datetime.now().isoformat(),
            tool_results_summary=tool_results_summary or [],
        )
        
        # Save to disk
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        
        return checkpoint
    
    def load_checkpoint(self, checkpoint_id: str) -> Optional[PlanCheckpoint]:
        """Load a checkpoint by ID."""
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        if not checkpoint_path.exists():
            return None
        
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return PlanCheckpoint.from_dict(data)
    
    def get_latest_checkpoint(self, task_id: str) -> Optional[PlanCheckpoint]:
        """Get the most recent checkpoint for a task."""
        checkpoints = []
        for ckpt_file in self.checkpoint_dir.glob("*.json"):
            try:
                with open(ckpt_file, "r") as f:
                    data = json.load(f)
                if data.get("task_id") == task_id or task_id in ckpt_file.name:
                    checkpoints.append((ckpt_file, PlanCheckpoint.from_dict(data)))
            except (OSError, IOError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load checkpoint {ckpt_file.name}: {e}")
                continue
        
        if not checkpoints:
            return None
        
        # Sort by saved_at timestamp
        checkpoints.sort(key=lambda x: x[1].saved_at, reverse=True)
        return checkpoints[0][1]
    
    def list_checkpoints(self) -> List[PlanCheckpoint]:
        """List all available checkpoints."""
        checkpoints = []
        for ckpt_file in self.checkpoint_dir.glob("*.json"):
            try:
                with open(ckpt_file, "r") as f:
                    data = json.load(f)
                    checkpoints.append(PlanCheckpoint.from_dict(data))
            except (OSError, IOError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load checkpoint {ckpt_file.name}: {e}")
                continue
        return sorted(checkpoints, key=lambda c: c.saved_at, reverse=True)
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by ID."""
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            return True
        return False
    
    def cleanup_old_checkpoints(self, keep_last: int = 5):
        """Keep only the N most recent checkpoints."""
        checkpoints = self.list_checkpoints()
        if len(checkpoints) <= keep_last:
            return
        
        for ckpt in checkpoints[keep_last:]:
            checkpoint_path = self.checkpoint_dir / f"{ckpt.checkpoint_id}.json"
            if checkpoint_path.exists():
                checkpoint_path.unlink()
