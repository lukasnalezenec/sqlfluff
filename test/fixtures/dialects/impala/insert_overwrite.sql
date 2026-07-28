INSERT OVERWRITE TABLE db.foo SELECT col1, col2 FROM db.foo2;

INSERT OVERWRITE TABLE db.foo PARTITION (col1, col2) SELECT col1, col2, col3 FROM db.foo2;

INSERT OVERWRITE TABLE db.foo PARTITION (col1=1, col2='a') SELECT col3 FROM db.foo2;

INSERT OVERWRITE TABLE db.foo [SHUFFLE] SELECT col1, col2 FROM db.foo2;

INSERT OVERWRITE TABLE db.foo [NOSHUFFLE] SELECT col1, col2 FROM db.foo2;

INSERT OVERWRITE TABLE db.foo IF NOT EXISTS SELECT col1, col2 FROM db.foo2;

INSERT OVERWRITE TABLE target_table PARTITION (partition_code = '202601') SELECT id, name FROM source_table;

WITH src AS (SELECT id, name FROM source_table) INSERT OVERWRITE TABLE target_table PARTITION (partition_code = '202601') SELECT id, name FROM src;

INSERT OVERWRITE TABLE target_table PARTITION (partition_code = '202601') WITH src AS (SELECT id, name FROM source_table) SELECT id, name FROM src;
