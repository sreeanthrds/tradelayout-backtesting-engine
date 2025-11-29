"""
Strategy Executor - Orchestrates strategy execution

Manages nodes, processes ticks, handles order callbacks.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import asyncio

from interfaces.data_reader import DataReaderInterface
from interfaces.data_writer import DataWriterInterface
from interfaces.order_placer import OrderPlacerInterface
from strategy.expression_evaluator import ExpressionEvaluator
from strategy.nodes import BaseNode, EntryNode, ExitNode, ConditionNode, NodeStatus


logger = logging.getLogger(__name__)


class StrategyExecutor:
    """
    Executes trading strategies.
    
    Features:
    - Node orchestration
    - Tick processing
    - Order management
    - State management
    - Three-state node handling
    """
    
    def __init__(
        self,
        user_id: str,
        strategy_id: str,
        strategy_config: Dict[str, Any],
        data_reader: DataReaderInterface,
        data_writer: DataWriterInterface,
        order_placer: OrderPlacerInterface
    ):
        """Initialize strategy executor."""
        self.user_id = user_id
        self.strategy_id = strategy_id
        self.strategy_config = strategy_config
        self.data_reader = data_reader
        self.data_writer = data_writer
        self.order_placer = order_placer
        
        # Expression evaluator
        self.expression_evaluator = ExpressionEvaluator(data_reader)
        
        # Nodes
        self.nodes: Dict[str, BaseNode] = {}
        self.active_nodes: List[str] = []
        
        # State
        self.is_running = False
        self.tick_count = 0
    
    async def initialize(self):
        """Initialize strategy - create nodes."""
        logger.info(f"Initializing strategy {self.strategy_id}")
        
        # Create nodes from config
        nodes_config = self.strategy_config.get('nodes', [])
        
        for node_config in nodes_config:
            node = await self._create_node(node_config)
            if node:
                self.nodes[node.node_id] = node
        
        # Set start node as active
        start_node_id = self.strategy_config.get('start_node')
        if start_node_id:
            self.active_nodes.append(start_node_id)
            logger.info(f"Start node set: {start_node_id}")
        else:
            # No start node - activate all entry nodes
            logger.warning("No start_node in config - activating all entry nodes")
            for node_id, node in self.nodes.items():
                if 'entry' in node.node_type.lower():
                    self.active_nodes.append(node_id)
                    logger.info(f"Activated entry node: {node_id}")
        
        # Load saved states
        await self._load_states()
        
        logger.info(f"Strategy initialized with {len(self.nodes)} nodes, {len(self.active_nodes)} active")
    
    async def _create_node(self, node_config: Dict[str, Any]) -> Optional[BaseNode]:
        """Create a node from configuration."""
        try:
            node_id = node_config.get('id')
            node_type = node_config.get('type')
            
            # Common parameters
            common_params = {
                'node_id': node_id,
                'node_type': node_type,
                'config': node_config,
                'data_reader': self.data_reader,
                'data_writer': self.data_writer,
                'expression_evaluator': self.expression_evaluator,
                'user_id': self.user_id,
                'strategy_id': self.strategy_id
            }
            
            # Create node based on type (handle both old and new formats)
            node_type_lower = node_type.lower()
            
            if node_type_lower in ['entry', 'entrynode']:
                return EntryNode(
                    order_placer=self.order_placer,
                    **common_params
                )
            elif node_type_lower in ['exit', 'exitnode']:
                return ExitNode(
                    order_placer=self.order_placer,
                    **common_params
                )
            elif node_type_lower in ['condition', 'conditionnode', 'entrysignalnode', 'exitsignalnode']:
                return ConditionNode(**common_params)
            elif node_type_lower in ['start', 'startnode', 'strategyoverview']:
                # Start node and overview - no execution logic needed for backtesting
                logger.info(f"Skipping {node_type} (not needed for backtesting)")
                return None
            else:
                logger.warning(f"Unknown node type: {node_type}")
                return None
        
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            return None
    
    async def _load_states(self):
        """Load saved node states."""
        for node_id, node in self.nodes.items():
            try:
                await node.load_state()
            except Exception as e:
                logger.error(f"Error loading state for {node_id}: {e}")
    
    async def start(self):
        """Start strategy execution."""
        self.is_running = True
        logger.info(f"Strategy {self.strategy_id} started")
    
    async def stop(self):
        """Stop strategy execution."""
        self.is_running = False
        
        # Save all node states
        for node in self.nodes.values():
            await node.save_state()
        
        logger.info(f"Strategy {self.strategy_id} stopped")
    
    async def process_tick(self, tick_data: Dict[str, Any]):
        """
        Process a tick.
        
        Args:
            tick_data: Tick data with symbol, ltp, timestamp, etc.
        """
        if not self.is_running:
            return
        
        self.tick_count += 1
        
        # Process active nodes
        for node_id in list(self.active_nodes):
            node = self.nodes.get(node_id)
            if not node:
                continue
            
            # Execute node
            try:
                next_nodes = await node.execute(tick_data)
                
                # If node returned next nodes, activate them
                if next_nodes:
                    await self._activate_nodes(next_nodes)
            
            except Exception as e:
                logger.error(f"Error executing node {node_id}: {e}")
    
    async def _activate_nodes(self, node_ids: List[str]):
        """Activate nodes."""
        for node_id in node_ids:
            if node_id not in self.active_nodes:
                self.active_nodes.append(node_id)
                logger.info(f"Activated node: {node_id}")
    
    def can_shutdown(self) -> bool:
        """
        Check if strategy can safely shutdown.
        
        Returns True only if ALL nodes are INACTIVE.
        Prevents shutdown while orders are pending.
        """
        active_count = 0
        pending_count = 0
        
        for node in self.nodes.values():
            if node.is_active():
                active_count += 1
            elif node.is_pending():
                pending_count += 1
        
        if active_count > 0 or pending_count > 0:
            logger.debug(f"Cannot shutdown: {active_count} active, {pending_count} pending")
            return False
        
        return True
    
    async def get_status(self) -> Dict[str, Any]:
        """Get strategy status."""
        node_statuses = {}
        for node_id, node in self.nodes.items():
            node_statuses[node_id] = {
                'status': node.status.value,
                'visited': node.visited,
                're_entry_num': node.re_entry_num
            }
        
        return {
            'strategy_id': self.strategy_id,
            'is_running': self.is_running,
            'tick_count': self.tick_count,
            'active_nodes': self.active_nodes,
            'node_statuses': node_statuses,
            'can_shutdown': self.can_shutdown()
        }
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all positions for this strategy."""
        try:
            return await self.data_reader.get_positions(
                user_id=self.user_id,
                strategy_id=self.strategy_id
            )
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get open positions."""
        try:
            return await self.data_reader.get_positions(
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                status='OPEN'
            )
        except Exception as e:
            logger.error(f"Error getting open positions: {e}")
            return []
    
    async def calculate_pnl(self) -> float:
        """Calculate total PNL."""
        try:
            positions = await self.get_positions()
            total_pnl = sum(pos.get('pnl', 0) for pos in positions)
            return total_pnl
        except Exception as e:
            logger.error(f"Error calculating PNL: {e}")
            return 0.0
