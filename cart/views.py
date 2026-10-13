from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.response import Response
 
from .models import CartItem
from .serializers import (
    AddToCartSerializer,
    CartItemSerializer,
    CartSerializer,
    UpdateQuantitySerializer,
    get_cart,
)
 
 
class CartView(generics.RetrieveDestroyAPIView):
    """GET: view my cart. DELETE: empty it."""
 
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]
 
    def get_object(self):
        return get_cart(self.request.user)
 
    def perform_destroy(self, instance):
        instance.items.all().delete()
 
 
class CartItemViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST   /cart/items/        add a product (adds to quantity if already there)
    PATCH  /cart/items/{id}/   set the quantity
    DELETE /cart/items/{id}/   remove the line
    """
 
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["post", "patch", "delete", "head", "options"]
 
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CartItem.objects.none()
        # Only ever the caller's own cart lines -> other users get a 404
        return CartItem.objects.filter(cart__user=self.request.user).select_related("product")
 
    def get_serializer_class(self):
        if self.action == "create":
            return AddToCartSerializer
        if self.action == "partial_update":
            return UpdateQuantitySerializer
        return CartItemSerializer
 
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)
 
    def partial_update(self, request, *args, **kwargs):
        item = self.get_object()
        serializer = self.get_serializer(item, data=request.data)  # quantity is required
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CartItemSerializer(item).data)