"""
Zep Retrieval Tool Service
Encapsulates graph search, node reading, edge queries, and other tools for Report Agent use.

Core Retrieval Tools (Optimized):
1. InsightForge (Deep Insight Retrieval) - Most powerful hybrid retrieval, automatically generates sub-questions and multi-dimensional retrieval.
2. PanoramaSearch (Breadth Search) - Gets the full view, including expired content.
3. QuickSearch (Simple Search) - Fast retrieval.
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger("mirofish.zep_tools")


@dataclass
class SearchResult:
    """Search result"""

    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count,
        }

    def to_text(self) -> str:
        """Convert to text format for LLM understanding"""
        text_parts = [
            f"Search query: {self.query}",
            f"Found {self.total_count} relevant items",
        ]

        if self.facts:
            text_parts.append("\n### Relevant facts:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")

        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """Node information"""

    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
        }

    def to_text(self) -> str:
        """Convert to text format"""
        entity_type = next(
            (l for l in self.labels if l not in ["Entity", "Node"]), "Unknown type"
        )
        return f"Entity: {self.name} (Type: {entity_type})\nSummary: {self.summary}"


@dataclass
class EdgeInfo:
    """Edge information"""

    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # Time info
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at,
        }

    def to_text(self, include_temporal: bool = False) -> str:
        """Convert to text format"""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = (
            f"Relationship: {source} --[{self.name}]--> {target}\nFact: {self.fact}"
        )

        if include_temporal:
            valid_at = self.valid_at or "Unknown"
            invalid_at = self.invalid_at or "To date"
            base_text += f"\nTemporality: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (Expired: {self.expired_at})"

        return base_text

    @property
    def is_expired(self) -> bool:
        """Is expired"""
        return self.expired_at is not None

    @property
    def is_invalid(self) -> bool:
        """Is invalid"""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    Deep Insight Retrieval Result (InsightForge)
    Contains retrieval results for multiple sub-questions, as well as integrated analysis.
    """

    query: str
    simulation_requirement: str
    sub_queries: List[str]

    # Multi-dimension retrieval results
    semantic_facts: List[str] = field(default_factory=list)  # SemanticSearch results
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # Entity insights
    relationship_chains: List[str] = field(default_factory=list)  # Relationship chains

    # Statistics
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships,
        }

    def to_text(self) -> str:
        """convert to detailed textFormat,ForLLMUnderstand"""
        text_parts = [
            f"## Deep Insight Retrieval",
            f"Query: {self.query}",
            f"Scenario: {self.simulation_requirement}",
            f"\n### Prediction Data Statistics",
            f"- Related predictive facts: {self.total_facts} items",
            f"- Entities involved: {self.total_entities} items",
            f"- Relationship chains: {self.total_relationships} items",
        ]

        # Sub-queries
        if self.sub_queries:
            text_parts.append(f"\n### Sub-questions analyzed")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")

        # Semantic search results
        if self.semantic_facts:
            text_parts.append(f"\n### [Key Facts] (Please cite these in the report)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        # Entity insights
        if self.entity_insights:
            text_parts.append(f"\n### [Core Entities]")
            for entity in self.entity_insights:
                text_parts.append(
                    f"- **{entity.get('name', 'Unknown')}** ({entity.get('type', 'Entity')})"
                )
                if entity.get("summary"):
                    text_parts.append(f'  Summary: "{entity.get("summary")}"')
                if entity.get("related_facts"):
                    text_parts.append(
                        f"  Related facts: {len(entity.get('related_facts', []))} items"
                    )

        # Relationship chains
        if self.relationship_chains:
            text_parts.append(f"\n### [Relationship Chains]")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")

        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    Breadth Search Result (Panorama)
    Contains all relevant information, including expired content.
    """

    query: str

    # All nodes
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # All edges(Includeexpired)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # Current active facts
    active_facts: List[str] = field(default_factory=list)
    # Expired/invalid facts (historical records)
    historical_facts: List[str] = field(default_factory=list)

    # Statistics
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count,
        }

    def to_text(self) -> str:
        """Convert to text format(Full version, not truncated)"""
        text_parts = [
            f"## Breadth Search Results (Panoramic View)",
            f"Query: {self.query}",
            f"\n### Statistics",
            f"- Total nodes: {self.total_nodes}",
            f"- Total edges: {self.total_edges}",
            f"- Current effective facts: {self.active_count} items",
            f"- Historical/expired facts: {self.historical_count} items",
        ]

        # Current effective facts
        if self.active_facts:
            text_parts.append(
                f"\n### [Current Effective Facts] (Simulation original text)"
            )
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        # Historical/expired facts
        if self.historical_facts:
            text_parts.append(
                f"\n### [Historical/Expired Facts] (Process evolution records)"
            )
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        # Involved entities
        if self.all_nodes:
            text_parts.append(f"\n### [Involved Entities]")
            for node in self.all_nodes:
                entity_type = next(
                    (l for l in node.labels if l not in ["Entity", "Node"]), "Entity"
                )
                text_parts.append(f"- **{node.name}** ({entity_type})")

        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """Interview result for a single agent"""

    agent_name: str
    agent_role: str  # Role type (e.g., student, teacher, media, etc.)
    agent_bio: str  # Bio
    question: str  # Interview question
    response: str  # Interview answer
    key_quotes: List[str] = field(default_factory=list)  # Key quotes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes,
        }

    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        # Full bio, not truncated
        text += f"_Bio: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**Key Quotes:**\n"
            for quote in self.key_quotes:
                # Cleanup quotes
                clean_quote = (
                    quote.replace("\u201c", "").replace("\u201d", "").replace('"', "")
                )
                clean_quote = clean_quote.replace("\u300c", "").replace("\u300d", "")
                clean_quote = clean_quote.strip()
                # Remove punctuation from the beginning
                while clean_quote and clean_quote[0] in ",,;;::,.!?\n\r\t ":
                    clean_quote = clean_quote[1:]
                # Filter out garbage
                skip = False
                for d in "123456789":
                    if f"Question{d}" in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # Truncate long content
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find(".", 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[: dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    Interview Result
    Contains interview responses from multiple simulated agents.
    """

    interview_topic: str  # Interview topic
    interview_questions: List[str]  # Interview question list

    # Selected agents for interview
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # Each agent's interview answer
    interviews: List[AgentInterview] = field(default_factory=list)

    # Agent selection reasoning
    selection_reasoning: str = ""
    # Integrated interview summary
    summary: str = ""

    # Statistics
    total_agents: int = 0
    interviewed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count,
        }

    def to_text(self) -> str:
        """convert to detailed textFormat,ForLLMUnderstandAndreport citation"""
        text_parts = [
            "## In-depth Interview Report",
            f"**Topic:** {self.interview_topic}",
            f"**Participants:** {self.interviewed_count} / {self.total_agents} simulated agents",
            "\n### Selection Reasoning",
            self.selection_reasoning or "(Automatically selected)",
            "\n---",
            "\n### Interview Transcripts",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### Interview #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("(No interview records)\n\n---")

        text_parts.append("\n### Interview Summary and Key Points")
        text_parts.append(self.summary or "(No summary)")

        return "\n".join(text_parts)


class ZepToolsService:
    """
    Zep Retrieval Tool Service

    [Core Retrieval Tools - Optimized]
    1. insight_forge - Deep insight retrieval (most powerful, automatically generates sub-questions, multi-dimensional retrieval)
    2. panorama_search - Breadth search (gets full view, including expired content)
    3. quick_search - Simple search (fast retrieval)
    4. interview_agents - Depth interview (interviews simulated agents, obtains multi-perspective views)

    [Basic Tools]
    - search_graph - Graph semantic search
    - get_all_nodes - Gets all nodes in the graph
    - get_all_edges - Gets all edges in the graph (including temporal info)
    - get_node_detail - Gets detailed node information
    - get_node_edges - Gets edges related to a node
    - get_entities_by_type - Gets entities by type
    - get_entity_summary - Gets relation summary of an entity
    """

    # Retry config
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0

    def __init__(
        self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None
    ):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY not configured")

        self.client = Zep(api_key=self.api_key)
        # LLM client used for InsightForge sub-question generation
        self._llm_client = llm_client
        logger.info("ZepToolsService initialized")

    @property
    def llm(self) -> LLMClient:
        """Lazy init LLM client"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """API call with retry mechanism"""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(
                        f"Zep {operation_name} failed after {max_retries} attempts: {str(e)}"
                    )

        raise last_exception

    def search_graph(
        self, graph_id: str, query: str, limit: int = 10, scope: str = "edges"
    ) -> SearchResult:
        """
        Graph semantic search

        Use hybrid search (semantic+BM25) to search related info in graph.
        If Zep Cloud search API unavailable, fallback to local keyword matching.

        Args:
            graph_id: Graph ID (Standalone Graph)
            query: Search query
            limit: Return result count
            scope: Search scope,"edges" Or "nodes"

        Returns:
            SearchResult: Search results
        """
        # Zep API limit: max 400 characters per query
        ZEP_QUERY_MAX = 400
        if len(query) > ZEP_QUERY_MAX:
            query = query[:ZEP_QUERY_MAX]

        logger.info(f"Graph search: graph_id={graph_id}, query={query[:50]}...")

        # Try to useZep Cloud Search API
        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=query,
                    limit=limit,
                    scope=scope,
                    reranker="cross_encoder",
                ),
                operation_name=f"graph_search(graph={graph_id})",
            )

            facts = []
            edges = []
            nodes = []

            # ParseedgeSearch results
            if hasattr(search_results, "edges") and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, "fact") and edge.fact:
                        facts.append(edge.fact)
                    edges.append(
                        {
                            "uuid": getattr(edge, "uuid_", None)
                            or getattr(edge, "uuid", ""),
                            "name": getattr(edge, "name", ""),
                            "fact": getattr(edge, "fact", ""),
                            "source_node_uuid": getattr(edge, "source_node_uuid", ""),
                            "target_node_uuid": getattr(edge, "target_node_uuid", ""),
                        }
                    )

            # Parse nodesSearch results
            if hasattr(search_results, "nodes") and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append(
                        {
                            "uuid": getattr(node, "uuid_", None)
                            or getattr(node, "uuid", ""),
                            "name": getattr(node, "name", ""),
                            "labels": getattr(node, "labels", []),
                            "summary": getattr(node, "summary", ""),
                        }
                    )
                    # Node summary also counts as fact
                    if hasattr(node, "summary") and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")

            logger.info(f"Search complete: found {len(facts)} relevant facts")

            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts),
            )

        except Exception as e:
            logger.warning(f"Zep Search API failed, falling back to local search: {str(e)}")
            # Fallback:Use localKeyword matchSearch
            return self._local_search(graph_id, query, limit, scope)

    def _local_search(
        self, graph_id: str, query: str, limit: int = 10, scope: str = "edges"
    ) -> SearchResult:
        """
        Local keyword matching search (as Zep Search API fallback)

        Get all edges/nodes, then keyword match locally

        Args:
            graph_id: Graph ID
            query: Search query
            limit: Return result count
            scope: Search scope

        Returns:
            SearchResult: Search results
        """
        logger.info(f"Using local search: query={query[:30]}...")

        facts = []
        edges_result = []
        nodes_result = []

        # Extract query keywords (simple tokenization)
        query_lower = query.lower()
        keywords = [
            w.strip()
            for w in query_lower.replace(",", " ").replace(",", " ").split()
            if len(w.strip()) > 1
        ]

        def match_score(text: str) -> int:
            """Calculate text-query match score"""
            if not text:
                return 0
            text_lower = text.lower()
            # Exact query match
            if query_lower in text_lower:
                return 100
            # Keyword match
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score

        try:
            if scope in ["edges", "both"]:
                # Get all edges and match
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))

                # Sort by score
                scored_edges.sort(key=lambda x: x[0], reverse=True)

                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append(
                        {
                            "uuid": edge.uuid,
                            "name": edge.name,
                            "fact": edge.fact,
                            "source_node_uuid": edge.source_node_uuid,
                            "target_node_uuid": edge.target_node_uuid,
                        }
                    )

            if scope in ["nodes", "both"]:
                # Get all nodes and match
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))

                scored_nodes.sort(key=lambda x: x[0], reverse=True)

                for score, node in scored_nodes[:limit]:
                    nodes_result.append(
                        {
                            "uuid": node.uuid,
                            "name": node.name,
                            "labels": node.labels,
                            "summary": node.summary,
                        }
                    )
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")

            logger.info(f"Local search complete: found {len(facts)} relevant facts")

        except Exception as e:
            logger.error(f"Local search failed: {str(e)}")

        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts),
        )

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        Get all nodes of graph (paginated)

        Args:
            graph_id: Graph ID

        Returns:
            Node list
        """
        logger.info(f"Fetching all nodes for graph {graph_id}...")

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = (
                getattr(node, "uuid_", None) or getattr(node, "uuid", None) or ""
            )
            result.append(
                NodeInfo(
                    uuid=str(node_uuid) if node_uuid else "",
                    name=node.name or "",
                    labels=node.labels or [],
                    summary=node.summary or "",
                    attributes=node.attributes or {},
                )
            )

        logger.info(f"Fetched {len(result)} nodes")
        return result

    def get_all_edges(
        self, graph_id: str, include_temporal: bool = True
    ) -> List[EdgeInfo]:
        """
        GetgraphAlledge(PaginateGet,ContainsTime info)

        Args:
            graph_id: Graph ID
            include_temporal: whetherContainsTime info(DefaultTrue)

        Returns:
            Edge list (includes created_at, valid_at, invalid_at, expired_at)
        """
        logger.info(f"Fetching all edges for graph {graph_id}...")

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = (
                getattr(edge, "uuid_", None) or getattr(edge, "uuid", None) or ""
            )
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or "",
            )

            # AddTime info
            if include_temporal:
                edge_info.created_at = getattr(edge, "created_at", None)
                edge_info.valid_at = getattr(edge, "valid_at", None)
                edge_info.invalid_at = getattr(edge, "invalid_at", None)
                edge_info.expired_at = getattr(edge, "expired_at", None)

            result.append(edge_info)

        logger.info(f"Fetched {len(result)} edges")
        return result

    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
        Get single node detailed info

        Args:
            node_uuid: Node UUID

        Returns:
            Node info or None
        """
        logger.info(f"Fetching node detail: {node_uuid[:8]}...")

        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=f"get_node_detail(uuid={node_uuid[:8]}...)",
            )

            if not node:
                return None

            return NodeInfo(
                uuid=getattr(node, "uuid_", None) or getattr(node, "uuid", ""),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
            )
        except Exception as e:
            logger.error(f"Failed to fetch node detail: {str(e)}")
            return None

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        Get all edges related to node

        Get all graph edges, then filter edges related to specified node

        Args:
            graph_id: Graph ID
            node_uuid: Node UUID

        Returns:
            Edge list
        """
        logger.info(f"Fetching edges for node {node_uuid[:8]}...")

        try:
            # GetAll graph edges,Then filter
            all_edges = self.get_all_edges(graph_id)

            result = []
            for edge in all_edges:
                # Check if edge related to specified node (as source or target)
                if (
                    edge.source_node_uuid == node_uuid
                    or edge.target_node_uuid == node_uuid
                ):
                    result.append(edge)

            logger.info(f"Found {len(result)} edges related to node")
            return result

        except Exception as e:
            logger.warning(f"Failed to fetch node edges: {str(e)}")
            return []

    def get_entities_by_type(self, graph_id: str, entity_type: str) -> List[NodeInfo]:
        """
        Get entities by type

        Args:
            graph_id: Graph ID
            entity_type: Entity type (e.g., Student, PublicFigure, etc.)

        Returns:
            Entity list matching type
        """
        logger.info(f"Fetching entities of type {entity_type}...")

        all_nodes = self.get_all_nodes(graph_id)

        filtered = []
        for node in all_nodes:
            # Check if labels contain specified type
            if entity_type in node.labels:
                filtered.append(node)

        logger.info(f"Found {len(filtered)} entities of type {entity_type}")
        return filtered

    def get_entity_summary(self, graph_id: str, entity_name: str) -> Dict[str, Any]:
        """
        Get entity relation summary

        Search all info related to entity and generate summary

        Args:
            graph_id: Graph ID
            entity_name: Entity name

        Returns:
            Entity summary info
        """
        logger.info(f"Fetching relation summary for entity {entity_name}...")

        # First search entity-related info
        search_result = self.search_graph(
            graph_id=graph_id, query=entity_name, limit=20
        )

        # Try to find entity among all nodes
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break

        related_edges = []
        if entity_node:
            # Pass ingraph_idParameters
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)

        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges),
        }

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        Get graph statistics

        Args:
            graph_id: Graph ID

        Returns:
            Statistics
        """
        logger.info(f"Fetching statistics for graph {graph_id}...")

        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)

        # Count entity type distribution
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1

        # Count relation type distribution
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1

        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types,
        }

    def get_simulation_context(
        self, graph_id: str, simulation_requirement: str, limit: int = 30
    ) -> Dict[str, Any]:
        """
        Get simulation-related context info

        Comprehensive search of all simulation requirement-related info

        Args:
            graph_id: Graph ID
            simulation_requirement: Simulation requirement description
            limit: Limit per info type

        Returns:
            Simulation context info
        """
        logger.info(f"Fetching simulation context: {simulation_requirement[:50]}...")

        # Search info related to simulation requirement
        search_result = self.search_graph(
            graph_id=graph_id, query=simulation_requirement, limit=limit
        )

        # Get graph statistics
        stats = self.get_graph_statistics(graph_id)

        # GetAllEntitynode
        all_nodes = self.get_all_nodes(graph_id)

        # Filter entities with actual type (non-pure Entity nodes)
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append(
                    {
                        "name": node.name,
                        "type": custom_labels[0],
                        "summary": node.summary,
                    }
                )

        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],  # LimitCount
            "total_entities": len(entities),
        }

    # ========== Core retrieval tools(After optimization) ==========

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5,
    ) -> InsightForgeResult:
        """
        [InsightForge - Deep Insight Retrieval]

        Most powerful hybrid retrieval, automatically decomposes problem and retrieves multi-dimensionally:
        1. Use LLM to decompose problem into multiple sub-questions
        2. Semantic search for each sub-question
        3. Extract related entities and get their detailed info
        4. Track relationship chains
        5. Integrate all results, generate deep insight

        Args:
            graph_id: Graph ID
            query: User question
            simulation_requirement: Simulation requirement description
            report_context: Report context (optional, for more accurate sub-question generation)
            max_sub_queries: Max sub-question count

        Returns:
            InsightForgeResult: Deep insight retrieval result
        """
        logger.info(f"InsightForge deep insight retrieval: {query[:50]}...")

        result = InsightForgeResult(
            query=query, simulation_requirement=simulation_requirement, sub_queries=[]
        )

        # Step 1: UseLLMGeneratesubQuestion
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries,
        )
        result.sub_queries = sub_queries
        logger.info(f"Generated {len(sub_queries)} sub-queries")

        # Step 2: Semantic search for each sub-question
        all_facts = []
        all_edges = []
        seen_facts = set()

        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id, query=sub_query, limit=15, scope="edges"
            )

            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)

            all_edges.extend(search_result.edges)

        # to originalQuestionalso performSearch
        main_search = self.search_graph(
            graph_id=graph_id, query=query, limit=20, scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)

        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)

        # Step 3: Extract related entity UUIDs from edges, only get info for these entities (not all nodes)
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get("source_node_uuid", "")
                target_uuid = edge_data.get("target_node_uuid", "")
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)

        # GetAllRelatedEntitydetails(NotLimitCount,Full output)
        entity_insights = []
        node_map = {}  # Used forLaterRelationship chainsBuild

        for uuid in list(entity_uuids):  # Process all entities, not truncated
            if not uuid:
                continue
            try:
                # SeparateGeteachitemsRelatednode info
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next(
                        (l for l in node.labels if l not in ["Entity", "Node"]), "Entity"
                    )

                    # Get all facts related to entity (not truncated)
                    related_facts = [
                        f for f in all_facts if node.name.lower() in f.lower()
                    ]

                    entity_insights.append(
                        {
                            "uuid": node.uuid,
                            "name": node.name,
                            "type": entity_type,
                            "summary": node.summary,
                            "related_facts": related_facts,  # Full output, not truncated
                        }
                    )
            except Exception as e:
                logger.debug(f"Failed to fetch node {uuid}: {e}")
                continue

        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)

        # Step 4: BuildAllRelationship chains(NotLimitCount)
        relationship_chains = []
        for edge_data in all_edges:  # Process all edges, not truncated
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get("source_node_uuid", "")
                target_uuid = edge_data.get("target_node_uuid", "")
                relation_name = edge_data.get("name", "")

                source_name = (
                    node_map.get(source_uuid, NodeInfo("", "", [], "", {})).name
                    or source_uuid[:8]
                )
                target_name = (
                    node_map.get(target_uuid, NodeInfo("", "", [], "", {})).name
                    or target_uuid[:8]
                )

                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)

        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)

        logger.info(
            f"InsightForge complete: {result.total_facts} facts, {result.total_entities} entities, {result.total_relationships} relationships"
        )
        return result

    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5,
    ) -> List[str]:
        """
        UseLLMGeneratesubQuestion

        will complexQuestiondecompose intoManyitemscan independently retrievesubQuestion
        """
        system_prompt = """You are a professional problem analysis expert. Your task is to break down a complex problem into multiple sub-questions that can be independently observed in the simulation world.

