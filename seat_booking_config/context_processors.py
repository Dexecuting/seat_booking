from pathlib import Path

from django.conf import settings


def asset_version():
    """Newest change time of our CSS and JS. Added to their URLs so browsers never run a stale mix
    of old and new files; in production the hashed file names already do this job."""
    if not settings.DEBUG:
        return ''
    static = Path(settings.BASE_DIR) / 'static'
    files = [*static.glob('js/*.js'), *static.glob('css/*.css')]
    return int(max(f.stat().st_mtime for f in files))


def site(request):
    """Makes {{ site_name }} and {{ asset_version }} available in every template."""
    return {'site_name': settings.SITE_NAME, 'asset_version': asset_version()}
