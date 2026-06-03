"""Frozen 3.0 artifact graph contracts with machine_spec as source of truth."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


SOURCE_OF_TRUTH_ARTIFACT = "machine_spec"
HUMAN_PROJECTION_ARTIFACTS = frozenset({"human_brief", "optional_prd", "optional_manual"})


class ArtifactGraphValidationError(ValueError):
    """Artifact graph constraint validation error."""
    pass



class ArtifactNodeType(str, Enum):
    REQUIREMENT = "requirement"
    DECISION = "decision"
    HUMAN_BRIEF = "human_brief"
    MACHINE_SPEC = SOURCE_OF_TRUTH_ARTIFACT
    AGENT_PACKAGE = "agent_package"
    ACCEPTANCE_PROTOCOL = "acceptance_protocol"
    REVIEW_CHECKLIST = "review_checklist"
    REVIEW_RESULT = "review_result"
    TRACEABILITY_MAP = "traceability_map"
    DECISION_LOG = "decision_log"
    OPTIONAL_PRD = "optional_prd"
    OPTIONAL_MANUAL = "optional_manual"


class ArtifactEdgeType(str, Enum):
    DERIVES_FROM = "derives_from"
    ADDRESSES_REQUIREMENT = "addresses_requirement"
    RESOLVES_DECISION = "resolves_decision"
    VALIDATES = "validates"
    REVIEWS = "reviews"
    SUPERSEDES = "supersedes"


@dataclass
class ArtifactRef:
    name: str
    version: Optional[str] = None
    storage_uri: Optional[str] = None
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactRef":
        return cls(
            name=data["name"],
            version=data.get("version"),
            storage_uri=data.get("storage_uri"),
            checksum=data.get("checksum"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ArtifactNode:
    node_id: str
    type: ArtifactNodeType
    artifact_ref: ArtifactRef
    summary: str = ""
    created_by: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_source_of_truth(self) -> bool:
        return self.type == ArtifactNodeType.MACHINE_SPEC

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "type": self.type.value,
            "artifact_ref": self.artifact_ref.to_dict(),
            "summary": self.summary,
            "created_by": self.created_by,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactNode":
        return cls(
            node_id=data["node_id"],
            type=ArtifactNodeType(data["type"]),
            artifact_ref=ArtifactRef.from_dict(data["artifact_ref"]),
            summary=data.get("summary", ""),
            created_by=data.get("created_by", "system"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ArtifactEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    type: ArtifactEdgeType
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactEdge":
        return cls(
            edge_id=data["edge_id"],
            from_node_id=data["from_node_id"],
            to_node_id=data["to_node_id"],
            type=ArtifactEdgeType(data["type"]),
            summary=data.get("summary", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ArtifactGraph:
    work_id: str
    nodes: List[ArtifactNode] = field(default_factory=list)
    edges: List[ArtifactEdge] = field(default_factory=list)
    graph_id: str = field(default_factory=lambda: f"graph_{uuid4().hex[:12]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def source_of_truth_node(self) -> Optional[ArtifactNode]:
        for node in self.nodes:
            if node.is_source_of_truth:
                return node
        return None

    def validate(self) -> None:
        """Validate the artifact graph constraints to enforce machine_spec as source of truth.

        1. Single source of truth: If the graph contains any projection or derived node,
           it must contain exactly one machine_spec node.
        2. Traceability: Every projection or derived node must be connected to the
           machine_spec node.
        3. No reverse dependency: The machine_spec cannot have a derives_from edge
           pointing to any projection or derived node.
        """
        spec_nodes = [node for node in self.nodes if node.is_source_of_truth]
        
        project_or_derived_types = {
            ArtifactNodeType.HUMAN_BRIEF,
            ArtifactNodeType.OPTIONAL_PRD,
            ArtifactNodeType.OPTIONAL_MANUAL,
            ArtifactNodeType.AGENT_PACKAGE,
            ArtifactNodeType.ACCEPTANCE_PROTOCOL,
            ArtifactNodeType.REVIEW_RESULT,
            ArtifactNodeType.REVIEW_CHECKLIST,
            ArtifactNodeType.TRACEABILITY_MAP,
            ArtifactNodeType.MACHINE_SPEC
        }
        
        has_project_or_derived = any(node.type in project_or_derived_types for node in self.nodes)
        
        if has_project_or_derived:
            if len(spec_nodes) != 1:
                raise ArtifactGraphValidationError(
                    f"ArtifactGraph must contain exactly one machine_spec node when containing "
                    f"projections or derived artifacts, but found {len(spec_nodes)}."
                )
            
            spec_node = spec_nodes[0]
            spec_node_id = spec_node.node_id
            
            # Compute connectivity using undirected BFS
            from collections import defaultdict
            adj = defaultdict(list)
            for edge in self.edges:
                adj[edge.from_node_id].append(edge.to_node_id)
                adj[edge.to_node_id].append(edge.from_node_id)
                
            visited = {spec_node_id}
            queue = [spec_node_id]
            while queue:
                curr = queue.pop(0)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
                        
            # Ensure all projection or derived nodes are connected to the machine_spec
            target_types = project_or_derived_types - {ArtifactNodeType.MACHINE_SPEC}
            for node in self.nodes:
                if node.type in target_types and node.node_id not in visited:
                    raise ArtifactGraphValidationError(
                        f"Artifact node '{node.node_id}' of type '{node.type.value}' "
                        f"is disconnected from the machine_spec source of truth."
                    )
                    
            # Prevent reverse derives_from dependencies
            projection_node_ids = {node.node_id for node in self.nodes if node.type in target_types}
            for edge in self.edges:
                if edge.type == ArtifactEdgeType.DERIVES_FROM:
                    if edge.from_node_id == spec_node_id and edge.to_node_id in projection_node_ids:
                        to_node = next(n for n in self.nodes if n.node_id == edge.to_node_id)
                        raise ArtifactGraphValidationError(
                            f"Edge '{edge.edge_id}' is invalid because the source of truth "
                            f"cannot derive from projection/derived node '{to_node.node_id}' "
                            f"of type '{to_node.type.value}'."
                        )


    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "work_id": self.work_id,
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactGraph":
        return cls(
            graph_id=data.get("graph_id", f"graph_{uuid4().hex[:12]}"),
            work_id=data["work_id"],
            nodes=[ArtifactNode.from_dict(item) for item in data.get("nodes", [])],
            edges=[ArtifactEdge.from_dict(item) for item in data.get("edges", [])],
            metadata=dict(data.get("metadata", {})),
        )
