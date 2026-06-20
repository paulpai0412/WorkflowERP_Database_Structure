# DB Config

Use this reference when configuring database access for `wferp-report`.

## Production Baseline From ODC

Source file:

- `C:/Users/ivychi/util/test/css04 CHD View_Customer.odc`
- `C:/Users/ivychi/util/test/1 財務_訂單報表即時分析_CHD.XLSX`

Extracted ODC values:

- Provider: `SQLOLEDB.1`
- Authentication: Windows Integrated Security / SSPI
- Data Source: `css04`
- Initial Catalog: `CHD`
- Default object context: `[CHD].[dbo].[View_Customer]`
- ODC command type: `Table`

The Excel workbook stores the same connection in `xl/connections.xml` under connection name `css04 CHD View_Customer`.

Runtime environment mapping:

```powershell
$env:DB_DRIVER = "pyodbc"
$env:DB_AUTH_MODE = "windows_domain"
$env:DB_ENV = "prod"
$env:DB_HOST = "css04"
$env:DB_PORT = "1433"
$env:DB_DATABASE = "CHD"
$env:DB_ODBC_DRIVER = "SQL Server"
```

When an OLE DB connection is needed on Windows, use this equivalent connection string:

```text
Provider=SQLOLEDB.1;Integrated Security=SSPI;Persist Security Info=True;Initial Catalog=CHD;Data Source=css04;Use Procedure for Prepare=1;Auto Translate=True;Packet Size=4096;Use Encryption for Data=False;Tag with column collation when possible=False
```

## Safety

- Treat this connection as production.
- Only execute `SELECT` statements.
- Never execute `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE`, DDL, mutating stored procedures, or transaction-changing commands.
- Do not store passwords or secrets in repo files. The ODC uses integrated authentication and does not provide a password.
- Do not embed DB connection strings or credentials in delivered HTML reports.

## Read-Only Smoke Test

Use only this shape for connection smoke testing:

```sql
SELECT TOP 1 1 AS connection_test
```

If this query cannot connect, report the connection-layer error. Do not try business-table queries until the smoke test succeeds.

## Verified Runtime Note

The production smoke test succeeds when executed from an unsandboxed Windows PowerShell process under `CHD-TECH\ivychi` with the OLE DB connection string above:

```text
SELECT TOP 1 1 AS connection_test -> 1
```

The same connection can fail inside the Codex sandbox with `[DBNETLIB][ConnectionOpen (SECCreateCredentials()).]SSL Security error.` Treat that as a sandbox/security-context failure, not as evidence that `css04` or `CHD` is unavailable.
