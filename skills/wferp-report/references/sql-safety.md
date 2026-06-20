# SQL Safety

只允許 read-only SELECT。禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`EXEC`、`MERGE`、`TRUNCATE`、`xp_`、SQL comments、multi statement、`SELECT INTO`。先做本地 safety validation，再要求使用者確認，再進 DB execution。
