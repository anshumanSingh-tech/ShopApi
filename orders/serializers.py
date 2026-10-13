from rest_framework import serializers

from .models import Order, OrderItem
from .services import checkout

class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "unit_price", "quantity", "line_total")
        
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = (
            "id", 
            "status",
            "shipping_address",
            "total_amount",
            "items",
            "created_at",
            "updated_at",
        )
        
class CheckoutSerializer(serializers.Serializer):
    shipping_address = serializers.CharField(min_length=10, max_length=500)
    
    def create(self, validated_data):
        user = self.context["request"].user
        return checkout(user, validated_data["shipping_address"])
    
class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)