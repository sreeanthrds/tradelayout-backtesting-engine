"""
Node Manager
============

Handles node creation and graph building from strategy configuration.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class NodeManager:
    """
    Manages node creation and graph building.
    
    Responsibilities:
    - Create node instances from strategy config
    - Build parent-child relationships (graph)
    - Initialize node states
    """
    
    def __init__(self):
        """Initialize node manager."""
        self.nodes: Dict[str, Any] = {}
        logger.info("🔗 Node Manager initialized")
    
    def create_nodes(self, strategy: Any) -> Dict[str, Any]:
        """
        Create all node instances from strategy configuration.
        
        Args:
            strategy: Strategy object with config
        
        Returns:
            Dictionary of {node_id: node_instance}
        """
        logger.info("🏗️  Creating nodes from strategy...")
        logger.info(f"   📋 Found {len(strategy.nodes)} nodes in strategy config")
        
        # Import node types
        from strategy.nodes.start_node import StartNode
        from strategy.nodes.entry_node import EntryNode
        from strategy.nodes.entry_signal_node import EntrySignalNode
        from strategy.nodes.exit_node import ExitNode
        from strategy.nodes.exit_signal_node import ExitSignalNode
        from strategy.nodes.re_entry_signal_node import ReEntrySignalNode
        from strategy.nodes.square_off_node import SquareOffNode
        
        # Create all nodes
        for node_config in strategy.nodes:
            node_id = node_config.get('id')
            node_type = node_config.get('type')
            node_data = node_config.get('data', {})
            
            node = self._create_node(node_type, node_id, node_data)
            
            if node:
                self.nodes[node_id] = node
                logger.info(f"   ✅ Created {node_type}: {node_id}")
            elif node_type == 'strategyOverview':
                logger.info(f"   ⏭️  Skipped virtual node: {node_id}")
            else:
                logger.warning(f"   ⚠️  Unknown node type '{node_type}': {node_id}")
        
        # Build graph relationships
        self._build_graph(strategy.edges)
        
        total_nodes_in_config = len(strategy.nodes)
        nodes_created = len(self.nodes)
        nodes_skipped = total_nodes_in_config - nodes_created
        
        logger.info(f"   ✅ Created {nodes_created}/{total_nodes_in_config} nodes ({nodes_skipped} skipped/virtual)")
        if nodes_skipped > 0:
            logger.info(f"   ℹ️  Skipped nodes are likely UI-only (strategyOverview) or unsupported types")
        
        return self.nodes
    
    def _create_node(self, node_type: str, node_id: str, node_data: Dict) -> Any:
        """
        Create a single node instance.
        
        Args:
            node_type: Type of node (e.g., 'startNode', 'entryNode')
            node_id: Unique node ID
            node_data: Node configuration data
        
        Returns:
            Node instance or None if type is unknown/virtual
        """
        from strategy.nodes.start_node import StartNode
        from strategy.nodes.entry_node import EntryNode
        from strategy.nodes.entry_signal_node import EntrySignalNode
        from strategy.nodes.exit_node import ExitNode
        from strategy.nodes.exit_signal_node import ExitSignalNode
        from strategy.nodes.re_entry_signal_node import ReEntrySignalNode
        from strategy.nodes.square_off_node import SquareOffNode
        
        if node_type == 'startNode' or node_type == 'start':
            return StartNode(node_id=node_id, data=node_data)
        elif node_type == 'entrySignalNode':
            return EntrySignalNode(node_id=node_id, data=node_data)
        elif node_type == 'entryNode' or node_type == 'entry':
            return EntryNode(node_id=node_id, data=node_data)
        elif node_type == 'reEntrySignalNode':
            return ReEntrySignalNode(node_id=node_id, data=node_data)
        elif node_type == 'exitSignalNode':
            return ExitSignalNode(node_id=node_id, data=node_data)
        elif node_type == 'exitNode' or node_type == 'exit':
            return ExitNode(node_id=node_id, data=node_data)
        elif node_type == 'squareOffNode':
            return SquareOffNode(node_id=node_id, data=node_data)
        elif node_type == 'strategyOverview':
            # Skip virtual nodes
            return None
        else:
            return None
    
    def _build_graph(self, edges: List[Dict]):
        """
        Build parent-child relationships from edges.
        
        Args:
            edges: List of edge definitions from strategy
        """
        logger.info("   Building node graph...")
        
        # Build adjacency lists
        parent_map: Dict[str, List[str]] = {}
        child_map: Dict[str, List[str]] = {}
        
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            
            if source not in child_map:
                child_map[source] = []
            child_map[source].append(target)
            
            if target not in parent_map:
                parent_map[target] = []
            parent_map[target].append(source)
        
        # Set relations for each node
        for node_id, node in self.nodes.items():
            parents = parent_map.get(node_id, [])
            children = child_map.get(node_id, [])
            node.set_relations(parents, children)
            
            if children:
                logger.info(f"      {node_id} → {children}")
        
        total_edges = sum(len(v) for v in child_map.values())
        logger.info(f"   Total edges processed: {total_edges}")
    
    def initialize_states(self, context: Dict) -> None:
        """
        Initialize node states - only Start Node is active, all others inactive.
        
        Args:
            context: Execution context
        """
        from strategy.nodes.start_node import StartNode
        
        logger.info("   Initializing node states (only Start Node active)...")
        
        for node_id, node in self.nodes.items():
            if isinstance(node, StartNode):
                node.mark_active(context)
                logger.info(f"   ✅ Start Node activated: {node_id}")
            else:
                node.mark_inactive(context)
        
        node_states = context.get('node_states', {})
        logger.info(f"   Node states initialized: {len(node_states)} nodes")
