# Hangarin

Hangarin is a Django task manager for a shared team workspace. Signed-in users can
manage tasks, priorities, categories, notes, and subtasks. Staff users can also
manage the same five models in Django Admin.

This is a separate project from PSUSphere. It uses Hangarin branding, its own
database, public username/password registration, and optional Google and GitHub
login through django-allauth. Every public signup creates a regular user. Public
pages never offer an administrator role.

## What the project contains

The five assignment models are:

- `Priority`: task importance, such as `high` or `critical`.
- `Category`: task grouping, such as `Work` or `School`.
- `Task`: title, description, deadline, status, priority, and category.
- `Note`: text attached to one task.
- `SubTask`: a smaller action attached to one parent task.

All five models inherit created and updated timestamps from an abstract
`BaseModel`. Priority and Category deletion is protected while a Task uses them.
Deleting a Task also deletes its related Notes and SubTasks.

Important folders:

```text
hangarin/                 Django project settings, root URLs, WSGI, and ASGI
tasks/                    Models, Admin, forms, views, URLs, seed command, tests
templates/                Login, dashboard, list, form, detail, and error pages
static/tasks/             Hangarin CSS, JavaScript, and favicon source files
requirements.txt          Exact Python dependency versions
.env.example              Safe environment-variable example
```

## Install as a Progressive Web App

Hangarin uses `django-pwa` for its web manifest and service-worker route. On
HTTPS (or local `localhost`), open the site in a supporting browser and choose
**Install app** or **Add to Home Screen** from the browser menu. The app uses
Hangarin's navy-and-gold icons and opens in a standalone window.

When offline, Hangarin shows a branded reconnect page. Tasks, notes, and
account pages are **not** saved for offline viewing or editing because this is
a shared workspace and those pages may contain private, changing data. Changes
made by another user appear after you reconnect and reload.

To verify the PWA after deployment, open `/manifest.json`, `/serviceworker.js`,
and `/offline/` on the hosted site. In browser developer tools, check
**Application → Manifest** and **Application → Service workers**, then turn on
offline mode and open a task page: the offline page should appear without
displaying cached task data. Re-enable the network afterward. After changing
the precached asset list or files, increment `CACHE_NAME` in
`static/tasks/js/serviceworker.js`, run `collectstatic`, and reload the web app.

## Local setup on Windows

These steps start from a clean checkout and use Python 3.13.

1. Clone the repository and enter it:

   ```powershell
   git clone https://github.com/<github-account>/<repository>.git Hangarin
   cd Hangarin
   ```

2. Confirm Python 3.13 is available:

   ```powershell
   py -3.13 --version
   ```

3. Create and activate the virtual environment:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, allow scripts only for the current terminal,
   then activate again:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

4. Install the exact dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   python -m pip check
   ```

5. Create the local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

   The copied values are for local development only. Never commit `.env`.

6. Create the database tables and an administrator:

   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   ```

7. Start Django:

   ```powershell
   python manage.py runserver
   ```

8. Open `http://127.0.0.1:8000/admin/` and sign in as the superuser.

9. Manually add these exact lookup values in Admin before generating demo data:

   - Priorities: `high`, `medium`, `low`, `critical`, `optional`
   - Categories: `Work`, `School`, `Personal`, `Finance`, `Projects`

10. Return to the terminal, stop the server with `Ctrl+C`, and generate the
    deterministic demo records:

    ```powershell
    python manage.py create_initial_data
    ```

    The first successful run creates 10 Tasks, 10 Notes, and 20 SubTasks. Running
    it again leaves the existing data unchanged. The command also refuses to run
    if only part of the required lookup data exists.

11. Start the server again and open `http://127.0.0.1:8000/`:

    ```powershell
    python manage.py runserver
    ```

Open `http://127.0.0.1:8000/accounts/signup/` to create a regular user. Every
active signed-in user works with the same shared task dataset; this is not a
private per-user task list.

