from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")
        read_only_fields = ("id", "slug")

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    seller_id = serializers.IntegerField(source="seller.id", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "description",
            "price",
            "stock",
            "is_active",
            "category",
            'category_name',
            "seller_id",
            "created_at",
            "updated_at",
        )

        read_only_fields = ("id", "created_at", "updated_at")
