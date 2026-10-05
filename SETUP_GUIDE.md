# Development Setup Guide

Kenya Sports Venue Seat Booking and Visualization System  
**BBIT 4 - IS Project II**

## Quick Start (5 minutes)

### For Windows

```bash
# 1. Clone and navigate
git clone https://github.com/yourusername/seat_booking.git
cd seat_booking

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup database
copy .env.example .env
python manage.py migrate

# 5. Create admin user
python manage.py createsuperuser

# 6. Run server
python manage.py runserver

# Visit http://localhost:8000
```

### For macOS/Linux

```bash
# 1. Clone and navigate
git clone https://github.com/yourusername/seat_booking.git
cd seat_booking

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup database
cp .env.example .env
python manage.py migrate

# 5. Create admin user
python manage.py createsuperuser

# 6. Run server
python manage.py runserver

# Visit http://localhost:8000
```

## Detailed Setup

### 1. Prerequisites

Verify you have the required software:

```bash
# Python 3.10+
python --version

# Git
git --version

# PostgreSQL (optional, for production)
psql --version
```

### 2. Clone Repository

```bash
git clone https://github.com/yourusername/seat_booking.git
cd seat_booking
```

### 3. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

Verify activation (you should see `(venv)` in terminal):
```bash
pip --version
```

### 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure Environment

Copy example env file:
```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

Edit `.env` with your settings:

```env
DEBUG=True
SECRET_KEY=django-insecure-dev-key-change-in-production

# Database (SQLite for dev, PostgreSQL for production)
USE_POSTGRESQL=False

# Email (optional for development, uses console backend)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# M-Pesa Daraja (get credentials from Safaricom)
DARAJA_CONSUMER_KEY=your_key
DARAJA_CONSUMER_SECRET=your_secret
```

### 6. Initialize Database

**SQLite (Development - Recommended for initial setup):**

```bash
python manage.py migrate
```

**PostgreSQL (Production):**

First, create the database in PostgreSQL:
```sql
-- Connect to PostgreSQL as superuser
psql -U postgres

-- Create database and user
CREATE DATABASE seat_booking;
CREATE USER seatbooking WITH PASSWORD 'password123';
ALTER ROLE seatbooking SET client_encoding TO 'utf8';
ALTER ROLE seatbooking SET default_transaction_isolation TO 'read committed';
ALTER ROLE seatbooking SET default_transaction_deferrable TO on;
ALTER ROLE seatbooking SET timezone TO 'Africa/Nairobi';
GRANT ALL PRIVILEGES ON DATABASE seat_booking TO seatbooking;
\q
```

Update `.env`:
```env
USE_POSTGRESQL=True
DB_NAME=seat_booking
DB_USER=seatbooking
DB_PASSWORD=password123
DB_HOST=localhost
DB_PORT=5432
```

Then run migrations:
```bash
python manage.py migrate
```

### 7. Create Superuser Account

```bash
python manage.py createsuperuser
```

Follow prompts:
```
Username: admin
Email: admin@example.com
Password: (enter secure password)
Password (again): (confirm)
```

### 8. Create Static Files Directory

```bash
# Windows
mkdir static
python manage.py collectstatic

# macOS/Linux
mkdir -p static
python manage.py collectstatic
```

### 9. Load Sample Data (Optional)

```bash
# Create sample venues, events, and seats
python manage.py shell

# In Python shell:
from users.models import User
from venues.models import Venue, Seat, SeatCategory
from events.models import Event
from datetime import datetime, timedelta

# Create admin user
admin = User.objects.create_superuser(
    email='admin@test.com',
    password='admin123',
    first_name='Admin',
    last_name='User',
    role='admin'
)

# Create a venue
venue = Venue.objects.create(
    name='Nyayo Indoor Arena',
    location='Nairobi',
    capacity=3000,
    description='Indoor basketball court'
)

# Create seat categories
category_vip = SeatCategory.objects.create(
    venue=venue,
    name='VIP',
    price=5000.00
)

category_regular = SeatCategory.objects.create(
    venue=venue,
    name='Regular',
    price=2000.00
)

# Create sample seats
for row in range(1, 11):
    for seat_num in range(1, 31):
        Seat.objects.create(
            venue=venue,
            row_number=row,
            seat_number=seat_num,
            category=category_vip if row <= 3 else category_regular,
            status='available'
        )

