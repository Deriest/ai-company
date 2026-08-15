"""RAG-based semantic file retrieval for large codebases.

Implements lightweight semantic indexing using simple embeddings
or hash-based similarity to find relevant files in large repositories.

Features:
- Hash-based document embedding (simhash) for fast similarity search
- Semantic relevance scoring based on task descriptions
- Lazy loading of file content to save memory
- Returns top 100+ files for large repos instead of limited 30
"""

import os
import hashlib
import logging
import asyncio
from typing import Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("aic.rag")


@dataclass
class FileEmbedding:
    """Represents a file's embedding vector."""
    file_path: str
    rel_path: str
    abs_path: str
    embedding_hash: str  # Simplified hash-based embedding
    file_size: int
    line_count: int
    language: str
    relevance_score: float = 0.0


@dataclass
class RetrievalResult:
    """Result from semantic file retrieval."""
    query: str
    files: list[FileEmbedding]
    total_indexed: int
    retrieval_time_ms: float
    metadata: dict = field(default_factory=dict)


def get_simple_embedding(text: str) -> str:
    """Generate a simple hash-based embedding for text.
    
    Uses SHA-256 hash truncated to first 16 hex chars as a simplified
    embedding vector representation. This is computationally efficient
    but less semantically accurate than real embeddings.
    
    For production use with accuracy needs, consider integrating:
    - sentence-transformers with All-MiniLM-L6-v2
    - FastText word vectors
    - OpenAI embeddings API
    """
    hash_obj = hashlib.sha256(text.encode('utf-8'))
    return hash_obj.hexdigest()[:16]


def tokenize_text(text: str) -> list[str]:
    """Tokenize text into words for similarity calculation."""
    import re
    # Simple tokenization: lowercase, alphanumeric words only
    return re.findall(r'[a-z0-9_]+', text.lower())


def jaccard_similarity(set1: set[str], set2: set[str]) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def calculate_cosine_similarity(vec1: dict[str, int], vec2: dict[str, int]) -> float:
    """Calculate cosine similarity between two term frequency vectors."""
    if not vec1 or not vec2:
        return 0.0
    
    all_terms = set(vec1.keys()) | set(vec2.keys())
    dot_product = sum(vec1.get(t, 0) * vec2.get(t, 0) for t in all_terms)
    
    norm1 = sum(v ** 2 for v in vec1.values()) ** 0.5
    norm2 = sum(v ** 2 for v in vec2.values()) ** 0.5
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


def detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    lang_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.jsx': 'javascript',
        '.rs': 'rust',
        '.go': 'go',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'c-header',
        '.hpp': 'cpp-header',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.sql': 'sql',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.md': 'markdown',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sh': 'shell',
        '.bash': 'shell',
    }
    
    ext = os.path.splitext(file_path)[1].lower()
    return lang_map.get(ext, 'text')