Requirements:
1. Each sub-question should be specific enough to find relevant Agent behaviors or events in the simulation world.
2. Sub-questions should cover different dimensions of the original problem (e.g., who, what, why, how, when, where).
3. Sub-questions should be relevant to the simulation scenario.
4. Return in JSON format: {"sub_queries": ["Sub-question 1", "Sub-question 2", ...]}"""

        user_prompt = f"""Simulation scenario background:
{simulation_requirement}

{f"Report context: {report_context[:500]}" if report_context else ""}

Please break down the following problem into {max_queries} sub-questions:
{query}

Return the list of sub-questions in JSON format."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )

            sub_queries = response.get("sub_queries", [])
            # ensure stringList
            return [str(sq) for sq in sub_queries[:max_queries]]

        except Exception as e:
            logger.warning(f"Failed to generate sub-queries: {str(e)}, using defaults")
            # Fallback:Returnbased on originalQuestionvariant
            return [
                query,
                f"{query} Main participants",
                f"{query} Causes and effects",
                f"{query} Development process",
            ][:max_queries]

    def panorama_search(
        self, graph_id: str, query: str, include_expired: bool = True, limit: int = 50
    ) -> PanoramaResult:
        """
        [PanoramaSearch - Breadth Search]

        Get full view, including all related content and historical/expired info:
        1. GetAllRelatednode
        2. GetAlledge(Includes expired/invalid)
        3. Classify current active and historical info

        This tool is suitable for understanding full event picture, tracking evolution.

        Args:
            graph_id: Graph ID
            query: Search query(Used forRelatednessSort)
            include_expired: Include expired content (default True)
            limit: Return result countLimit

        Returns:
            PanoramaResult: BreadthSearch results
        """
        logger.info(f"PanoramaSearch broad search: {query[:50]}...")

        result = PanoramaResult(query=query)

        # GetAll nodes
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)

        # GetAlledge(ContainsTime info)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)

        # Classify facts
        active_facts = []
        historical_facts = []

        for edge in all_edges:
            if not edge.fact:
                continue

            # as factsAddEntity name
            source_name = (
                node_map.get(edge.source_node_uuid, NodeInfo("", "", [], "", {})).name
                or edge.source_node_uuid[:8]
            )
            target_name = (
                node_map.get(edge.target_node_uuid, NodeInfo("", "", [], "", {})).name
                or edge.target_node_uuid[:8]
            )

            # Check if expired/invalid
            is_historical = edge.is_expired or edge.is_invalid

            if is_historical:
                # Historical/expired facts, add time markers
                valid_at = edge.valid_at or "Unknown"
                invalid_at = edge.invalid_at or edge.expired_at or "Unknown"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # Current active facts
                active_facts.append(edge.fact)

        # Relevance sort based on query
        query_lower = query.lower()
        keywords = [
            w.strip()
            for w in query_lower.replace(",", " ").replace(",", " ").split()
            if len(w.strip()) > 1
        ]

        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score

        # SortAndLimitCount
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)

        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)

        logger.info(
            f"PanoramaSearch complete: {result.active_count} active, {result.historical_count} historical"
        )
        return result

    def quick_search(self, graph_id: str, query: str, limit: int = 10) -> SearchResult:
        """
        [QuickSearch - Simple Search]

        Fast, lightweight retrieval tool:
        1. Directly call Zep semantic search
        2. Return most relevant results
        3. Suitable for simple, direct retrieval needs

        Args:
            graph_id: Graph ID
            query: Search query
            limit: Return result count

        Returns:
            SearchResult: Search results
        """
        logger.info(f"QuickSearch: {query[:50]}...")

        # directCallexistingsearch_graphMethod
        result = self.search_graph(
            graph_id=graph_id, query=query, limit=limit, scope="edges"
        )

        logger.info(f"QuickSearch complete: {result.total_count} results")
        return result

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None,
    ) -> InterviewResult:
        """
        [InterviewAgents - Deep Interview]

        Call real OASIS interview API, interview agents running in simulation:
        1. Auto-read persona files, understand all simulated agents
        2. Use LLM to analyze interview requirement, intelligently select most relevant agents
        3. Use LLM to generate interview questions
        4. Call /api/simulation/interview/batch Endpoint for real interview(Dual platform simultaneous interview)
        5. Integrate all interview results, generate interview report

        【Important】This feature requires simulation environment running (OASIS environment not closed)

        【Use case】
        - Need to understand event from different role perspectives
        - Need to collect multiple opinions and viewpoints
        - Need to get real simulated agent responses (not LLM simulated)

        Args:
            simulation_id: Simulation ID (for locating persona files and calling interview API)
            interview_requirement: Interview requirementdescription(Unstructured,Such as"Understand student views on event")
            simulation_requirement: Simulation requirement background (optional)
            max_agents: Max agents to interview
            custom_questions: Custom interview questions (optional, auto-generate if not provided)

        Returns:
            InterviewResult: Interview result
        """
        from .simulation_runner import SimulationRunner

        logger.info(
            f"InterviewAgents (real API): {interview_requirement[:50]}..."
        )

        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or [],
        )

        # Step 1: Read persona files
        profiles = self._load_agent_profiles(simulation_id)

        if not profiles:
            logger.warning(f"No agent profiles found for simulation {simulation_id}")
            result.summary = "No agent profiles available for interview"
            return result

        result.total_agents = len(profiles)
        logger.info(f"Loaded {len(profiles)} agent profiles")

        # Step 2: Use LLM to select agents to interview (return agent_id list)
        selected_agents, selected_indices, selection_reasoning = (
            self._select_agents_for_interview(
                profiles=profiles,
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                max_agents=max_agents,
            )
        )

        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(
            f"Selected {len(selected_agents)} agents for interview: {selected_indices}"
        )

        # Step 3: Generate interview questions (if not provided)
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents,
            )
            logger.info(f"Generated {len(result.interview_questions)} interview questions")

        # Combine questions into interview prompt
        combined_prompt = "\n".join(
            [f"{i + 1}. {q}" for i, q in enumerate(result.interview_questions)]
        )

        # Add optimization prefix to constrain agent response format
        INTERVIEW_PROMPT_PREFIX = (
            "You are being interviewed. Please combine your persona, all past memories, and actions, "
            "to answer the following questions in natural language.\n"
            "Requirements:\n"
            "1. Use natural language, do not call any tools.\n"
            "2. Do not return in JSON format or tool call format.\n"
            "3. Do not use Markdown headers (e.g., #, ##, ###).\n"
            "4. Answer each question one by one, starting with 'Question X:' (X is the question number).\n"
            "5. Separate each answer with an empty line.\n"
            "6. Provide substantive answers, at least 2-3 sentences for each question.\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"

        # Step 4: Callreal interviewAPI(Not specifyplatform,DefaultDual platform simultaneous interview)
        try:
            # Build batch interview list (not specify platform, dual platform interview)
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append(
                    {
                        "agent_id": agent_idx,
                        "prompt": optimized_prompt,  # Use optimizedprompt
                        # Not specifyplatform,APIWilltwitterAndredditInterview both platforms
                    }
                )

            logger.info(f"Calling batch interview API (dual platform): {len(interviews_request)} agents")

            # Call SimulationRunner batch interview method (not pass platform, dual platform interview)
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # Not specifyplatform,Dual platform interview
                timeout=180.0,  # Dual platform needs longer timeout
            )

            logger.info(
                f"Interview API response: {api_result.get('interviews_count', 0)} results, success={api_result.get('success')}"
            )

            # Check if API call succeeded
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "unknown error")
                logger.warning(f"Interview API returned failure: {error_msg}")
                result.summary = (
                    f"Interview API call failed: {error_msg}. Please check the OASIS simulation environment."
                )
                return result

            # Step 5: ParseAPIReturnResult,BuildAgentInterviewObject
            # Dual platform mode return format: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = (
                api_data.get("results", {}) if isinstance(api_data, dict) else {}
            )

            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get(
                    "realname", agent.get("username", f"Agent_{agent_idx}")
                )
                agent_role = agent.get("profession", "Unknown")
                agent_bio = agent.get("bio", "")

                # GetThisAgentin bothitemsplatformInterview result
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})

                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # Clean possible tool calls JSON Wrapper
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # Always output dual platform markers
                twitter_text = (
                    twitter_response if twitter_response else "(No response from this platform)"
                )
                reddit_text = (
                    reddit_response if reddit_response else "(No response from this platform)"
                )
                response_text = f"【TwitterPlatform response】\n{twitter_text}\n\n【RedditPlatform response】\n{reddit_text}"

                # ExtractKey quotes(From answers of both platforms)
                import re

                combined_responses = f"{twitter_response} {reddit_response}"

                # Clean response text:Remove markers,Number,Markdown etc interference
                clean_text = re.sub(r"#{1,6}\s+", "", combined_responses)
                clean_text = re.sub(r"\{[^}]*tool_name[^}]*\}", "", clean_text)
                clean_text = re.sub(r"[*_`|>~\-]{2,}", "", clean_text)
                clean_text = re.sub(r"Question\d+[::]\s*", "", clean_text)
                clean_text = re.sub(r"【[^】]+】", "", clean_text)

                # Strategy1(Main): Extract complete substantive sentences
                sentences = re.split(r"[.!?]", clean_text)
                meaningful = [
                    s.strip()
                    for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r"^[\s\W,,;;::,]+", s.strip())
                    and not s.strip().startswith(("{", "Question"))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "." for s in meaningful[:3]]

                # Strategy2(Supplement): Correctly paired Chinese quotes""Long text within
                if not key_quotes:
                    paired = re.findall(
                        r"\u201c([^\u201c\u201d]{15,100})\u201d", clean_text
                    )
                    paired += re.findall(
                        r"\u300c([^\u300c\u300d]{15,100})\u300d", clean_text
                    )
                    key_quotes = [
                        q for q in paired if not re.match(r"^[,,;;::,]", q)
                    ][:3]

                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # ExpandbioLengthLimit
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5],
                )
                result.interviews.append(interview)

            result.interviewed_count = len(result.interviews)

        except ValueError as e:
            # Simulation environment not running
            logger.warning(f"Interview API call failed (environment not running?): {e}")
            result.summary = (
                f"Interview failed: {str(e)}. The simulation environment may be stopped, please ensure OASIS is running."
            )
            return result
        except Exception as e:
            logger.error(f"Interview API call exception: {e}")
            import traceback

            logger.error(traceback.format_exc())
            result.summary = f"Interview process error: {str(e)}"
            return result

        # Step 6: Generate interview summary
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement,
            )

        logger.info(
            f"InterviewAgents complete: interviewed {result.interviewed_count} agents (dual platform)"
        )
        return result

    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Clean Agent In response JSON toolCallWrapper,Extract actual content"""
        if not response or not response.strip().startswith("{"):
            return response
        text = response.strip()
        if "tool_name" not in text[:80]:
            return response
        import re as _re

        try:
            data = json.loads(text)
            if isinstance(data, dict) and "arguments" in data:
                for key in ("content", "text", "body", "message", "reply"):
                    if key in data["arguments"]:
                        return str(data["arguments"][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace("\\n", "\n").replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Load simulation'sAgentPersona file"""
        import os
        import csv

        # BuildPersona filePath
        sim_dir = os.path.join(
            os.path.dirname(__file__), f"../../uploads/simulations/{simulation_id}"
        )

        profiles = []

        # Priority try to readReddit JSONFormat
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, "r", encoding="utf-8") as f:
                    profiles = json.load(f)
                logger.info(f"Loaded {len(profiles)} profiles from reddit_profiles.json")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read reddit_profiles.json: {e}")

        # Try to readTwitter CSVFormat
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # CSVFormatconvert to unifiedFormat
                        profiles.append(
                            {
                                "realname": row.get("name", ""),
                                "username": row.get("username", ""),
                                "bio": row.get("description", ""),
                                "persona": row.get("user_char", ""),
                                "profession": "Unknown",
                            }
                        )
                logger.info(f"Loaded {len(profiles)} profiles from twitter_profiles.csv")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read twitter_profiles.csv: {e}")

        return profiles

    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int,
    ) -> tuple:
        """
        UseLLMSelectneedinterviewAgent

        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: SelectedAgentComplete infoList
                - selected_indices: SelectedAgentindexList(Used forAPICall)
                - reasoning: Selection reason
        """

        # BuildAgentSummary list
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "Unknown"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", []),
            }
            agent_summaries.append(summary)

        system_prompt = """You are a professional interview planning expert.Your task is based on interview requirement,From simulationAgentSelect most suitable interview subjects from list.

Selection criteria:
1. Agentidentity/Profession andInterview topicRelated
2. AgentMay hold unique or valuable viewpoints
3. Select diverse perspectives(Such as:Support side,Opposition side,Neutral party,Professionals, etc.)
4. Prioritize roles directly related to event

ReturnJSONFormat:
{
    "selected_indices": [SelectedAgentindexList],
    "reasoning": "Selection reasoning explanation"
}"""

        user_prompt = f"""Interview requirement:
{interview_requirement}

Simulation background:
{simulation_requirement if simulation_requirement else "Not provided"}

OptionalAgentList(Total{len(agent_summaries)}items):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

PleaseSelect up to{max_agents}Most suitable for interviewAgent,AndexplainSelection reason."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )

            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "Auto-select based on relevance")

            # GetSelectedAgentComplete info
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)

            return selected_agents, valid_indices, reasoning

        except Exception as e:
            logger.warning(f"LLM agent selection failed, using default: {e}")
            # Fallback:Before selectionNitems
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "Use default selection strategy"

    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]],
    ) -> List[str]:
        """Use LLM to generate interview questions"""

        agent_roles = [a.get("profession", "Unknown") for a in selected_agents]

        system_prompt = """You are a professional journalist/Interviewer.Based onInterview requirement,Generate3-5itemsdeepInterview question.

