from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsFan(BasePermission):
    message = 'Only fan accounts can do this.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'fan'


class IsOrganizer(BasePermission):
    """Organizers and administrators (admins can do anything an organizer can)."""
    message = 'Only event organizers can do this.'

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (user.role in ('organizer', 'admin') or user.is_superuser)


class IsAdminRole(BasePermission):
    message = 'Only administrators can do this.'

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


class IsOrganizerOrReadOnly(IsOrganizer):
    """Anyone (even logged out) can read; only organizers/admins can create or edit."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or super().has_permission(request, view)


class IsGateStaff(BasePermission):
    """Gate staff scan tickets; organizers and admins can too."""
    message = 'Only gate staff can scan tickets.'

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (
            user.role in ('gate_staff', 'organizer', 'admin') or user.is_superuser)
