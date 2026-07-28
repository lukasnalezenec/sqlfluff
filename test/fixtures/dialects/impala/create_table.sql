CREATE TABLE db.foo
  (col1 integer, col2 string);

CREATE TABLE db.foo (
    col1 INT,
    col2 STRING,
    col3 DECIMAL(10,2)
) PARTITIONED BY (col4 INT);

CREATE TABLE db.kudu_t (
    id INT PRIMARY KEY,
    val STRING NOT NULL
) PARTITION BY HASH (id) PARTITIONS 4
  STORED AS KUDU;

CREATE EXTERNAL TABLE db.like_t
  LIKE PARQUET '/data/sample.parquet'
  CACHED IN 'default_pool';

CREATE EXTERNAL TABLE t_external_location (id BIGINT, name STRING) STORED AS PARQUET LOCATION '/data/test/t_external_location';

CREATE EXTERNAL TABLE t_external_full (id BIGINT, name STRING) PARTITIONED BY (partition_code STRING) STORED AS PARQUET LOCATION '/data/test/t_external_full' TBLPROPERTIES ("transactional" = "false");

CREATE TABLE t_kudu (id BIGINT, name STRING) STORED AS KUDU;

CREATE TABLE t_kudu_comment (id BIGINT, name STRING) COMMENT 'table comment' STORED AS KUDU;

CREATE TABLE t_kudu_pk (id BIGINT, business_date STRING, name STRING, PRIMARY KEY (id, business_date)) STORED AS KUDU;

CREATE TABLE t_kudu_pk_comment (id BIGINT, business_date STRING, name STRING, PRIMARY KEY (id, business_date)) COMMENT 'kudu table with primary key' STORED AS KUDU;

CREATE TABLE t_like LIKE source_table STORED AS PARQUET;

CREATE TABLE t_part_parquet (id BIGINT, name STRING) PARTITIONED BY (partition_code STRING COMMENT 'technical partition') STORED AS PARQUET;

CREATE TABLE t_part_comment_parquet (id BIGINT, name STRING) PARTITIONED BY (partition_code STRING COMMENT 'technical partition') COMMENT 'table comment' STORED AS PARQUET;

CREATE TABLE t_tblprops (id BIGINT, name STRING) STORED AS PARQUET TBLPROPERTIES ("transactional" = "false");

CREATE TABLE t_full_tail (id BIGINT, name STRING) PARTITIONED BY (partition_code STRING COMMENT 'technical partition') COMMENT 'table comment' STORED AS PARQUET TBLPROPERTIES ("transactional" = "false");
