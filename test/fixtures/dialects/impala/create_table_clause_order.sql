-- TBLPROPERTIES before LOCATION is invalid Impala, but it must parse so
-- rule IM02 can report the clause-order violation.
CREATE EXTERNAL TABLE db.staging (
    id INT
)
STORED AS PARQUET
TBLPROPERTIES ('transactional'='true')
LOCATION '/data/staging';

CREATE TABLE db.kudu_late (
    id INT PRIMARY KEY
)
TBLPROPERTIES ('k'='v')
STORED AS KUDU;
