ATTENDANCE MANAGEMENT SYSTEM
LOCAL DEVELOPMENT SETUP

Prerequisites:
- Git
- Python 3.10+
- Node.js
- Docker Desktop

1. CLONE THE REPOSITORY

git clone https://github.com/krisshhjain/attendance-management-system.git

cd attendance-management-system

2. GET THE LATEST DEVELOP BRANCH

git checkout develop

git pull origin develop

3. SET UP ENVIRONMENT VARIABLES

Copy the `.env.example` file to create your own local `.env` file:
For Windows PowerShell:
cp .env.example .env
For Linux/Mac/Git Bash:
cp .env.example .env

4. START POSTGRESQL USING DOCKER

Make sure Docker Desktop is running.

From the project root:

docker compose up -d

Check that the containers are running:

docker compose ps

You should see the PostgreSQL container running.

Do NOT install PostgreSQL separately.

5. SET UP THE PYTHON VIRTUAL ENVIRONMENT

Go into the backend:

cd backend

Create a virtual environment:

python -m venv venv

Activate it:

.\venv\Scripts\Activate.ps1

You should now see:

(venv)

at the beginning of your terminal.

6. INSTALL BACKEND DEPENDENCIES

Run:

pip install -r requirements.txt

7. RUN DATABASE MIGRATIONS

Run:

python manage.py migrate

8. CHECK THE BACKEND

Run:

python manage.py check

You should get:

System check identified no issues (0 silenced).

9. START DJANGO

Run:

python manage.py runserver

Django should start at:

http://127.0.0.1:8000/

10. TEST THE DJANGO ADMIN

Open:

http://127.0.0.1:8000/admin/

The existing development superuser is not included in Git.

If you need your own admin account for local testing, create one:

python manage.py createsuperuser

Enter your own email and password.

DO NOT commit or share your password.

11. BACKEND API

The current APIs are:

POST
/api/auth/login/

GET
/api/attendance/today/

POST
/api/attendance/check-in/

POST
/api/attendance/check-out/

GET
/api/attendance/history/

GET
/api/admin/attendance/

12. FRONTEND SETUP

Open a NEW terminal.

Go to the project root:

cd attendance-management-system

Go into frontend:

cd frontend

Install frontend dependencies:

npm install

Start the frontend:

npm run dev

13. TEAM GIT WORKFLOW

Welcome to the team! Our primary goal is to ensure `main` always represents stable, working code.

**First Day Setup Checklist:**
- [ ] Clone the repository
- [ ] Ensure you are on `main` branch (`git checkout main`)
- [ ] Set up `.env` from `.env.example`
- [ ] Start Docker Compose
- [ ] Set up Python venv, install requirements, and run migrations
- [ ] Install Node modules and run the frontend

**Branching & Committing:**
- NEVER work directly on `main`.
- ALWAYS create a feature or fix branch from `main` (`git checkout -b feature/your-feature-name`).
- NEVER push directly to `main`.
- Use descriptive branch names: `feature/`, `fix/`, `refactor/`, `docs/`, `chore/`.

**Updating Your Branch (Handling Merge Conflicts):**
If `main` is updated by another developer, keep your branch synchronized:
1. `git fetch origin`
2. `git checkout main`
3. `git pull origin main`
4. `git checkout feature/your-feature-name`
5. `git merge main`
6. Resolve conflicts in your editor, test locally, commit the resolution, and push.

**Pull Requests:**
- When your feature is done, push your branch and open a Pull Request (PR) to develop.
- At least one approval is required to merge.
- Automated CI checks must pass.

For detailed contribution rules, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).