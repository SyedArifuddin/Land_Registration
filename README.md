# Land Registration App

This repository contains a Flask-based land registration application.

## Vercel deployment

### Required files
- `vercel.json` — configures Vercel to route all traffic through `api/index.py`
- `api/index.py` — entrypoint for the Flask WSGI app
- `requirements.txt` — Python dependencies
- `.vercelignore` — excludes local secrets and database artifacts

### Environment variables
Set these in Vercel dashboard before deployment:

- `DATABASE_URL` — full MySQL connection string, e.g. `mysql://user:pass@host:3306/dbname`
- or separately:
  - `DB_HOST`
  - `DB_USER`
  - `DB_PASSWORD`
  - `DB_NAME`
  - `DB_PORT`

### Notes
- The app uses MySQL and `mysql-connector-python`.
- `templates/` and `static/` are served by Flask from the deployed package.
- Local files such as `registry.db`, `passwords.txt`, and `users.json` are excluded from deployment.

### Deploy steps
1. Install Vercel CLI: `npm i -g vercel`
2. Run `vercel login`
3. From the repo folder, run `vercel`
4. When prompted, choose the current project or create a new one
5. Confirm the deployment

If Vercel does not auto-detect the Python deployment, ensure `vercel.json` is present and try `vercel --prod` again.
