from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView


def page(template):
    """Frontend pages are static shells; their JavaScript loads data from /api/."""
    return TemplateView.as_view(template_name=template)


urlpatterns = [
    path('admin/', admin.site.urls),

    # API
    path('api/auth/', include('users.urls')),
    path('api/venues/', include('venues.urls')),
    path('api/events/', include('events.urls')),
    path('api/bookings/', include('bookings.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/tickets/', include('tickets.urls')),
    path('api/gates/', include('gates.urls')),
    path('api/reports/', include('reports.urls')),

    # Frontend pages
    path('', RedirectView.as_view(url='/events/', permanent=False)),
    path('events/', page('events/list.html'), name='events'),
    path('events/<int:pk>/', page('events/detail.html'), name='event-detail'),
    path('login/', page('auth/login.html'), name='login'),
    path('register/', page('auth/register.html'), name='register'),
    path('checkout/<int:pk>/', page('checkout.html'), name='checkout'),
    path('tickets/', page('tickets/list.html'), name='tickets'),
    path('tickets/<int:pk>/', page('tickets/detail.html'), name='ticket-detail'),
    path('gate/', page('gate.html'), name='gate'),
    path('reports/', page('reports.html'), name='reports'),
    path('organizer/events/', page('organizer/events.html'), name='organizer-events'),
    path('organizer/events/new/', page('organizer/event_form.html'), name='organizer-event-new'),
    path('organizer/events/<int:pk>/edit/', page('organizer/event_form.html'), name='organizer-event-edit'),
]