The first administrator must be created with `python manage.py createsuperuser`.
Only an existing superuser can create, promote, or change staff and superuser
accounts in Django Admin. A public registration or social login can never create
an administrator.

## Optional Google and GitHub login

Local username registration works without OAuth credentials. If a provider's two
environment values are empty, Hangarin hides that provider instead of showing a
broken button.

Create separate OAuth applications for local development and production. Never
reuse secrets in source code or commit them to Git.

For the local Google OAuth web application, add these values in Google Cloud:

```text
Authorized JavaScript origin: http://127.0.0.1:8000
Authorized redirect URI:      http://127.0.0.1:8000/accounts/google/login/callback/
```

For the local GitHub OAuth application, use:

```text
Homepage URL:                   http://127.0.0.1:8000
Authorization callback URL:    http://127.0.0.1:8000/accounts/github/login/callback/
```

Put the resulting values in the untracked local `.env` file:

```dotenv
GOOGLE_OAUTH_CLIENT_ID=<local-google-client-id>
GOOGLE_OAUTH_CLIENT_SECRET=<local-google-client-secret>
GITHUB_OAUTH_CLIENT_ID=<local-github-client-id>
GITHUB_OAUTH_CLIENT_SECRET=<local-github-client-secret>
```

Restart `runserver` after changing `.env`. Provider buttons start OAuth through a
CSRF-protected POST. Hangarin does not store provider tokens and does not silently
merge a social identity into an existing local account by matching email.

## Everyday local commands

From the repository folder:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

Stop the server with `Ctrl+C`. Leave the virtual environment with:

```powershell
deactivate
```

## Verification

Run these checks before every GitHub push or deployment:

```powershell
python --version
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
node --test tasks/tests/serviceworker.test.cjs
python manage.py collectstatic --noinput --clear
git diff --check
git status --short
```

Expected results:

- Python reports version 3.13.
- Django reports no system-check issues and no model changes.
- All tests pass from a fresh test database.
- Node.js runs the service-worker behavior tests (Django does not discover `.cjs` tests).
- Static files collect into the ignored `staticfiles/` folder.
- `git diff --check` reports no whitespace errors.
- `.env`, `.venv`, `db.sqlite3`, and `staticfiles/` do not appear in Git status.

## GitHub handoff

This checkout does not assume a particular GitHub repository. Create an empty
repository on GitHub, then connect it without placing credentials in source code:

```powershell
git remote -v
git remote add origin https://github.com/<github-account>/<repository>.git
git remote -v
git push -u origin feat/hangarin-task-manager
```

If `origin` already exists, do not add it again. Confirm that it points to the
correct Hangarin repository. Open a pull request from
`feat/hangarin-task-manager` into `main`, review the checks, and merge it. Deploy
the reviewed `main` revision rather than editing production code directly.

For a classroom submission, provide both:

- the GitHub repository URL, such as
  `https://github.com/<github-account>/<repository>`;
- the public application URL, such as
  `https://<username>.pythonanywhere.com`.

Do not submit the private PythonAnywhere dashboard or Web-tab URL.

## PythonAnywhere deployment

Replace every `<username>`, `<hostname>`, and GitHub placeholder below. Keep the
repository folder named `Hangarin` so the documented absolute paths match.

### 1. Preflight

1. In PythonAnywhere, open **Account > System image**. Use an image that provides
   Python 3.13. The current official PythonAnywhere table lists Python 3.13 on the
   `innit` image.
2. Start a new Bash console and verify the runtime and SQLite library:

   ```bash
   python3.13 --version
   python3.13 -c "import sqlite3; print(sqlite3.sqlite_version)"
   ```

   Stop if Python is not 3.13 or SQLite is older than 3.37. Changing the account's
   system image can change installed packages, so record the existing setup first.
3. Record the Git revision that passed local verification:

   ```powershell
   git rev-parse HEAD
   ```

### 2. Upload the reviewed source

In the PythonAnywhere Bash console:

```bash
cd /home/<username>
git clone --branch main --single-branch https://github.com/<github-account>/<repository>.git Hangarin
cd /home/<username>/Hangarin
git rev-parse HEAD
```

