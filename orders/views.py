from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Order
from .serializers import CheckoutSerializer, OrderSerializer, OrderStatusSerializer


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST /orders/              checkout: turn my cart into an order
    GET  /orders/              my orders (staff see all)
    GET  /orders/{id}/         one order
    POST /orders/{id}/cancel/  cancel while still pending (stock is returned)
    PATCH /orders/{id}/status/ staff only: confirm / ship / deliver / cancel
    """

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "total_amount"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        qs = Order.objects.prefetch_related("items")
        user = self.request.user

        return qs if user.is_staff else qs.filter(user=user)

    def get_serializer_class(self):
        if self.action == "create":
            return CheckoutSerializer
        if self.action == "set_status":
            return OrderStatusSerializer
        return OrderSerializer

    def _respond(self, order_id, http_status=status.HTTP_200_OK):
        order = Order.objects.prefetch_related("items").get(pk=order_id)
        return Response(OrderSerializer(order).data, status=http_status)

    @extend_schema(request=CheckoutSerializer, responses={201: OrderSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.checkout(request.user, serializer.validated_data["shipping_address"])
        return self._respond(order.pk, status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        allowed_from = None if request.user.is_staff else {Order.Status.PENDING}
        services.change_status(order.pk, Order.Status.CANCELLED, allowed_from=allowed_from)
        return self._respond(order.pk)

    @extend_schema(request=OrderStatusSerializer, responses=OrderSerializer)
    @action(
        detail=True,
        methods=["patch"],
        url_path="status",
        permission_classes=[permissions.IsAdminUser],
    )
    def set_status(self, request, pk=None):
        order = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_status(order.pk, serializer.validated_data["status"])
        return self._respond(order.pk)
