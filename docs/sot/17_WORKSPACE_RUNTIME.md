# 17 — Workspace Runtime

**Subsystem:** File Tree, Git & Directory Management  
**Files:** `backend/workspace_manager.py`, `src/renderer/src/components/FileTree.tsx`  

---

## 1. Local Directory Integration

AIC-ADE interacts directly with local project directories on the host operating system:
- **Project Selection:** Users select local folders using the native OS directory picker (`window.aic.selectDirectory()`).
- **File System Operations:** File reading, directory listing, searching, and patching run via local system calls (`search_files`, `read_file`, `patch`).
- **Workspace Security:** Unrecognized or untrusted directories trigger a Workspace Trust verification dialog.
