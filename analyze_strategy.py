"""
Analyze Strategy Structure
Fetch and display complete strategy details for analysis
"""

import json
import os
from src.adapters.supabase_adapter import SupabaseStrategyAdapter

# Set Supabase credentials (same as used in other scripts)
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

def analyze_strategy(strategy_id: str, user_id: str):
    """Fetch and analyze strategy structure."""
    
    print("=" * 80)
    print("📋 STRATEGY ANALYSIS")
    print("=" * 80)
    print(f"Strategy ID: {strategy_id}")
    print(f"User ID: {user_id}")
    print()
    
    # Initialize adapter
    adapter = SupabaseStrategyAdapter()
    
    # Fetch strategy
    print("🔍 Fetching strategy from Supabase...")
    strategy = adapter.get_strategy(strategy_id, user_id)
    
    # Save to file for detailed analysis
    output_file = f"strategy_analysis_{strategy_id[:8]}.json"
    with open(output_file, 'w') as f:
        json.dump(strategy, f, indent=2, default=str)
    print(f"✅ Strategy saved to: {output_file}\n")
    
    # Display summary
    print("=" * 80)
    print("STRATEGY SUMMARY")
    print("=" * 80)
    print(f"Name: {strategy.get('name', 'Unknown')}")
    print(f"Description: {strategy.get('description', 'N/A')}")
    print(f"Status: {strategy.get('status', 'N/A')}")
    print()
    
    # Trading Instrument
    print("=" * 80)
    print("TRADING INSTRUMENT")
    print("=" * 80)
    tic = strategy.get('tradingInstrumentConfig', {})
    print(f"Symbol: {tic.get('symbol', 'N/A')}")
    print(f"Exchange: {tic.get('exchange', 'N/A')}")
    print(f"Timeframes: {', '.join([tf.get('timeframe', 'N/A') for tf in tic.get('timeframes', [])])}")
    print()
    
    # Indicators
    print("=" * 80)
    print("INDICATORS")
    print("=" * 80)
    indicators = strategy.get('indicators', [])
    if indicators:
        for idx, ind in enumerate(indicators, 1):
            print(f"{idx}. {ind.get('name', 'N/A')} (Type: {ind.get('type', 'N/A')})")
            params = ind.get('params', {})
            if params:
                print(f"   Params: {params}")
    else:
        print("No indicators configured")
    print()
    
    # Nodes
    print("=" * 80)
    print("NODE STRUCTURE")
    print("=" * 80)
    nodes = strategy.get('nodes', [])
    print(f"Total Nodes: {len(nodes)}\n")
    
    for node in nodes:
        node_id = node.get('id', 'N/A')
        node_type = node.get('type', 'N/A')
        label = node.get('label', 'N/A')
        
        print(f"\n{'='*60}")
        print(f"NODE: {label} ({node_type})")
        print(f"{'='*60}")
        print(f"ID: {node_id}")
        
        # Display type-specific data
        if node_type == 'StartNode':
            print(f"Symbol: {node.get('tradingInstrumentConfig', {}).get('symbol', 'N/A')}")
            end_conditions = node.get('endConditions', {})
            if end_conditions:
                print(f"End Conditions: {json.dumps(end_conditions, indent=2)}")
        
        elif node_type == 'EntrySignalNode':
            conditions = node.get('entryConditions', [])
            print(f"Entry Conditions: {len(conditions)}")
            for idx, cond in enumerate(conditions, 1):
                print(f"  {idx}. {cond.get('condition', 'N/A')}")
        
        elif node_type == 'EntryNode':
            positions = node.get('positions', [])
            print(f"Positions: {len(positions)}")
            for idx, pos in enumerate(positions, 1):
                print(f"\n  Position {idx}:")
                print(f"    VPI: {pos.get('vpi', 'N/A')}")
                print(f"    Transaction Type: {pos.get('transactionType', 'N/A')}")
                print(f"    Quantity Type: {pos.get('quantityType', 'N/A')}")
                print(f"    Lots: {pos.get('lots', 'N/A')}")
                
                # Option details
                option_details = pos.get('optionDetails', {})
                if option_details:
                    print(f"    Option Type: {option_details.get('optionType', 'N/A')}")
                    print(f"    Strike Type: {option_details.get('strikeType', 'N/A')}")
                    print(f"    Strike Value: {option_details.get('strikeValue', 'N/A')}")
                    print(f"    Expiry: {option_details.get('expiry', 'N/A')}")
        
        elif node_type == 'ExitSignalNode':
            conditions = node.get('exitConditions', [])
            print(f"Exit Conditions: {len(conditions)}")
            for idx, cond in enumerate(conditions, 1):
                print(f"  {idx}. {cond.get('condition', 'N/A')}")
        
        elif node_type == 'ExitNode':
            exit_config = node.get('exitConfig', {})
            print(f"Target Position VPI: {exit_config.get('targetPositionVpi', 'N/A')}")
            print(f"Exit Mode: {exit_config.get('exitMode', 'N/A')}")
            
        # Node Variables
        variables = node.get('nodeVariables', [])
        if variables:
            print(f"\nNode Variables: {len(variables)}")
            for var in variables:
                print(f"  - {var.get('name', 'N/A')}: {var.get('value', 'N/A')}")
        
        # Connections
        connections = node.get('connections', [])
        if connections:
            print(f"\nConnections: {len(connections)}")
            for conn in connections:
                target_node = next((n for n in nodes if n['id'] == conn['targetNodeId']), None)
                target_label = target_node.get('label', 'Unknown') if target_node else 'Unknown'
                print(f"  → {target_label} ({conn.get('targetNodeId', 'N/A')})")
    
    print("\n" + "=" * 80)
    print("✅ Analysis Complete!")
    print("=" * 80)
    print(f"\nFull strategy JSON saved to: {output_file}")
    print("You can review the complete structure there.\n")
    
    return strategy


if __name__ == "__main__":
    # Analyze the specific strategy
    strategy_id = "4a7a1a31-e209-4b23-891a-3899fb8e4c28"
    user_id = "user_2yfjTGEKjL7XkklQyBaMP6SN2Lc"
    
    strategy = analyze_strategy(strategy_id, user_id)
