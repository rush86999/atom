"""SemanticBugClusterer: LLM embedding-based bug clustering service."""
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.embedding_service import EmbeddingService
from core.lancedb_handler import LanceDBHandler
from core.llm_service import LLMService
from tests.bug_discovery.models.bug_report import BugReport
from tests.bug_discovery.ai_enhanced.models.bug_cluster import BugCluster


class SemanticBugClusterer:
    """
    Cluster bugs by semantic similarity using LLM embeddings.

    Generates embeddings for bug error messages, stack traces, and code
    contexts, then clusters similar bugs using LanceDB vector search.

    Example:
        clusterer = SemanticBugClusterer()

        # Cluster bugs from discovery run
        clusters = await clusterer.cluster_bugs(
            bugs=bug_reports,
            similarity_threshold=0.75,
            min_cluster_size=2
        )

        for cluster in clusters:
            print(f"Cluster {cluster.cluster_id}: {cluster.size} bugs")
            print(f"  Theme: {cluster.theme}")
    """

    # Embedding table name
    BUG_EMBEDDINGS_TABLE = "bug_embeddings"

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        lancedb_handler: Optional[LanceDBHandler] = None,
        llm_service: Optional[LLMService] = None
    ):
        """
        Initialize SemanticBugClusterer.

        Args:
            embedding_service: EmbeddingService for generating embeddings
            lancedb_handler: LanceDBHandler for vector storage
            llm_service: LLMService for cluster theme generation
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.lancedb_handler = lancedb_handler or LanceDBHandler(
            db_path="./data/bug_clusters",
            workspace_id="default"
        )
        self.llm_service = llm_service or LLMService(tenant_id="default")

        # Create bug embeddings table
        self._ensure_embeddings_table()

    def _ensure_embeddings_table(self):
        """Create LanceDB table for bug embeddings if not exists."""
        try:
            # Check if handler has DB initialized
            if self.lancedb_handler.db is None:
                self.lancedb_handler._initialize_db()

            existing_tables = self.lancedb_handler.db.table_names()
            if self.BUG_EMBEDDINGS_TABLE not in existing_tables:
                # Create table with schema
                import pyarrow as pa

                schema = pa.schema([
                    pa.field("id", pa.string()),
                    pa.field("bug_id", pa.string()),
                    pa.field("error_message", pa.string()),
                    pa.field("stack_trace", pa.string()),
                    pa.field("vector", pa.list_(pa.float32())),  # Embedding vector
                    pa.field("metadata", pa.string()),  # JSON string
                    pa.field("timestamp", pa.string()),
                ])

                self.lancedb_handler.db.create_table(
                    self.BUG_EMBEDDINGS_TABLE,
                    schema=schema
                )
        except Exception as e:
            print(f"[SemanticBugClusterer] Warning: Could not create bug_embeddings table: {e}")

    async def cluster_bugs(
        self,
        bugs: List[BugReport],
        similarity_threshold: float = 0.75,
        min_cluster_size: int = 2
    ) -> List[BugCluster]:
        """
        Cluster bugs by semantic similarity.

        Args:
            bugs: List of BugReport objects from discovery methods
            similarity_threshold: Minimum similarity for clustering (cosine similarity, 0.0-1.0)
            min_cluster_size: Minimum bugs per cluster

        Returns:
            List of BugCluster objects with themes and statistics
        """
        if len(bugs) < min_cluster_size:
            return []  # Not enough bugs to cluster

        # Generate embeddings for all bugs
        embeddings = await self._generate_bug_embeddings(bugs)

        # Store embeddings in LanceDB
        await self._store_embeddings(embeddings)

        # Cluster using vector similarity search
        clusters = await self._cluster_by_similarity(
            bugs=bugs,
            embeddings=embeddings,
            similarity_threshold=similarity_threshold,
            min_cluster_size=min_cluster_size
        )

        # Generate cluster themes using LLM
        for cluster in clusters:
            cluster.theme = await self._generate_cluster_theme(cluster.bug_ids, bugs)

        # Calculate cluster statistics
        for cluster in clusters:
            cluster.severity_distribution = self._calculate_severity_distribution(cluster.bug_ids, bugs)
            cluster.platform_distribution = self._calculate_platform_distribution(cluster.bug_ids, bugs)

        return clusters

    async def _generate_bug_embeddings(
        self,
        bugs: List[BugReport]
    ) -> List[Dict[str, Any]]:
        """Generate embeddings for bug error messages."""
        embeddings = []

        for bug in bugs:
            # Clean and combine error message + stack trace for embedding
            text_to_embed = self._clean_text_for_embedding(bug.error_message)
            if bug.stack_trace:
                text_to_embed += " " + self._clean_text_for_embedding(bug.stack_trace)

            # Generate embedding
            try:
                embedding = await self.embedding_service.generate_embedding(text_to_embed)
            except Exception as e:
                print(f"[SemanticBugClusterer] Warning: Failed to generate embedding: {e}")
                # Use zero vector as fallback
                embedding = [0.0] * 384  # FastEmbed default dimension

            embeddings.append({
                "bug_id": bug.test_name,  # Use test_name as ID
                "error_message": bug.error_message,
                "stack_trace": bug.stack_trace or "",
                "embedding": embedding,
                "metadata": bug.metadata,
                "timestamp": str(bug.timestamp) if hasattr(bug, 'timestamp') and bug.timestamp else str(datetime.utcnow()),
                "bug": bug  # Store reference
            })

        return embeddings

    def _clean_text_for_embedding(self, text: str) -> str:
        """
        Remove non-semantic content from error messages.

        - Remove file paths
        - Remove line numbers
        - Remove timestamps
        - Keep error keywords, function names, error types
        """
        # Remove file paths (Unix and Windows)
        text = re.sub(r'[/\\][a-zA-Z0-9_/\-\.\\]+[/\\]', '', text)
        text = re.sub(r'[a-zA-Z]:\\[a-zA-Z0-9_\\\-\.\\]+', '', text)

        # Remove line numbers
        text = re.sub(r':\d+', '', text)

        # Remove timestamps (ISO format and similar)
        text = re.sub(r'\d{4}-\d{2}-\d{2}T?\d{2}:\d{2}:\d{2}.*?\d', '', text)
        text = re.sub(r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}', '', text)

        # Remove memory addresses (0x...)
        text = re.sub(r'0x[0-9a-fA-F]+', '', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    async def _store_embeddings(self, embeddings: List[Dict[str, Any]]) -> bool:
        """Store embeddings in LanceDB."""
        try:
            if self.lancedb_handler.db is None:
                return False

            table = self.lancedb_handler.db.open_table(self.BUG_EMBEDDINGS_TABLE)

            # Convert to list of dicts for LanceDB
            data = []
            for emb in embeddings:
                record = {
                    "id": emb["bug_id"],
                    "bug_id": emb["bug_id"],
                    "error_message": emb["error_message"],
                    "stack_trace": emb["stack_trace"],
                    "vector": emb["embedding"],  # LanceDB uses "vector" column
                    "metadata": json.dumps(emb["metadata"]),
                    "timestamp": emb["timestamp"]
                }
                data.append(record)

            # Insert into LanceDB
            table.add(data)
            return True

        except Exception as e:
            print(f"[SemanticBugClusterer] Warning: Could not store embeddings: {e}")
            return False

    async def _cluster_by_similarity(
        self,
        bugs: List[BugReport],
        embeddings: List[Dict[str, Any]],
        similarity_threshold: float,
        min_cluster_size: int
    ) -> List[BugCluster]:
        """Cluster bugs using vector similarity search."""
        clusters = []
        assigned_bugs: Set[str] = set()

        # For each bug, find similar bugs via vector search
        for i, bug_embedding in enumerate(embeddings):
            bug_id = bug_embedding["bug_id"]

            if bug_id in assigned_bugs:
                continue  # Already assigned to a cluster

            # Vector search for similar bugs
            similar_bugs = await self._vector_search(
                query_vector=bug_embedding["embedding"],
                limit=len(bugs)
            )

            # Filter by similarity threshold and not already assigned
            similar_bug_ids = []
            similarity_scores = []

            for result in similar_bugs:
                similar_bug_id = result.get("bug_id", "")
                # Convert distance to similarity (cosine distance -> similarity)
                distance = result.get("_distance", 1.0)
                similarity = 1.0 - distance

                if similarity >= similarity_threshold and similar_bug_id not in assigned_bugs:
                    similar_bug_ids.append(similar_bug_id)
                    similarity_scores.append(similarity)

            # Check if cluster meets minimum size
            if len(similar_bug_ids) >= min_cluster_size:
                # Mark bugs as assigned
                assigned_bugs.update(similar_bug_ids)

                # Find original bug objects
                cluster_bugs = []
                for bug_id in similar_bug_ids:
                    for emb in embeddings:
                        if emb["bug_id"] == bug_id:
                            cluster_bugs.append(emb["bug"])
                            break

                # Create cluster
                cluster = BugCluster(
                    cluster_id=self._generate_cluster_id(),
                    theme="",  # Generated later
                    size=len(cluster_bugs),
                    similarity_scores=similarity_scores,
                    avg_similarity=sum(similarity_scores) / len(similarity_scores),
                    bug_ids=similar_bug_ids,
                    bug_reports=[b.test_name for b in cluster_bugs],
                    representative_bug=self._find_representative_bug(similar_bug_ids, similarity_scores),
                    discovery_methods=list(set([
                        b.discovery_method if isinstance(b.discovery_method, str) else b.discovery_method.value
                        for b in cluster_bugs
                    ])),
                    timestamp=datetime.utcnow()
                )
                clusters.append(cluster)

        return clusters

    async def _vector_search(
        self,
        query_vector: List[float],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Perform vector search for similar bugs."""
        try:
            if self.lancedb_handler.db is None:
                return []

            table = self.lancedb_handler.db.open_table(self.BUG_EMBEDDINGS_TABLE)
            results = table.search(query_vector).limit(limit).to_pandas()

            # Convert to list of dicts
            return results.to_dict("records")

        except Exception as e:
            print(f"[SemanticBugClusterer] Warning: Vector search failed: {e}")
            return []

    def _find_representative_bug(
        self,
        bug_ids: List[str],
        similarity_scores: List[float]
    ) -> str:
        """Find the most representative bug (highest similarity)."""
        # Pair bug IDs with scores and find max
        bug_scores = list(zip(bug_ids, similarity_scores))
        bug_scores.sort(key=lambda x: x[1], reverse=True)
        return bug_scores[0][0] if bug_scores else bug_ids[0]

    def _generate_cluster_id(self) -> str:
        """Generate unique cluster ID."""
        return f"cluster_{hashlib.md5(datetime.utcnow().isoformat().encode()).hexdigest()[:8]}"

    async def _generate_cluster_theme(
        self,
        bug_ids: List[str],
        bugs: List[BugReport]
    ) -> str:
        """Generate semantic theme for bug cluster using LLM."""
        if not bug_ids:
            return "Empty cluster"

        # Get error messages for bugs in cluster
        bug_map = {bug.test_name: bug for bug in bugs}

        error_messages = "\n".join([
            f"- {bug_map.get(bug_id, BugReport(
                discovery_method='property',
                test_name=bug_id,
                error_message='Unknown error',
                error_signature='unknown'
            )).error_message[:200]}"
            for bug_id in bug_ids[:5]  # Top 5 for context
        ])

        prompt = f"""Analyze these bug error messages and generate a short theme label (3-5 words).

Error messages:
{error_messages}

Task: What is the common theme or root cause across these bugs?

Examples:
- "SQL injection in agent_id parameter"
- "Memory leaks in LLM streaming"
- "Race conditions in cache updates"
- "Authentication failures across endpoints"
- "Timeout errors in API calls"

Respond ONLY with the theme label, no explanation."""

        try:
            response = await self.llm_service.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50
            )

            return response.strip()

        except Exception as e:
            print(f"[SemanticBugClusterer] Warning: Theme generation failed: {e}")
            # Fallback: generic theme
            return f"Cluster of {len(bug_ids)} similar bugs"

    def _calculate_severity_distribution(
        self,
        bug_ids: List[str],
        bugs: List[BugReport]
    ) -> Dict[str, int]:
        """Calculate severity distribution for cluster."""
        bug_map = {bug.test_name: bug for bug in bugs}

        distribution = defaultdict(int)
        for bug_id in bug_ids:
            bug = bug_map.get(bug_id)
            if bug:
                severity = bug.severity if isinstance(bug.severity, str) else bug.severity.value
                distribution[severity] += 1

        return dict(distribution)

    def _calculate_platform_distribution(
        self,
        bug_ids: List[str],
        bugs: List[BugReport]
    ) -> Dict[str, int]:
        """Calculate platform distribution for cluster."""
        bug_map = {bug.test_name: bug for bug in bugs}

        distribution = defaultdict(int)
        for bug_id in bug_ids:
            bug = bug_map.get(bug_id)
            if bug:
                platform = bug.metadata.get("platform", "unknown")
                distribution[platform] += 1

        return dict(distribution)

    async def save_clusters(
        self,
        clusters: List[BugCluster],
        output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Save clusters to JSON files.

        Args:
            clusters: List of BugCluster objects
            output_dir: Output directory (default: backend/tests/bug_discovery/storage/clusters)

        Returns:
            List of saved file paths
        """
        if output_dir is None:
            output_dir = str(backend_dir / "tests" / "bug_discovery" / "storage" / "clusters")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        saved_paths = []
        for cluster in clusters:
            filename = f"cluster_{cluster.cluster_id}.json"
            filepath = Path(output_dir) / filename

            with open(filepath, "w") as f:
                json.dump(cluster.dict(), f, indent=2, default=str)

            saved_paths.append(str(filepath))

        return saved_paths

    async def generate_cluster_report(
        self,
        clusters: List[BugCluster],
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate markdown report for bug clusters.

        Args:
            clusters: List of BugCluster objects
            output_path: Optional output file path

        Returns:
            Markdown report content
        """
        lines = [
            "# Semantic Bug Clustering Report\n",
            f"**Generated**: {datetime.utcnow().isoformat()}",
            f"**Clusters Found**: {len(clusters)}\n",
            "## Summary\n",
            f"- Total clusters: {len(clusters)}",
            f"- Bugs clustered: {sum(c.size for c in clusters)}",
            f"- Average cluster size: {sum(c.size for c in clusters) / max(len(clusters), 1):.1f}",
            f"- Average similarity: {sum(c.avg_similarity for c in clusters) / max(len(clusters), 1):.2f}\n",
            "## Clusters\n"
        ]

        for i, cluster in enumerate(clusters, 1):
            lines.append(f"### {i}. {cluster.theme}")
            lines.append(f"**Cluster ID**: `{cluster.cluster_id}`")
            lines.append(f"**Size**: {cluster.size} bugs")
            lines.append(f"**Avg Similarity**: {cluster.avg_similarity:.2f}")
            lines.append(f"**Discovery Methods**: {', '.join(cluster.discovery_methods)}")

            if cluster.severity_distribution:
                lines.append(f"**Severity**: {cluster.severity_distribution}")

            if cluster.platform_distribution:
                lines.append(f"**Platforms**: {cluster.platform_distribution}")

            lines.append("**Bugs**:")
            for bug_id in cluster.bug_ids[:10]:  # Top 10
                lines.append(f"- `{bug_id}`")

            if cluster.size > 10:
                lines.append(f"- ... and {cluster.size - 10} more")

            lines.append("")

        report = "\n".join(lines)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(report)

        return report
