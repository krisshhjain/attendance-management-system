# Contributing to Attendance Management System

Welcome to the team. This document defines the Git, GitHub, Docker, and development workflow for the Attendance Management System.

The goal is to keep `main` stable while allowing everyone to develop independently.

## 1. Golden Rules

1. **Nobody works directly on `main`.**
2. **Nobody pushes directly to `main`.**
3. **All development happens on branches.**
4. **Pull Requests are the only way to merge code into `main`.**
5. **Never commit passwords, API keys, `.env` files, database files, or other secrets.**
6. **Always pull the latest `main` before starting a new task.**
7. **Test your changes before opening or updating a Pull Request.**
8. **Do not modify another developer's branch unless explicitly agreed upon.**

---

## 2. Repository Structure

The GitHub repository is the shared source of truth for the project.

Each developer should have their own local clone:

```text
Developer 1 ─┐
Developer 2 ─┤
Developer 3 ─┤
Developer 4 ─┤
Developer 5 ─┤──> GitHub Repository ──> main
Developer 6 ─┤
Developer 7 ─┤
Developer 8 ─┘
```

Do not create separate repositories for individual developers.

---

## 3. Branch Structure

The `main` branch represents stable, reviewed code.

Developers should create task-specific branches from `main`.

### Branch naming convention

Use one of the following prefixes:

```text
feature/
fix/
refactor/
docs/
chore/
```

Examples:

```text
feature/login-api
feature/attendance-dashboard
feature/face-verification
feature/leave-management

fix/authentication-error
fix/attendance-duplicate-entry

refactor/attendance-service

docs/update-readme

chore/update-dependencies
```

Keep branch names short and descriptive.

---

# 4. First-Time Setup

Clone the repository:

```bash
git clone <repository-url>
cd attendance-management-system
```

Verify the remote:

```bash
git remote -v
```

Make sure you are on `main`:

```bash
git checkout main
```

Get the latest version:

```bash
git pull origin main
```

---

# 5. Starting a New Task

Always start a new task from the latest `main`.

```bash
git checkout main
git pull origin main
```

Create your branch:

```bash
git checkout -b feature/your-feature-name
```

Example:

```bash
git checkout -b feature/attendance-api
```

Confirm your branch:

```bash
git branch
```

You should see:

```text
* feature/attendance-api
  main
```

---

# 6. Working on Your Branch

Do all development work on your feature branch.

Check your changes:

```bash
git status
```

Review what changed:

```bash
git diff
```

Stage your changes:

```bash
git add .
```

Commit them:

```bash
git commit -m "Add attendance API"
```

Use clear commit messages that describe what changed.

Examples:

```text
Add employee authentication
Implement attendance creation API
Add leave request model
Fix duplicate attendance records
Update Docker configuration
Add attendance API tests
```

Avoid vague commits such as:

```text
changes
update
stuff
final
final2
working
```

---

# 7. Push Your Branch

Push your branch to GitHub:

```bash
git push -u origin feature/your-feature-name
```

After the first push, future pushes can usually be:

```bash
git push
```

---

# 8. Pull Requests

After your work is ready:

1. Push your branch to GitHub.
2. Open a Pull Request.
3. Set the target branch to `main`.
4. Explain what was changed.
5. Explain how the changes were tested.
6. Request review from another team member.

Example PR description:

```text
## What changed

- Added attendance creation API
- Added attendance validation
- Added PostgreSQL model
- Added API tests

## How it was tested

- Django tests passed
- Docker Compose started successfully
- Attendance API tested locally

## Related task

Attendance Management #12
```

Do not merge your own Pull Request unless the team's GitHub rules explicitly allow it.

At least one other team member should review and approve the Pull Request.

---

# 9. Keeping Your Branch Updated

Other developers may merge changes into `main` while you are working.

Before your Pull Request is merged, update your branch with the latest `main`.

First:

```bash
git fetch origin
```

Update local `main`:

```bash
git checkout main
git pull origin main
```

Return to your feature branch:

```bash
git checkout feature/your-feature-name
```

Merge the latest `main`:

```bash
git merge main
```

If there are no conflicts, test the project.

Then push:

```bash
git push
```

---

# 10. Resolving Merge Conflicts

If Git reports conflicts:

```text
CONFLICT (content): Merge conflict in <file>
```

Check which files have conflicts:

```bash
git status
```

Open the affected files.

Git will mark conflicts similar to:

```text
<<<<<<< HEAD
your changes
=======
changes from develop
>>>>>>> develop
```

Decide which code should remain, remove the conflict markers, and save the file.

Then:

```bash
git add .
```

Complete the merge:

```bash
git commit -m "Merge develop into feature/your-feature-name"
```

Run the application and tests.

Finally:

```bash
git push
```

The Pull Request will automatically update.

### Important

Never blindly choose "Accept Current" or "Accept Incoming" for every conflict.

Understand what both changes do before resolving the conflict.

---

# 11. Git Merge vs Rebase

