# Raw Block Policy

Raw blocks are verbatim evidence sections used for auditability.

Allowed raw blocks:
- Final SELECT SQL.
- Source inventory.
- Validator summaries.
- Data preview snippets.

Do not include secrets, credentials, or full connection strings with sensitive fields. Mask values if needed. Never include DML or DDL as executable instructions.
