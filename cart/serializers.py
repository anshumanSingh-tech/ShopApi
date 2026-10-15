from rest_framework import serializers

from catalog.models import Product

from .models import Cart, CartItem

MAX_QTY_PER_ITEM = 99


def get_cart(user):
    """Return the user's cart (creating it if needed) with items prefetched."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return Cart.objects.prefetch_related("items__product").get(pk=cart.pk)


class CartItemSerializer(serializers.ModelSerializer):
    """Read representation of a cart line."""

    product_name = serializers.CharField(source="product.name", read_only=True)
    unit_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )
    available_stock = serializers.IntegerField(source="product.stock", read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",
            "product_name",
            "unit_price",
            "quantity",
            "line_total",
            "available_stock",
        )


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ("id", "items", "item_count", "total")


class AddToCartSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QTY_PER_ITEM, default=1)

    def validate(self, attrs):
        user = self.context["request"].user
        product = attrs["product"]
        if product.seller_id == user.id:
            raise serializers.ValidationError({"product": "You cannot buy your own product."})

        existing = CartItem.objects.filter(cart__user=user, product=product).first()
        wanted = attrs["quantity"] + (existing.quantity if existing else 0)
        if wanted > product.stock:
            raise serializers.ValidationError(
                {
                    "quantity": f"Only {product.stock} in stock (you already have "
                    f"{existing.quantity if existing else 0} in your cart)."
                }
            )
        if wanted > MAX_QTY_PER_ITEM:
            raise serializers.ValidationError(
                {"quantity": f"You can order at most {MAX_QTY_PER_ITEM} of one product."}
            )
        return attrs

    def create(self, validated_data):
        cart, _ = Cart.objects.get_or_create(user=self.context["request"].user)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=validated_data["product"],
            defaults={"quantity": validated_data["quantity"]},
        )
        if not created:
            item.quantity += validated_data["quantity"]
            item.save(update_fields=["quantity"])
        return item


class UpdateQuantitySerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QTY_PER_ITEM)

    class Meta:
        model = CartItem
        fields = ("quantity",)

    def validate_quantity(self, value):
        stock = self.instance.product.stock
        if value > stock:
            raise serializers.ValidationError(f"Only {stock} in stock.")
        return value
