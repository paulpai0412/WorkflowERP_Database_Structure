# SQL Safety

Production SQL Server access is read-only.

Allowed:
- SELECT queries.
- SELECT TOP smoke tests.
- SELECT-only schema probes such as `SELECT TOP 0 * FROM object`.

Forbidden against production:
- INSERT, UPDATE, DELETE, MERGE, TRUNCATE.
- DROP, ALTER, CREATE.
- EXEC, stored procedures, and procedure calls.
- Transactional mutation, temp-table mutation, or side-effect queries.

Before execution, validate the statement begins with SELECT or WITH and contains no forbidden tokens outside comments or string literals.
