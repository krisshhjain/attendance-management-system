ATTENDANCE MANAGEMENT SYSTEM — LOCAL DEVELOPMENT SETUP
=======================================================

PREREQUISITES
-------------
- Git
- Python 3.10+
- Node.js 22+
- Docker Desktop (running)

=======================================================
QUICK START (All-in-One)
=======================================================

1. CLONE THE REPOSITORY

   git clone https://github.com/krisshhjain/attendance-management-system.git
   cd attendance-management-system

2. GET THE LATEST DEVELOP BRANCH

   git checkout develop
   git pull origin develop

3. SET UP ENVIRONMENT FILES

   Root .env (for Django):
     Copy-Item .env.example .env       (Windows PowerShell)
     cp .env.example .env              (Linux / Mac / Git Bash)

   Frontend .env:
     Copy-Item frontend\.env.example frontend\.env   (Windows PowerShell)
     cp frontend/.env.example frontend/.env          (Linux / Mac / Git Bash)

4. START POSTGRESQL VIA DOCKER

   Make sure Docker Desktop is running, then:

     docker compose up -d db

   Verify the container is healthy:

     docker compose ps

   You should see:
     attendance_postgres   Up (healthy)   0.0.0.0:5434->5432/tcp

5. SET UP PYTHON ENVIRONMENT

   Navigate to the backend folder:
     cd backend

   Create a virtual environment:
     python -m venv venv

   Activate it:
     Windows PowerShell:  .\venv\Scripts\Activate.ps1
     Linux / Mac:         source venv/bin/activate

   Install dependencies:
     pip install -r requirements.txt

6. RUN DATABASE MIGRATIONS

     python manage.py migrate

7. SEED DEFAULT LEAVE DATA

     python manage.py seed_leave_data

8. CREATE YOUR ADMIN/SUPERUSER (First time only)

     python manage.py createsuperuser

   Enter your email and password when prompted.
   This account is used to log into the admin panel at /admin/
   and into the application as Super Admin via /admin-login

9. VERIFY THE BACKEND

     python manage.py check

   Expected output:
     System check identified no issues (0 silenced).

10. START THE DJANGO BACKEND

     python manage.py runserver

   Backend runs at: http://127.0.0.1:8000/

11. START THE FRONTEND (Open a NEW terminal)

   Navigate to the frontend folder from the project root:
     cd frontend

   Install Node dependencies (first time only):
     npm install

   Start the dev server:
     npm run dev

   Frontend runs at: http://localhost:5173/

=======================================================
APPLICATION URLS
=======================================================

Frontend:        http://localhost:5173/
Backend API:     http://127.0.0.1:8000/api/
Django Admin:    http://127.0.0.1:8000/admin/

Employee Login:  http://localhost:5173/login
Admin Login:     http://localhost:5173/admin-login

=======================================================
KEY API ENDPOINTS
=======================================================

Authentication:
  POST  /api/auth/login/
  POST  /api/auth/token/refresh/
  GET   /api/auth/me/

Attendance (Employee):
  GET   /api/attendance/today/
  POST  /api/attendance/check-in/
  POST  /api/attendance/check-out/
  GET   /api/attendance/history/

Admin Attendance:
  GET   /api/admin/attendance/
  POST  /api/admin/force-checkout/
  GET   /api/admin/dashboard/

Leave Management (Employee):
  GET   /api/leave/types/
  GET   /api/leave/balances/
  GET   /api/leave/requests/
  POST  /api/leave/requests/
  POST  /api/leave/requests/<id>/cancel/

Leave Management (Admin):
  GET   /api/leave/admin/requests/
  POST  /api/leave/admin/requests/<id>/approve/
  POST  /api/leave/admin/requests/<id>/deny/
  GET   /api/leave/admin/balances/

Leave Configuration (Super Admin only):
  GET   /api/leave/admin/types/
  POST  /api/leave/admin/types/
  PATCH /api/leave/admin/types/<id>/
  GET   /api/leave/admin/policies/
  POST  /api/leave/admin/policies/
  PATCH /api/leave/admin/policies/<id>/

=======================================================
DOCKER: FULL STACK MODE (Optional)
=======================================================

To run the entire stack (DB + Backend + Frontend) in Docker:

  docker compose --profile full up --build -d

This builds and starts all 3 containers. The backend entrypoint.sh
automatically waits for PostgreSQL, runs migrations, and seeds data.

Access at:
  Frontend:   http://localhost:80
  Backend:    http://localhost:8000

=======================================================
13. TEAM GIT WORKFLOW
=======================================================

Welcome to the team! Our primary goal is to ensure `main` always represents stable, working code.

**First Day Setup Checklist:**
- [ ] Clone the repository
- [ ] Checkout `develop` branch
- [ ] Copy .env files from .env.example templates
- [ ] Start Docker Compose (db only: `docker compose up -d db`)
- [ ] Create Python venv, install requirements, run migrations
- [ ] Run seed_leave_data command
- [ ] Create superuser (python manage.py createsuperuser)
- [ ] Install Node modules and run the frontend

**Branching & Committing:**
- NEVER work directly on `main`.
- ALWAYS create a feature or fix branch from `develop` (`git checkout -b feature/your-feature-name`).
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

For detailed contribution rules, please refer to CONTRIBUTING.md.