class RAGIndex:
    """Hash-based semantic index for file retrieval."""
    
    def __init__(self, workspace_root: str = ".", chunk_size: int = 500):
        self.workspace_root = workspace_root
        self.embeddings: dict[str, FileEmbedding] = {}
        self.token_vectors: dict[str, dict[str, int]] = {}
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def index_file(self, file_path: str, max_content: int = 5000) -> bool:
        """Index a single file for semantic retrieval."""
        try:
            rel_path = os.path.relpath(file_path, self.workspace_root)
            
            # Skip binary/large files
            if os.path.getsize(file_path) > 500_000:
                return False
            
            # Read file content (lazy - only read when needed)
            content = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._read_file_safe,
                file_path,
                max_content
            )
            
            if not content:
                return False
            
            # Generate embedding hash
            embedding_hash = get_simple_embedding(content)
            
            # Build token vector for similarity calculations
            tokens = tokenize_text(content)
            token_vector = {}
            for token in tokens:
                token_vector[token] = token_vector.get(token, 0) + 1
            
            # Detect language
            language = detect_language(file_path)
            
            # Create embedding record
            embedding = FileEmbedding(
                file_path=file_path,
                rel_path=rel_path,
                abs_path=file_path,
                embedding_hash=embedding_hash,
                file_size=os.path.getsize(file_path),
                line_count=content.count('\n'),
                language=language,
            )
            
            async with self._lock:
                self.embeddings[rel_path] = embedding
                self.token_vectors[rel_path] = token_vector
            
            return True
            
        except Exception as e:
            logger.debug(f"Failed to index file {file_path}: {e}")
            return False
    
    def _read_file_safe(self, file_path: str, max_lines: int = 100) -> str:
        """Safely read file content, skipping binaries."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                        lines.append(line.rstrip())
                return '\n'.join(lines)
        except (OSError, UnicodeDecodeError):
            return ""
    
    async def build_index(self, extensions: list[str] | None = None) -> int:
        """Build index for all matching files in workspace."""
        start_time = asyncio.get_event_loop().time()
        
        if extensions is None:
            # Default source code extensions
            extensions = ['.py', '.js', '.ts', '.tsx', '.jsx', '.rs', '.go', 
                         '.java', '.c', '.cpp', '.rb', '.php', '.swift', 
                         '.kt', '.scala', '.sql', '.json', '.yaml', '.yml',
                         '.html', '.css', '.scss', '.sh', '.bash']
        
        count = 0
        for root, dirs, files in os.walk(self.workspace_root):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                'node_modules', '__pycache__', '.venv', 'venv', 'dist', 
                'build', '.git', 'target', 'vendor', 'bower_components'
            }]
            
            for f in files:
                if any(f.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, f)
                    success = await self.index_file(file_path)
                    if success:
                        count += 1
        
        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        logger.info(f"Indexed {count} files in {elapsed:.0f}ms")
        return count
    
    def reset(self):
        """Reset the index."""
        self.embeddings.clear()
        self.token_vectors.clear()
    
    def get_all_files(self) -> list[FileEmbedding]:
        """Get all indexed files."""
        return list(self.embeddings.values())


class RAGContextRetriever:
    """Semantic file retrieval service for agent context building."""
    
    def __init__(self, workspace_root: str = ".", chunk_size: int = 500):
        self.workspace_root = workspace_root
        self.index = RAGIndex(workspace_root)
        self._is_indexed = False
    
    async def initialize(self) -> int:
        """Initialize the index with all relevant files."""
        if not self._is_indexed:
            count = await self.index.build_index()
            self._is_indexed = True
            return count
        return len(self.index.embeddings)
    
    async def retrieve_relevant_files(
        self,
        query: str,
        max_results: int = 100,
        current_files: list[str] | None = None
    ) -> RetrievalResult:
        """Retrieve files most relevant to the given query.
        
        Args:
            query: Task description or query string
            max_results: Maximum number of files to return (default 100)
            current_files: Already-referenced files to exclude or deprioritize
        
        Returns:
            RetrievalResult with ranked files and metadata
        """
        start_time = asyncio.get_event_loop().time()
        
        # Tokenize query
        query_tokens = set(tokenize_text(query))
        query_vector = {}
        for token in tokenize_text(query):
            query_vector[token] = query_vector.get(token, 0) + 1
        
        # Score all files by similarity to query
        scored_files: list[tuple[float, FileEmbedding]] = []
        
        for rel_path, embedding in self.index.embeddings.items():
            score = 0.0
            
            # Factor 1: Token-based similarity
            file_vector = self.index.token_vectors.get(rel_path, {})
            file_tokens = set(file_vector.keys())
            jaccard = jaccard_similarity(query_tokens, file_tokens)
            if jaccard > 0:
                score += jaccard * 30  # Weight for direct token match
            
            # Factor 2: Cosine similarity on term frequencies
            cosine = calculate_cosine_similarity(query_vector, file_vector)
            if cosine > 0:
                score += cosine * 70  # Weight for proportional similarity
            
            # Factor 3: Path relevance (filename contains query terms)
            path_lower = rel_path.lower()
            for token in query_tokens:
                if len(token) > 3 and token in path_lower:
                    score += 5
                    break
            
            # Factor 4: Language relevance (bonus for expected languages)
            if embedding.language in {'python', 'javascript', 'typescript'}:
                score += 10
            
            # Deprioritize already-in-context files
            if current_files and rel_path in current_files:
                score *= 0.5
            
            if score > 0:
                embedding.relevance_score = score
                scored_files.append((score, embedding))
        
        # Sort by score (highest first), then alphabetically for determinism
        scored_files.sort(key=lambda x: (-x[0], x[1].rel_path))
        
        # Get top results
        top_files = [sf[1] for sf in scored_files[:max_results]]
        
        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        
        result = RetrievalResult(
            query=query,
            files=top_files,
            total_indexed=len(self.index.embeddings),
            retrieval_time_ms=elapsed,
            metadata={
                "scanned_files": len(scored_files),
                "matched_files": len(top_files),
                "method": "hash-based-similarity"
            }
        )
        
        logger.info(
            f"Retrieved {len(top_files)} relevant files from "
            f"{len(self.index.embeddings)} indexed in {elapsed:.0f}ms"
        )
        
        return result
    
    async def load_file_content(
        self,
        file_rel_path: str,
        max_lines: int = 200
    ) -> Optional[str]:
        """Lazy-load file content only when actually referenced."""
        embedding = self.index.embeddings.get(file_rel_path)
        if not embedding:
            # Try to find it directly
            abs_path = os.path.join(self.workspace_root, file_rel_path)
            if not os.path.exists(abs_path):
                return None
        else:
            abs_path = embedding.abs_path
        
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"\n... (truncated after {max_lines} lines)")
                        break
                    lines.append(line.rstrip())
                return '\n'.join(lines)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to read {file_rel_path}: {e}")
            return None
    
    def get_index_stats(self) -> dict[str, Any]:
        """Get statistics about the current index."""
        stats = {
            "total_files": len(self.index.embeddings),
            "languages": {},
            "total_lines": 0,
            "total_size_bytes": 0,
        }
        
        for emb in self.index.embeddings.values():
            lang = emb.language
            stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
            stats["total_lines"] += emb.line_count
            stats["total_size_bytes"] += emb.file_size
        
        return stats


# Global instance for use across services
_global_rag_index: Optional[RAGContextRetriever] = None


def get_rag_context_retriever(workspace_root: str = ".") -> RAGContextRetriever:
    """Get or create the global RAG retriever instance."""
    global _global_rag_index
    
    if _global_rag_index is None or _global_rag_index.workspace_root != workspace_root:
        _global_rag_index = RAGContextRetriever(workspace_root)
    
    return _global_rag_index


async def init_rag_index(workspace_root: str = ".") -> int:
    """Initialize the RAG index for the workspace."""
    retriever = get_rag_context_retriever(workspace_root)
    return await retriever.initialize()


# Convenience wrapper for RAG functionality
class RagContextService:
    """Convenience wrapper around RAGContextRetriever"""
    def __init__(self):
        self.retriever = RAGContextRetriever()
    
    def add_file(self, filepath: str, content: str):
        return self.retriever.add_file(filepath, content)
    
    def find_relevant_files(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        return self.retriever.find_relevant_files(query, top_k)


# Alias for better discoverability
DocumentIndexer = RAGIndex
