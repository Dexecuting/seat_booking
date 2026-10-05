from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer, TokenWithRoleSerializer, UserSerializer


def tokens_for(user):
    refresh = TokenWithRoleSerializer.get_token(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ - create a fan account and log them straight in."""
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'user': UserSerializer(user).data, **tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ with username + password -> access & refresh tokens."""
    serializer_class = TokenWithRoleSerializer


class LogoutView(APIView):
    """POST /api/auth/logout/ with {"refresh": "..."} - blacklists the refresh token."""

    def post(self, request):
        try:
            RefreshToken(request.data.get('refresh', '')).blacklist()
        except TokenError:
            return Response({'detail': 'Invalid or expired refresh token.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ - the logged-in user's profile."""
    serializer_class = UserSerializer
    http_method_names = ['get', 'patch']

    def get_object(self):
        return self.request.user