# Create an event
event = Event.objects.create(
    title='Kenya vs Tanzania Basketball',
    description='Friendly match',
    venue=venue,
    event_date=datetime.now() + timedelta(days=7),
    event_time=datetime.now().time(),
    status='upcoming'
)

print("Sample data created successfully!")
exit()
```

### 10. Run Development Server

```bash
python manage.py runserver
```

Output:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

Visit in your browser:
- **Home**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin (use superuser credentials)
- **API**: http://localhost:8000/api/v1/

## Common Commands

### Database Management

```bash
# Show all migrations
python manage.py showmigrations

# Create a new migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Reset database (development only)
python manage.py migrate zero
python manage.py migrate

# Backup database
pg_dump seat_booking > backup.sql
```

### Django Shell

```bash
# Open interactive Python shell with Django context
python manage.py shell

# Example queries
from users.models import User
from events.models import Event

# Get all users
users = User.objects.all()

# Get all events
events = Event.objects.all()

# Create new user
user = User.objects.create_user(
    email='fan@example.com',
    password='password123',
    first_name='John',
    last_name='Doe',
    phone='0712345678',
    role='fan'
)
```

### Testing

```bash
# Run all tests
python manage.py test

# Run tests for specific app
python manage.py test users

# Run with verbose output
python manage.py test --verbosity=2

# Run specific test
python manage.py test users.tests.UserModelTest
```

### Code Quality

```bash
# Format code with black
black .

# Check code style
flake8 .

# Run pylint
pylint **/*.py
```

## Troubleshooting

### Issue: "No such table" error

```bash
# Solution: Run migrations
python manage.py migrate
```

### Issue: Static files not loading

```bash
# Solution 1: Collect static files
python manage.py collectstatic

# Solution 2: Disable Debug if in production
# Update settings.py: DEBUG = False
```

### Issue: PostgreSQL connection refused

```bash
# Check if PostgreSQL is running
# Windows: Services > PostgreSQL should be running
# macOS: brew services start postgresql
# Linux: sudo service postgresql start

# Verify connection
psql -U seatbooking -d seat_booking -h localhost
```

### Issue: ModuleNotFoundError

```bash
# Solution: Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

### Issue: Port 8000 already in use

```bash
# Run on different port
python manage.py runserver 8001

# Or kill process on port 8000
# Windows: netstat -ano | findstr :8000
# macOS/Linux: lsof -i :8000
```

## IDE Setup

### Visual Studio Code

1. Install extensions:
   - Python
   - Django
   - PostgreSQL
   - REST Client

2. Create `.vscode/settings.json`:
```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "[python]": {
        "editor.defaultFormatter": "ms-python.python",
        "editor.formatOnSave": true
    }
}
```

3. Create `.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Django Debug",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/manage.py",
            "args": ["runserver"],
            "django": true
        }
    ]
}
```

### PyCharm

1. Open project in PyCharm
2. Configure Python interpreter:
   - Settings → Project → Python Interpreter
   - Add Interpreter → Existing Environment
   - Select `venv/bin/python`

3. Configure Django:
   - Settings → Languages & Frameworks → Django
   - Enable Django Support
   - Project Root: (auto-detected)
   - Settings: `seat_booking_config/settings.py`
   - Manage Script: `manage.py`

## Git Workflow

### Initial Setup

```bash
# Initialize git (if not cloned)
git init

# Add remote
git remote add origin https://github.com/yourusername/seat_booking.git

# Create and switch to develop branch
git checkout -b develop

# Make initial commit
git add .
git commit -m "Initial project setup"

# Push to remote
git push -u origin develop
```

### Feature Development

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and commit
git add .
git commit -m "Add your feature description"

# Push to remote
git push origin feature/your-feature

# Create pull request on GitHub
```

### Daily Workflow

```bash
# Update from remote
git pull origin develop

# Check status
git status

# Stage changes
git add .

# Commit
git commit -m "Descriptive commit message"

# Push
git push origin feature/your-feature
```

## Next Steps

1. ✅ Development environment set up
2. 📝 Review Chapter 4 design diagrams
3. 🗄️ Create Django models (next section)
4. 🔌 Implement API endpoints
5. 🎨 Build frontend templates
6. 🧪 Write unit tests
7. 🚀 Deploy to production

## Support

For issues during setup:
- Check Python version: `python --version` (must be 3.10+)
- Verify pip packages: `pip list`
- Check logs: `python manage.py --settings=seat_booking_config.settings` 
- Ask instructor or check GitHub issues

---

Happy coding! 🚀
