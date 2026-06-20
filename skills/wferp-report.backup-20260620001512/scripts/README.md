# Scripts

Scripts in this folder support repeatable report tasks.

Guidelines:
- Scripts must not execute production DML or DDL.
- Scripts that query production must accept only SELECT SQL.
- Prefer explicit input and output paths.
- Save logs and manifests into the active run folder.