The printed revision must match the reviewed revision. For a private repository,
configure a GitHub deploy key or other approved authentication first; do not put a
GitHub token in the clone URL.

### 3. Create the Python 3.13 virtual environment

```bash
mkvirtualenv hangarin-venv --python=python3.13
cd /home/<username>/Hangarin
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

The virtual environment path will normally be:

```text
/home/<username>/.virtualenvs/hangarin-venv
```

### 4. Create the production environment file

Generate a secret without putting the secret itself in shell history:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

In the PythonAnywhere **Files** editor, create
`/home/<username>/Hangarin/.env` with these values:

```dotenv
DJANGO_ENV=production
DJANGO_SECRET_KEY=<paste-the-generated-secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<hostname>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<hostname>
DJANGO_ENABLE_HSTS=False
HANGARIN_ALLOW_PRODUCTION_SEED=False
GOOGLE_OAUTH_CLIENT_ID=<production-google-client-id>
GOOGLE_OAUTH_CLIENT_SECRET=<production-google-client-secret>
GITHUB_OAUTH_CLIENT_ID=<production-github-client-id>
GITHUB_OAUTH_CLIENT_SECRET=<production-github-client-secret>
```

For the free PythonAnywhere hostname, `<hostname>` is normally
`<username>.pythonanywhere.com`. `DJANGO_ALLOWED_HOSTS` has no scheme;
`DJANGO_CSRF_TRUSTED_ORIGINS` must include `https://`.

Restrict the file to the deployment account:

```bash
chmod 600 /home/<username>/Hangarin/.env
```

Hangarin loads this same untracked file from both `hangarin/settings.py` and
`hangarin/wsgi.py`, so Web requests and management commands use the same values.
Create production OAuth applications with these exact HTTPS values:

```text
Google authorized JavaScript origin: https://<hostname>
Google authorized redirect URI:      https://<hostname>/accounts/google/login/callback/
GitHub homepage URL:                  https://<hostname>
GitHub callback URL:                  https://<hostname>/accounts/github/login/callback/
```

Do not include a trailing path in the origin/homepage value. Keep the trailing
slash on both callback URLs. If only one value in a provider pair is present,
production startup fails intentionally instead of exposing a half-configured
login button.

### 5. Prepare the database

```bash
cd /home/<username>/Hangarin
workon hangarin-venv
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

Do not copy a local development database into production. On an existing release,
complete the backup procedure below before `git pull` or `migrate`.

### 6. Configure the Web app

1. Open the PythonAnywhere **Web** tab.
2. Create the Web app with **Manual configuration**, not the Django wizard.
3. Select Python 3.13.
4. In **Code**, set both fields to:

   ```text
   Source code:      /home/<username>/Hangarin
   Working directory: /home/<username>/Hangarin
   ```

5. In **Virtualenv**, enter:

   ```text
   /home/<username>/.virtualenvs/hangarin-venv
   ```

6. Open the linked `/var/www/<hostname-with-underscores>_wsgi.py` file and replace
   its sample code with:

   ```python
   import os
   import sys

   project_path = "/home/<username>/Hangarin"
   if project_path not in sys.path:
       sys.path.insert(0, project_path)

   os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hangarin.settings")

   from hangarin.wsgi import application
   ```

7. In **Static files**, add exactly:

   ```text
   URL:       /static/
   Directory: /home/<username>/Hangarin/staticfiles
   ```

8. Save the WSGI file and click **Reload**.

### 7. Complete first-launch data setup

Open `https://<hostname>/admin/` and sign in as the superuser. Manually create the
five exact Priority values and five exact Category values listed in the local
setup section.

Production demo generation is disabled by default. If the professor requires
demo records and this is a reviewed, empty first launch:

1. Back up the database using the next section.
2. Temporarily change only this `.env` line:

   ```dotenv
   HANGARIN_ALLOW_PRODUCTION_SEED=True
   ```

