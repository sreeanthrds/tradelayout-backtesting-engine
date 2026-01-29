#!/usr/bin/env python3
"""
Check actual data size in ClickHouse Cloud
"""

import clickhouse_connect
import sys

def check_data_size():
    """Connect to ClickHouse and check actual data size."""
    
    print("🔍 Checking ClickHouse Cloud Data Size...")
    print("=" * 60)
    
    # You need to provide your credentials
    print("\n⚠️  Please provide your ClickHouse Cloud credentials:")
    host = input("Host (e.g., abc123.us-east-1.aws.clickhouse.cloud): ").strip()
    port = input("Port (default 8443): ").strip() or "8443"
    username = input("Username (default: default): ").strip() or "default"
    password = input("Password: ").strip()
    database = input("Database (default: default): ").strip() or "default"
    
    try:
        # Connect to ClickHouse
        print("\n🔄 Connecting to ClickHouse Cloud...")
        client = clickhouse_connect.get_client(
            host=host,
            port=int(port),
            username=username,
            password=password,
            database=database,
            secure=True
        )
        
        print("✅ Connected successfully!")
        print("\n" + "=" * 60)
        
        # Get all tables
        print("\n📊 Tables in database:")
        tables_query = "SHOW TABLES"
        tables = client.query(tables_query)
        
        if not tables.result_rows:
            print("❌ No tables found!")
            return
        
        print(f"Found {len(tables.result_rows)} tables:")
        for table in tables.result_rows:
            print(f"  - {table[0]}")
        
        print("\n" + "=" * 60)
        
        # Get detailed size information for each table
        print("\n📈 Detailed Size Information:")
        print("-" * 60)
        
        total_compressed = 0
        total_uncompressed = 0
        total_rows = 0
        
        for table in tables.result_rows:
            table_name = table[0]
            
            # Get table statistics
            stats_query = f"""
                SELECT 
                    '{table_name}' as table,
                    sum(rows) as total_rows,
                    formatReadableSize(sum(data_compressed_bytes)) as compressed_size,
                    formatReadableSize(sum(data_uncompressed_bytes)) as uncompressed_size,
                    sum(data_compressed_bytes) as compressed_bytes,
                    sum(data_uncompressed_bytes) as uncompressed_bytes,
                    round(sum(data_compressed_bytes) / sum(data_uncompressed_bytes) * 100, 2) as compression_ratio
                FROM system.parts
                WHERE table = '{table_name}' AND active
            """
            
            result = client.query(stats_query)
            
            if result.result_rows:
                row = result.result_rows[0]
                table, rows, compressed, uncompressed, comp_bytes, uncomp_bytes, ratio = row
                
                total_rows += rows
                total_compressed += comp_bytes
                total_uncompressed += uncomp_bytes
                
                print(f"\n📋 Table: {table}")
                print(f"   Rows: {rows:,}")
                print(f"   Compressed: {compressed}")
                print(f"   Uncompressed: {uncompressed}")
                print(f"   Compression: {ratio}%")
        
        print("\n" + "=" * 60)
        print("\n📊 TOTAL SUMMARY:")
        print("-" * 60)
        print(f"Total Rows: {total_rows:,}")
        print(f"Total Compressed: {format_bytes(total_compressed)}")
        print(f"Total Uncompressed: {format_bytes(total_uncompressed)}")
        
        if total_uncompressed > 0:
            compression_ratio = (total_compressed / total_uncompressed) * 100
            print(f"Overall Compression: {compression_ratio:.2f}%")
        
        print("\n" + "=" * 60)
        
        # Estimate load time
        print("\n⏱️  ESTIMATED LOAD TIMES:")
        print("-" * 60)
        
        # S3 download speed: ~50 MB/s (same region)
        download_time = total_compressed / (50 * 1024 * 1024)
        
        # ClickHouse import speed: ~10-20 MB/s for compressed data
        import_time = total_compressed / (15 * 1024 * 1024)
        
        # ClickHouse startup: ~15 seconds
        startup_time = 15
        
        total_time = download_time + import_time + startup_time
        
        print(f"Download from S3: {download_time:.1f} seconds")
        print(f"Import to ClickHouse: {import_time:.1f} seconds")
        print(f"ClickHouse startup: {startup_time} seconds")
        print(f"TOTAL: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        
        print("\n" + "=" * 60)
        
        # S3 cost estimate
        print("\n💰 ESTIMATED S3 COSTS:")
        print("-" * 60)
        
        # S3 Standard storage: $0.023 per GB/month
        storage_gb = total_compressed / (1024 * 1024 * 1024)
        storage_cost = storage_gb * 0.023
        
        print(f"Storage size: {storage_gb:.2f} GB")
        print(f"Monthly cost: ${storage_cost:.4f}")
        print(f"Annual cost: ${storage_cost * 12:.2f}")
        
        # Request costs (negligible)
        print(f"Request costs: ~$0.001/month (negligible)")
        
        print("\n" + "=" * 60)
        
        # Get date range
        print("\n📅 DATA RANGE:")
        print("-" * 60)
        
        for table in tables.result_rows:
            table_name = table[0]
            
            # Try to find timestamp column
            date_query = f"""
                SELECT 
                    min(ts) as first_date,
                    max(ts) as last_date,
                    dateDiff('day', min(ts), max(ts)) as days
                FROM {table_name}
                WHERE ts IS NOT NULL
            """
            
            try:
                result = client.query(date_query)
                if result.result_rows:
                    first, last, days = result.result_rows[0]
                    print(f"\n{table_name}:")
                    print(f"  First: {first}")
                    print(f"  Last: {last}")
                    print(f"  Days: {days}")
            except:
                # Table might not have 'ts' column
                pass
        
        print("\n" + "=" * 60)
        print("\n✅ Analysis complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nPlease check your credentials and try again.")
        sys.exit(1)


def format_bytes(bytes_val):
    """Format bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


if __name__ == "__main__":
    check_data_size()
