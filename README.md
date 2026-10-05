# Kenya Sports Venue Seat Booking and Visualization System

**BBIT 4 - IS Project II - Strathmore University**

A web-based seat booking and visualization system for sports venues in Kenya, enabling fans to interactively select and preview specific seats before purchasing tickets.

## Project Overview

This system addresses the documented gap in Kenya's sports ticketing infrastructure by providing:

- **Interactive SVG Seat Maps** - Real-time, colour-coded seat availability for each event
- **Seat-Specific View Previews** - Descriptive sightline information for each seat category
- **M-Pesa Payment Integration** - Direct M-Pesa STK Push payments via Safaricom Daraja API
- **QR Code Tickets** - Server-validated, single-use QR codes for gate entry
- **Management Dashboards** - Revenue tracking, occupancy heatmaps, and booking trends

## Key Features

### For Fans
✅ Browse events with interactive seat maps  
✅ Select specific seats and preview views  
✅ Hold seats during payment (10-minute configurable timer)  
✅ Pay directly via M-Pesa STK Push  
✅ Receive QR code tickets via email  
✅ Validate entry at gate with QR code  

### For Event Organizers
✅ Create and manage events and venues  
✅ Configure venue seat layouts  
✅ Set seat categories and pricing  
✅ Monitor real-time bookings  
✅ View revenue and occupancy reports  
✅ Analyze booking trends  

### For System Administrators
✅ Manage users and roles (Fan, Organizer, Admin)  
✅ Configure system-wide settings  
✅ Access comprehensive analytics  
✅ View gate entry logs  

## Project Structure

```
seat_booking/
├── seat_booking_config/      # Django project settings
│   ├── settings.py           # Main configuration (PostgreSQL, apps, middleware)
│   ├── urls.py               # Main URL routing
│   ├── wsgi.py               # WSGI application
│   └── asgi.py               # ASGI application
│
├── users/                     # User authentication and profiles
│   ├── models.py             # User, Fan, Organizer, Admin models
│   ├── views.py              # Authentication views
│   ├── serializers.py        # DRF serializers for API
│   └── urls.py               # User app URLs
│
├── venues/                    # Venue and seat management
│   ├── models.py             # Venue, Seat, SeatCategory models
│   ├── views.py              # Venue management views
│   ├── serializers.py        # Venue serializers
│   └── urls.py               # Venue app URLs
│
├── events/                    # Event management
│   ├── models.py             # Event model
│   ├── views.py              # Event views
│   ├── serializers.py        # Event serializers
│   └── urls.py               # Event app URLs
│
├── bookings/                  # Seat booking logic
│   ├── models.py             # Booking model with hold timer
│   ├── views.py              # Booking API views
│   ├── services.py           # Seat hold/release logic
│   ├── serializers.py        # Booking serializers
│   └── urls.py               # Booking app URLs
│
├── payments/                  # M-Pesa payment processing
│   ├── models.py             # Payment model
│   ├── views.py              # Payment API and callbacks
│   ├── daraja.py             # Safaricom Daraja API integration
│   ├── serializers.py        # Payment serializers
│   └── urls.py               # Payment app URLs
│
├── tickets/                   # QR code ticket generation
│   ├── models.py             # Ticket model
│   ├── views.py              # Ticket views
│   ├── qr_generator.py       # QR code generation logic
│   ├── serializers.py        # Ticket serializers
│   └── urls.py               # Ticket app URLs
│
├── gates/                     # Gate entry validation
│   ├── models.py             # GateEntry log model
│   ├── views.py              # Gate validation API
│   ├── validators.py         # QR code validation logic
│   ├── serializers.py        # Gate serializers
│   └── urls.py               # Gate app URLs
│
├── reports/                   # Analytics and reporting
│   ├── models.py             # Report models (if needed)
│   ├── views.py              # Report API endpoints
│   ├── services.py           # Report generation logic
│   ├── serializers.py        # Report serializers
│   └── urls.py               # Report app URLs
│
├── static/                    # Static files (CSS, JS, images)
│   ├── css/
│   ├── js/
│   │   └── seat-map.js       # Interactive SVG seat map
│   └── images/
│
├── templates/                 # HTML templates
│   ├── base.html
│   ├── home.html
│   └── ...
│
├── logs/                      # Application logs
│
├── manage.py                  # Django management script
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore patterns
└── README.md                 # This file
```

## Technology Stack

### Backend
- **Framework**: Django 4.2
- **Database**: PostgreSQL (Production), SQLite (Development)
- **API**: Django REST Framework
- **Payment**: Safaricom Daraja API (M-Pesa STK Push)

### Frontend
- **Markup**: HTML5
- **Styling**: CSS3
- **Interactivity**: JavaScript (Vanilla + SVG)
- **Seat Map**: SVG with real-time AJAX updates

### DevOps
- **Version Control**: Git/GitHub
- **Server**: Gunicorn + Nginx
- **Caching**: Redis
- **Task Queue**: Celery (for async email)

## Prerequisites

- Python 3.10+
- PostgreSQL 12+ (for production)
- Redis (for caching and Celery)
- Git

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/seat_booking.git
cd seat_booking
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Create Database

**For SQLite (Development):**
```bash
python manage.py migrate
```

**For PostgreSQL (Production):**
Ensure PostgreSQL is running, then update `.env` with your database credentials:
```env
USE_POSTGRESQL=True
DB_NAME=seat_booking
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
```

Then run migrations:
```bash
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 8. Run Development Server

```bash
python manage.py runserver
```

Visit `http://localhost:8000` to access the application.

## API Documentation

### Authentication Endpoints

```
POST   /api/v1/auth/register/          - User registration
POST   /api/v1/auth/login/             - User login
POST   /api/v1/auth/refresh/           - Refresh JWT token
POST   /api/v1/auth/logout/            - User logout
```

