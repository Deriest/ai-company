import re
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.ai_runtime import Artifact

class ArtifactService:
    @staticmethod
    async def extract_and_store(db: AsyncSession, conversation_id: str, message_id: str, content: str) -> list[Artifact]:
        artifacts = []
        
        # 1. Extract markdown code blocks with titles or language
        # pattern matches ```lang title="..." or simple ```lang\ncode\n```
        pattern = re.compile(r"```([a-zA-Z0-9_-]+)?(?:\s+title=[\"']([^\"']+)[\"'])?\n(.*?)```", re.DOTALL)
        matches = pattern.findall(content)
        
        for idx, match in enumerate(matches):
            lang = match[0] or "text"
            title = match[1] or f"Snippet {idx+1} ({lang})"
            code_content = match[2].strip()
            if not code_content:
                continue
                
            art_type = "code"
            mime_type = "text/plain"
            if lang in ["html", "svg"]:
                art_type = "html"
                mime_type = "text/html"
            elif lang == "json":
                art_type = "json"
                mime_type = "application/json"
            elif lang in ["diff", "patch"]:
                art_type = "diff"
            elif lang in ["sh", "bash", "console", "terminal"]:
                art_type = "terminal"
                
            art = Artifact(
                conversation_id=conversation_id,
                message_id=message_id,
                type=art_type,
                title=title,
                content=code_content,
                language=lang,
                mime_type=mime_type
            )
            db.add(art)
            artifacts.append(art)
            
        if artifacts:
            await db.commit()
            for a in artifacts:
                await db.refresh(a)
                
        return artifacts

artifact_service = ArtifactService()
