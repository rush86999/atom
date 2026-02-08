"""
GraphRAG Redis Worker (Upstash)
Background process to run community detection (Leiden Algorithm) on PostgreSQL Graph.
Consumes jobs from 'graph_reindex_jobs' Redis queue.
"""

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend-saas"))

from core.database import SessionLocal
from core.models import CommunityMembership, GraphCommunity, GraphEdge, GraphNode

try:
    import networkx as nx
except ImportError:
    class MockGraph:
        def __init__(self):
            self._nodes = {}
            self._edges = {}
        @property
        def nodes(self): return self._nodes
        def add_node(self, id, **attr): self._nodes[id] = attr
        def add_edge(self, u, v, **attr): self._edges[(u, v)] = attr
        def number_of_nodes(self): return len(self._nodes)

    class nx:
        Graph = MockGraph
        @staticmethod
        def connected_components(G):
            return [list(G.nodes.keys())]

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class RedisWorker:
    def __init__(self, redis_url: str = None):
        self.max_ram_nodes = 50000 
        self.queue_name = "graph_reindex_jobs"
        self.redis_client = None
        
        # Init Redis
        redis_url = redis_url or os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(redis_url)
                logger.info(f"Connected to Redis: {redis_url.split('@')[-1]}") # Log host only
            except ImportError:
                logger.warning("redis-py not installed.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
        else:
            logger.warning("No REDIS_URL provided. Worker will not listen to queue.")

    def fetch_graph(self, workspace_id: str) -> nx.Graph:
        """Load entire workspace graph into NetworkX"""
        session = SessionLocal()
        G = nx.Graph()
        try:
            logger.info(f"Fetching nodes for workspace {workspace_id}...")
            nodes = session.query(GraphNode.id, GraphNode.name).filter_by(workspace_id=workspace_id).all()
            for n in nodes:
                G.add_node(n.id, name=n.name)
            
            logger.info(f"Fetching edges for workspace {workspace_id}...")
            edges = session.query(GraphEdge.source_node_id, GraphEdge.target_node_id, GraphEdge.weight).filter_by(workspace_id=workspace_id).all()
            for e in edges:
                G.add_edge(e.source_node_id, e.target_node_id, weight=e.weight)
                
            return G
        finally:
            session.close()

    def detect_communities(self, G: nx.Graph) -> List[List[str]]:
        """Run Louvain/Leiden algorithm"""
        if G.number_of_nodes() == 0:
            return []
            
        try:
            from networkx.algorithms.community import louvain_communities
            logger.info(f"Running Louvain on {G.number_of_nodes()} nodes...")
            communities = louvain_communities(G, seed=42)
            return [list(c) for c in communities]
        except ImportError:
            logger.warning("Louvain not available, falling back to connected components")
            return [list(c) for c in nx.connected_components(G)]

    def generate_summary(self, G: nx.Graph, community_nodes: List[str]) -> str:
        """Generate LLM summary (Stubbed)"""
        node_names = [G.nodes[n].get("name", "Unknown") for n in community_nodes[:5]]
        count = len(community_nodes)
        if count > 5:
            return f"Cluster of {count} entities involving {', '.join(node_names)}..."
        return f"Group related to {', '.join(node_names)}"

    def extract_keywords(self, G: nx.Graph, community_nodes: List[str]) -> List[str]:
        """Extract top keywords (Stubbed)"""
        return [G.nodes[n].get("name") for n in community_nodes[:5] if G.nodes[n].get("name")]

    def save_communities(self, workspace_id: str, communities: List[List[str]], G: nx.Graph):
        """Persist results to Postgres"""
        session = SessionLocal()
        try:
            session.execute(text("DELETE FROM graph_communities WHERE workspace_id = :ws_id"), {"ws_id": workspace_id})
            session.commit()
            
            for i, members in enumerate(communities):
                if len(members) < 2: continue 
                
                summary = self.generate_summary(G, members)
                keywords = self.extract_keywords(G, members)
                
                comm = GraphCommunity(
                    workspace_id=workspace_id,
                    level=0,
                    summary=summary,
                    keywords=keywords
                )
                session.add(comm)
                session.flush() # Get ID
                
                for node_id in members:
                    membership = CommunityMembership(
                        community_id=comm.id,
                        node_id=node_id
                    )
                    session.add(membership)
            
            session.commit()
            logger.info(f"Saved {len(communities)} communities for workspace {workspace_id}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save communities: {e}")
        finally:
            session.close()

    def process_job(self, workspace_id: str):
        logger.info(f"WORKER: Starting job for {workspace_id}")
        G = self.fetch_graph(workspace_id)
        if G.number_of_nodes() > self.max_ram_nodes:
            logger.error(f"Graph too large ({G.number_of_nodes()} nodes).")
            return
            
        communities = self.detect_communities(G)
        self.save_communities(workspace_id, communities, G)
        logger.info("WORKER: Job Finished.")

    def run(self):
        """Main listening loop"""
        if not self.redis_client:
            logger.error("Redis not connected. Exiting.")
            return

        logger.info(f"Listening on queue: {self.queue_name}...")
        
        while True:
            # Scale-to-Zero logic: If fetch returns None after timeout, exit
            # For now, block indefinitely or use timeout
            try:
                # brpop returns tuple (queue_name, value)
                job = self.redis_client.brpop(self.queue_name, timeout=30)
                
                if job:
                    _, workspace_id_bytes = job
                    workspace_id = workspace_id_bytes.decode('utf-8')
                    self.process_job(workspace_id)
                else:
                    logger.info("Queue empty (timeout). Idle...")
                    # In production with 'machines on demand', we would exit here
                    # sys.exit(0) 
            except Exception as e:
                logger.error(f"Worker Error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    # If run with argument, process single job (Manual/Test mode)
    if len(sys.argv) > 1:
        workspace_id = sys.argv[1]
        worker = RedisWorker(redis_url="mock://") # Skip redis conn
        worker.process_job(workspace_id)
    else:
        # Run in Daemon mode
        worker = RedisWorker()
        worker.run()
