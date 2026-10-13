from django.urls import path
from rest_framework.routers import SimpleRouter

from users.urls import urlpatterns

from .views import CartItemViewSet, CartView

router = SimpleRouter()
router.register("items", CartItemViewSet, basename="cart-item")

urlpatterns = [path("", CartView.as_view(), name="cart")] + router.urls