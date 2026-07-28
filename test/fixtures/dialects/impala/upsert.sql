UPSERT [SHUFFLE] INTO TABLE db.t1 (col1)
  SELECT col1 FROM db.src;

UPSERT INTO db.t1 VALUES (1, 'a');

UPSERT INTO target_table SELECT id, name FROM source_table;

UPSERT INTO target_table (id, name) VALUES (1, 'abc');
