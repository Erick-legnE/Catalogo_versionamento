# Deployment, backup, and rollback

## Start

From the project folder, use the Python installation that has the project
requirements installed:

```powershell
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

For a production host, terminate TLS at a managed reverse proxy and set
`AUTOMACAO_HTTPS=1`. Keep `AUTOMACAO_STORAGE_DIR` on a protected data volume.

## Backup

Back up these folders together, retaining timestamps:

- `server_data/solicitacoes/` - generated fichas, uploaded art, manifests.
- `docs/data/` - reference, color, and hole-pattern source data.
- `versions/` - tested Blender scripts and `.blend` comparison artifacts.

Validate a backup by opening one `manifest.json`, its Ficha PDF, and one
versioned `.blend` on a non-production machine.

## Rollback

1. Stop the service.
2. Keep a copy of the current deployment folder and data folder.
3. Restore the prior code revision and the matching `server_data` backup.
4. Start the service locally and check `/api/health` before reopening access.
5. Record the reason, time, operator, prior revision, and restored revision in
   the operational change log.

Never overwrite historical `versions/` artifacts during a rollback; they are
used for geometry and texture comparisons.
