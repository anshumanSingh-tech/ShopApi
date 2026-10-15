from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .cache import CachedReadMixin
from .filters import ProductFilter
from .models import Category, Product
from .permissions import (
    IsAdminOrReadOnly,
    IsProductOwnerOrReadOnly,
    IsSeller,
    IsSellerOrReadOnly,
)
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet( CachedReadMixin, viewsets.ModelViewSet):

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

class ProductViewSet(CachedReadMixin, viewsets.ModelViewSet):

    serializer_class = ProductSerializer
    permission_classes = [IsSellerOrReadOnly, IsProductOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at", "name"]

    def get_queryset(self):
        qs = Product.objects.select_related("category")
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            return qs
        if user.is_authenticated:
            return qs.filter(Q(is_active=True) | Q(seller=user))
        return qs.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    @action(detail=False, methods=["get"], permission_classes=[IsSeller])
    def mine(self, request):
        qs = self.filter_queryset(self.get_queryset().filter(seller=request.user))
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
