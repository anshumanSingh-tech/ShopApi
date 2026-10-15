from rest_framework import generics, permissions

from .serializers import RegisterSerializers, UserSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializers
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