### Venue Management

```
GET    /api/v1/venues/                 - List all venues
POST   /api/v1/venues/                 - Create venue (Admin/Organizer)
GET    /api/v1/venues/{id}/            - Venue details
PUT    /api/v1/venues/{id}/            - Update venue
DELETE /api/v1/venues/{id}/            - Delete venue
```

### Event Management

```
GET    /api/v1/events/                 - List events
POST   /api/v1/events/                 - Create event (Organizer)
GET    /api/v1/events/{id}/            - Event details with seat map
PUT    /api/v1/events/{id}/            - Update event
DELETE /api/v1/events/{id}/            - Delete event
```

### Seat Booking

```
GET    /api/v1/events/{id}/seats/      - Get available seats
POST   /api/v1/bookings/               - Create booking
GET    /api/v1/bookings/{id}/          - Booking details
PUT    /api/v1/bookings/{id}/          - Update booking
DELETE /api/v1/bookings/{id}/          - Cancel booking
```

### Payments

```
POST   /api/v1/payments/initiate/      - Initiate M-Pesa payment
POST   /api/v1/payments/callback/      - M-Pesa callback (Daraja)
GET    /api/v1/payments/{id}/          - Payment status
```

### Tickets

```
GET    /api/v1/tickets/{id}/           - Get ticket details
POST   /api/v1/tickets/{id}/download/  - Download ticket (PDF with QR)
```

### Gate Validation

```
POST   /api/v1/gates/validate-qr/      - Validate QR code at gate
GET    /api/v1/gates/logs/             - Gate entry logs (Admin)
```

### Reports

```
GET    /api/v1/reports/revenue/        - Revenue report
GET    /api/v1/reports/occupancy/      - Occupancy report
GET    /api/v1/reports/trends/         - Booking trends report
```

## Database Models (from Chapter 4 ER Diagram)

### User Hierarchy
```
User (Base)
├── Fan
├── Organizer
└── Admin
```

### Core Models
- **Venue** - Venue information and seat layout
- **Seat** - Individual seat with category and status
- **SeatCategory** - Seat type (VIP, Regular, Student)
- **Event** - Sports event at a venue
- **Booking** - Fan's seat reservation
- **Payment** - M-Pesa transaction
- **Ticket** - QR code ticket (one per booking)
- **GateEntry** - Entry log for each scanned QR code

## Key Design Decisions

### 1. Seat Hold Mechanism
- **Implementation**: Database-level transaction locks with timer
- **Duration**: 10 minutes (configurable)
- **Purpose**: Prevent double-booking during payment window

### 2. QR Code Validation
- **Type**: Server-side, single-use validation
- **Format**: Unique token per booking
- **Safety**: Prevents duplicate scanning and fraudulent entry

### 3. M-Pesa Integration
- **Method**: STK Push via Daraja API
- **Security**: Server-side payment verification
- **Fallback**: Manual entry for failed QR scans

### 4. Real-Time Updates
- **Technology**: AJAX for seat availability
- **Efficiency**: Only updates changed seats
- **Scale**: Supports high concurrency during popular events

## Testing Strategy

### Unit Tests
```bash
python manage.py test users --verbosity=2
python manage.py test bookings --verbosity=2
```

### Black-Box Testing
- Test user workflows without code knowledge
- Verify all functional requirements

### White-Box Testing
- Test edge cases (concurrent bookings, payment failures)
- Verify seat hold mechanism

### User Acceptance Testing
- Conduct with sample users
- Gather feedback on usability

Run all tests:
```bash
python manage.py test --verbosity=2
```

## Performance Optimization

### Database
- Connection pooling (CONN_MAX_AGE)
- Atomic transactions (ATOMIC_REQUESTS)
- Query optimization with indexing

### Caching
- Redis for session storage
- Cache seat availability data
- Cache frequently accessed reports

### Frontend
- Lazy loading of seat maps
- AJAX for real-time updates
- Responsive SVG rendering

## Deployment

### Development
```bash
python manage.py runserver
```

### Production
```bash
# Using Gunicorn
gunicorn seat_booking_config.wsgi:application --bind 0.0.0.0:8000

# Or with Nginx reverse proxy
# See deployment guide for Nginx configuration
```

## Environment Variables Explained

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBUG` | True | Enable debug mode (set False in production) |
| `SECRET_KEY` | auto-generated | Django secret key for sessions |
| `USE_POSTGRESQL` | False | Switch between SQLite and PostgreSQL |
| `SEAT_HOLD_DURATION_MINUTES` | 10 | How long to hold a selected seat |
| `DARAJA_*` | - | Safaricom API credentials |
| `EMAIL_*` | - | Email configuration for ticket delivery |

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
psql -U postgres -d seat_booking

# Reset migrations (development only)
python manage.py migrate zero
python manage.py migrate
```

### M-Pesa Integration Issues
- Verify Daraja API credentials in .env
- Check sandbox vs. production mode
- Review payment callback logs

### Static Files Not Loading
```bash
python manage.py collectstatic --clear --noinput
```

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -am 'Add your feature'`
3. Push to branch: `git push origin feature/your-feature`
4. Submit pull request

## License

This project is part of Strathmore University's BBIT 4 IS Project II.

## Support

For issues or questions:
- **Email**: denzel.machuki@strathmore.ac.ke
- **Supervisor**: Mr. Patrick Shabaya

## Project Links

- **GitHub**: https://github.com/yourusername/seat_booking
- **Documentation**: See `/docs` folder
- **Issue Tracker**: GitHub Issues

---

**Last Updated**: January 2025  
**Status**: In Development (Chapter 5: Implementation)  
**Current Phase**: Django Setup & Database Configuration