3. Run:

   ```bash
   cd /home/<username>/Hangarin
   workon hangarin-venv
   python manage.py create_initial_data
   ```

4. Immediately change the value back to `False` and reload the Web app.

Never use the seed command to reset or overwrite a live dataset.

### 8. Verify HTTPS, then enable HSTS

Visit the HTTPS site first. Confirm that login, static files, and redirects work.
The free `<username>.pythonanywhere.com` hostname already has a certificate. If a
custom domain is used, configure its certificate before forcing HTTPS.

Before HSTS is enabled, this command should report only Django's expected HSTS
warning `security.W004`:

```bash
python manage.py check --deploy
```

After the complete HTTPS smoke test succeeds, set this in `.env`:

```dotenv
DJANGO_ENABLE_HSTS=True
```

Reload, then require a completely clean deployment check:

```bash
python manage.py check --deploy --fail-level WARNING
```

Enable PythonAnywhere's **Force HTTPS** switch only after HTTPS itself works, then
reload and confirm there is no redirect loop. HSTS is intentionally delayed
because browsers remember it for a long time.

### 9. Hosted smoke test

Use a clearly named temporary record and avoid changing real shared data.

1. Open `https://<hostname>/static/tasks/css/hangarin.css` directly. It must return
   CSS, not a 404 page.
2. In a private browser window, open `https://<hostname>/tasks/`. It must redirect
   to the styled Hangarin login page.
3. Create one temporary account through **Create account**. Confirm it is a
   regular user and that `/admin/` refuses access.
4. Submit one invalid login and confirm the error is generic.
5. Test each configured Google and GitHub button. Confirm the provider returns to
   the exact HTTPS callback and the resulting account is a regular user.
6. Sign in and confirm the dashboard, overdue/upcoming queues, and totals render.
7. On Tasks, combine a search, status, priority, category, ordering, and Next/Last
   pagination. Confirm the active choices remain selected.
8. Submit an Add Task form with a blank required field. Confirm the linked error
   summary appears and no record is created.
9. Create, view, edit, and delete one task named
   `Deployment smoke - YYYY-MM-DD`. Confirm the delete page describes child impact.
10. Open Admin as authorized staff and confirm the five domain-model sections.
    Sign in as a superuser to confirm User and Group privilege administration.
11. Open a missing URL such as `/definitely-missing/` and confirm the branded 404.
12. Log out using the Log out button. A direct GET to `/accounts/logout/` must not
    end a session.
13. In browser developer tools, confirm session and CSRF cookies are Secure,
    HttpOnly, and SameSite=Lax.
14. Review PythonAnywhere access, error, and server logs. There must be no new 5xx,
    CSRF, static-file, import, host, or database-lock errors.

Review the logs again after 15 minutes, one hour, and the next day.

## Backup before an update

For an existing deployment, temporarily disable the Web app or enable its
password protection so no user can write during the backup and migration window.
Then run these commands in a Bash console:

```bash
cd /home/<username>/Hangarin
workon hangarin-venv
HANGARIN_RELEASE=$(date +%Y%m%d-%H%M%S)
HANGARIN_BACKUP_DIR="/home/<username>/hangarin-backups/$HANGARIN_RELEASE"
mkdir -p "$HANGARIN_BACKUP_DIR"
git rev-parse HEAD > "$HANGARIN_BACKUP_DIR/revision.txt"
python -m pip freeze > "$HANGARIN_BACKUP_DIR/installed-requirements.txt"
python manage.py showmigrations > "$HANGARIN_BACKUP_DIR/migrations.txt"
python manage.py shell -c "from tasks.models import Category, Note, Priority, SubTask, Task; print({'priorities': Priority.objects.count(), 'categories': Category.objects.count(), 'tasks': Task.objects.count(), 'notes': Note.objects.count(), 'subtasks': SubTask.objects.count()})" > "$HANGARIN_BACKUP_DIR/counts.txt"
sqlite3 db.sqlite3 ".backup '$HANGARIN_BACKUP_DIR/db.sqlite3'"
sqlite3 "$HANGARIN_BACKUP_DIR/db.sqlite3" "PRAGMA integrity_check;"
sha256sum .env > "$HANGARIN_BACKUP_DIR/env.sha256"
cp requirements.txt "$HANGARIN_BACKUP_DIR/requirements.txt"
```

