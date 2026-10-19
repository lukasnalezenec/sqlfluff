ALTER TABLE db.old_table RENAME TO db.new_table;

ALTER TABLE t1 ADD COLUMNS (c1 INT, c2 STRING);

ALTER TABLE t1 SET CACHED IN 'default_pool' WITH REPLICATION = 3;

ALTER TABLE t1 RECOVER PARTITIONS;

alter table db.t drop partition (k = 'v');

alter table db.t drop if exists partition (k = 'v');

alter table db.t drop partition (k = 1) purge;

alter table db.t add partition (k = 1);

alter table db.t add if not exists partition (k = 'v');

alter table db.t add if not exists range partition '2021-01' <= values < '2022-01';
