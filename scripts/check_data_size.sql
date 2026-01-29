-- ClickHouse Data Size Analysis
-- Run this in your ClickHouse Cloud console

-- 1. Show all tables
SHOW TABLES;

-- 2. Get detailed size for each table
SELECT 
    table,
    sum(rows) as total_rows,
    formatReadableSize(sum(data_compressed_bytes)) as compressed_size,
    formatReadableSize(sum(data_uncompressed_bytes)) as uncompressed_size,
    round(sum(data_compressed_bytes) / sum(data_uncompressed_bytes) * 100, 2) as compression_ratio_percent
FROM system.parts
WHERE active
GROUP BY table
ORDER BY sum(data_compressed_bytes) DESC;

-- 3. Get total size across all tables
SELECT 
    'TOTAL' as summary,
    sum(rows) as total_rows,
    formatReadableSize(sum(data_compressed_bytes)) as total_compressed,
    formatReadableSize(sum(data_uncompressed_bytes)) as total_uncompressed,
    round(sum(data_compressed_bytes) / sum(data_uncompressed_bytes) * 100, 2) as compression_ratio_percent,
    sum(data_compressed_bytes) as compressed_bytes,
    sum(data_uncompressed_bytes) as uncompressed_bytes
FROM system.parts
WHERE active;

-- 4. Get date range (if you have a table with 'ts' column)
-- Replace 'your_table_name' with your actual table name
SELECT 
    min(ts) as first_date,
    max(ts) as last_date,
    dateDiff('day', min(ts), max(ts)) as total_days,
    count() as total_rows
FROM your_table_name;

-- 5. Get data size per day (to estimate daily growth)
-- Replace 'your_table_name' with your actual table name
SELECT 
    toDate(ts) as date,
    count() as rows_per_day,
    formatReadableSize(sum(length(toString(*)))) as approx_size_per_day
FROM your_table_name
GROUP BY date
ORDER BY date DESC
LIMIT 30;
