# DB Config

This skill currently targets the user's production WFERP database connection.
Treat this connection as production unless the user explicitly provides a
verified test database.

## Attachment Evidence

- ODC attachment: `C:/Users/ivychi/util/test/css04 CHD View_Customer.odc`
- Excel attachment: `C:/Users/ivychi/util/test/1 ??_????????_CHD.XLSX`
- User-provided connection string:

```text
Provider=SQLOLEDB.1;Integrated Security=SSPI;Persist Security Info=True;User ID=IRO;Initial Catalog=CHD;Data Source=css04;Use Procedure for Prepare=1;Auto Translate=True;Packet Size=4096;Workstation ID=CPC100;Use Encryption for Data=False;Tag with column collation when possible=False
```

## Canonical Production Target

- Provider: `SQLOLEDB.1`
- Authentication: `Integrated Security=SSPI`
- User ID in workbook connection string: `IRO`
- Initial Catalog: `CHD`
- Data Source: `css04`
- Workstation ID in workbook connection string: `CPC100`
- Default source object: `[CHD].[dbo].[View_Customer]`

## SQL Safety

Production access is read-only.

Allowed against production:

- `SELECT` statements only.
- Smoke test: `SELECT TOP 1 1 AS connection_test`
- Schema probe: `SELECT TOP 0 * FROM [CHD].[dbo].[View_Customer]`

Forbidden against production:

- `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE`
- `DROP`, `ALTER`, `CREATE`
- `EXEC`, stored procedures, and procedure calls
- Transaction-changing commands or any other data-changing SQL

Local writes are allowed only for local artifacts under the run folder, such as
CSV, JSON, SQLite, and HTML report files. These writes must not be described as
production database writes.

## Verified Runtime Note

A prior SELECT-only smoke test from unsandboxed Windows PowerShell as
`CHD-TECH\ivychi` using the exact OLE DB connection string returned `1`. The
same connection may fail inside the Codex sandbox with an SSL/security-provider
error; if that happens, record the failure as environment-related instead of
changing the SQL safety rule.