Questionneedrequirement:
1. Open-ended questions,Encourage detailed answers
2. ForNotdifferent roles may haveNotdifferent answers
3. Cover facts,Viewpoints,feelings, etc.Manyitemsdimension
4. Natural language,Like real interview
5. Each question limited to50Within characters,Concise
6. Direct questions,Don't include background explanation or prefix

ReturnJSONFormat:{"questions": ["Question1", "Question2", ...]}"""

        user_prompt = f"""Interview requirement:{interview_requirement}

Simulation background:{simulation_requirement if simulation_requirement else "Not provided"}

Interview subject role:{", ".join(agent_roles)}

PleaseGenerate3-5itemsInterview question."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
            )

            return response.get(
                "questions", [f"About{interview_requirement},What is your view?"]
            )

        except Exception as e:
            logger.warning(f"Failed to generate interview questions: {e}")
            return [
                f"About{interview_requirement},youViewpointsis what?",
                "How does this affect you or the group you represent?",
                "How do you think this problem should be solved or improved?",
            ]

    def _generate_interview_summary(
        self, interviews: List[AgentInterview], interview_requirement: str
    ) -> str:
        """Generate interview summary"""

        if not interviews:
            return "No interviews completed"

        # Collect all interview content
        interview_texts = []
        for interview in interviews:
            interview_texts.append(
                f"【{interview.agent_name}({interview.agent_role})】\n{interview.response[:500]}"
            )

        system_prompt = """You are a professional news editor.PleaseBased onManyintervieweesresponse,GenerateAn interview summary.

Summary requirements:
1. Extract main viewpoints from each party
2. Point out consensus and disagreements
3. Highlight valuable quotes
4. Objective and neutral,Don't favor any side
5. Limited to1000within characters

Format constraints(Must follow):
- Use plain text paragraphs,separate with blank linesNotdifferent parts
- NotneedUseMarkdownTitle(Such as#,##,###)
- Don't use dividers(Such as---,***)
- Use Chinese quotes when quoting respondent's original words""
- Can use**Bold**Mark keywords,butNotneedUseotherMarkdownSyntax"""

        user_prompt = f"""Interview topic:{interview_requirement}

Interview content:
{"".join(interview_texts)}

PleaseGenerate interview summary."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            return summary

        except Exception as e:
            logger.warning(f"Failed to generate interview summary: {e}")
            # Fallback:Simple concatenation
            return f"Interviewed{len(interviews)}interviewees,Include:" + ",".join(
                [i.agent_name for i in interviews]
            )
