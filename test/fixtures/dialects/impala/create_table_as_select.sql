CREATE TABLE db.ctas_table
  PARTITIONED BY (year INT)
  STORED AS PARQUET
  CACHED IN 'default_pool'
AS SELECT * FROM db.src;

CREATE TABLE db.foo
AS SELECT col1, col2
FROM db.foo1;

CREATE TABLE db.foo
AS SELECT (col1, col2)
FROM db.foo1;

CREATE EXTERNAL TABLE IF NOT EXISTS db.foo
    PARTITIONED BY (col1)
    SORT BY (col2)
    COMMENT 'table_comment'
    ROW FORMAT DELIMITED
    WITH SERDEPROPERTIES ('key1'='value1', 'key2'='value2')
    STORED AS PARQUET
    LOCATION 'hdfs://host/path/to/location'
    TBLPROPERTIES ('key1'='value1', 'key2'='value2')
AS
    SELECT col1, col2, col3, col4
    FROM db.baz;

CREATE TABLE t_ctas STORED AS PARQUET AS SELECT id, name FROM source_table;

CREATE TABLE t_ctas_part PARTITIONED BY (partition_code) STORED AS PARQUET AS SELECT id, name, partition_code FROM source_table;