The integrity check must print `ok`. Keep backups outside the repository and
outside `staticfiles/`. The checksum records the configuration version without
copying secrets into the release bundle.

Now fetch and verify the reviewed release before changing the database:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git rev-parse HEAD
python -m pip install -r requirements.txt
python -m pip check
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput --clear
```

Reload and complete the hosted smoke test before re-enabling normal access.

## Rollback

Rollback if a runtime, dependency, migration, deployment check, HTTPS, static,
authentication, CRUD, count, or log check fails.

1. Keep the Web app disabled or password-protected.
2. Note the failed revision and preserve its database for investigation.
3. Switch to the revision saved in the backup bundle:

   ```bash
   cd /home/<username>/Hangarin
   workon hangarin-venv
   git switch --detach <revision-from-revision.txt>
   python -m pip install -r requirements.txt
   mv db.sqlite3 db.failed-$(date +%Y%m%d-%H%M%S).sqlite3
   cp /home/<username>/hangarin-backups/<release>/db.sqlite3 db.sqlite3
   sqlite3 db.sqlite3 "PRAGMA integrity_check;"
   python manage.py migrate
   python manage.py collectstatic --noinput --clear
   python manage.py check
   ```

4. Confirm `.env` still matches the saved checksum and intended hostname. Rotate
   the secret and invalidate sessions if the secret may have been exposed.
5. Reload the Web app and repeat the complete hosted smoke test.
6. Re-enable access only after counts, functionality, and logs match the known-good
   release. For the first launch, rollback means restoring the offline pre-launch
   state instead of inventing a previous application version.

## Troubleshooting

- **The page is unstyled:** rerun `collectstatic`, confirm the `/static/` mapping
  points to `/home/<username>/Hangarin/staticfiles`, reload, and open the CSS URL
  directly.
- **`ModuleNotFoundError`:** confirm the Web tab uses the Hangarin Python 3.13
  virtual environment and the WSGI `project_path` is the folder containing
  `manage.py`.
- **`DisallowedHost`:** put only the deployed hostname in
  `DJANGO_ALLOWED_HOSTS`, without `https://`.
- **CSRF failure:** put the exact HTTPS origin in
  `DJANGO_CSRF_TRUSTED_ORIGINS`, including `https://` and no path.
- **A Google or GitHub button is missing:** set both the client ID and client
  secret for that provider, then reload the Web app. One empty value hides the
  provider locally; a partial pair is rejected in production.
- **OAuth redirect mismatch:** copy the exact provider callback from the OAuth
  section, including `https://`, `/accounts/.../login/callback/`, and its trailing
  slash. Local and PythonAnywhere deployments need separate OAuth applications.
- **A regular user cannot open Admin:** this is expected. Use `createsuperuser`
  for the first administrator; only a superuser may grant later staff access.
- **Redirect loop:** verify the proxy header configuration is unchanged and avoid
  layering another proxy's HTTPS redirect over both Django and PythonAnywhere.
- **Demo command refuses to run:** create every exact lookup value first. If any
  Task, Note, or SubTask already exists, the command intentionally makes no change.
- **Unexpected server error:** open the PythonAnywhere error log first, then the
  server and access logs. Keep `DJANGO_DEBUG=False`; do not expose a traceback to
  users.

## Official deployment references

- [PythonAnywhere supported Python versions](https://help.pythonanywhere.com/pages/PythonVersions/)
- [Deploying an existing Django project](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/)
- [Django static files on PythonAnywhere](https://help.pythonanywhere.com/pages/DjangoStaticFiles/)
- [Forcing HTTPS on PythonAnywhere](https://help.pythonanywhere.com/pages/ForcingHTTPS/)