The team's standard workflow is:

```bash
git merge main
```

We use merge rather than rebase to keep the workflow simple for the team and avoid unnecessary history rewriting.

Do not force-push shared branches.

Avoid:

```bash
git push --force
```

unless the team has explicitly agreed that it is necessary.

---

# 12. Environment Variables

Never commit real secrets.

Do not commit:

```text
.env
.env.local
.env.production
```

Do not commit:

```text
API keys
database passwords
Django secret keys
cloud credentials
access tokens
```

The repository should contain:

```text
.env.example
```

Developers should create their own local `.env` from the example.

For Docker Compose:

```env
DB_NAME=attendance_db
DB_USER=attendance_user
DB_PASSWORD=your_local_password
DB_HOST=db
DB_PORT=5432
DJANGO_SECRET_KEY=your_local_secret_key
```

Each developer may use their own local password and Django secret key.

### Docker networking

When Django runs inside the Docker Compose network:

```env
DB_HOST=db
```

Here, `db` refers to the PostgreSQL Docker Compose service.

Do not change this to `localhost` when running Django inside the Docker container.

If Django is intentionally run directly on the host machine instead of Docker, the database host may need to be different depending on the local configuration.

The team's standard development environment is Docker Compose.

---

# 13. Docker Development

The application should be runnable using the repository's Docker Compose configuration.

After cloning the repository and creating `.env`, start the application using the commands documented in the README.

Before opening a Pull Request, verify that the application can start successfully.

At minimum:

```bash
docker compose up --build
```

If migrations are required:

```bash
docker compose exec web python manage.py migrate
```

Run Django checks:

```bash
docker compose exec web python manage.py check
```

Run tests if available:

```bash
docker compose exec web python manage.py test
```

---

# 14. Django Migrations

Database model changes must include their corresponding Django migrations.

After modifying models:

```bash
docker compose exec web python manage.py makemigrations
```

Then apply them:

```bash
docker compose exec web python manage.py migrate
```

The generated migration files must be committed to Git.

Example:

```text
attendance/
    migrations/
        0001_initial.py
        0002_add_attendance_status.py
```

Never delete or modify an already-shared migration simply because it conflicts with another developer's work.

If two developers create migrations at the same time, coordinate before merging.

---

# 15. Do Not Commit Local/Generated Files

The repository should not contain:

```text
.env
__pycache__/
*.pyc
.venv/
venv/
node_modules/
*.log
local database files
Docker volumes
IDE-specific configuration
```

The `.gitignore` file should handle these automatically.

Before committing, check:

```bash
git status
```

If you see a secret, local database, virtual environment, or generated file that should not be committed, stop and fix `.gitignore` before pushing.

---

# 16. Before Opening a Pull Request

Run through this checklist:

```text
[ ] I am not working on main
[ ] My branch has a descriptive name
[ ] I pulled the latest main
[ ] My code runs locally
[ ] Docker Compose starts successfully
[ ] Django checks pass
[ ] Tests pass
[ ] Required migrations are included
[ ] No .env or secrets are committed
[ ] No unnecessary generated files are committed
[ ] I reviewed my own changes
[ ] My branch has been pushed to GitHub
```

---

# 17. GitHub Branch Protection

The repository administrator should configure `main` so that:

* Direct pushes are blocked.
* Pull Requests are required.
* At least one approval is required.
* Required CI checks must pass before merging.
* Force pushes are disabled.
* Branch deletion protection is enabled where appropriate.
* Developers cannot bypass the protection rules.

The exact GitHub settings should be configured by the repository administrator.

---

# 18. Recommended Pull Request Flow

The standard development flow is:

```text
             latest develop
                    │
                    ▼
          Create feature branch
                    │
                    ▼
              Develop locally
                    │
                    ▼
              Run tests/checks
                    │
                    ▼
              Push branch
                    │
                    ▼
             Open Pull Request
                    │
             ┌──────┴──────┐
             ▼             ▼
          CI checks      Code review
             │             │
             └──────┬──────┘
                    ▼
              PR approved
                    │
                    ▼
            Merge into develop
                    │
                    ▼
          Integrated develop
```

---

# 19. Daily Workflow — Quick Version

For most developers, the daily workflow is:

### Start work

```bash
git checkout main
git pull origin main
git checkout -b feature/my-task
```

### Work

```bash
git status
git add .
git commit -m "Describe the change"
```

### Push

```bash
git push -u origin feature/my-task
```

### Create PR

Open GitHub → Pull Request → `feature/my-task` → `main`.

### If main changes while working

```bash
git fetch origin
git checkout main
git pull origin main
git checkout feature/my-task
git merge main
```

Resolve conflicts if necessary, test, then:

```bash
git push
```

---

# 20. The Most Important Rule

If you remember only one thing:

```text
main = stable code

feature branch = your work

Pull Request = bridge between your work and develop
```

Never develop directly on `main`.

Never push directly to `main`.

Always use a branch and Pull Request.
