from django.conf import settings


def site(request):
    """Makes {{ site_name }} available in every template."""
    return {'site_name': settings.SITE_NAME}
