from rest_framework import status
from rest_framework.exceptions import APIException


class EmptyCartError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Your cart is empty."
    default_code = "empty_cart"

class CheckoutItemsError(APIException):

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "items_unavailable"

    def __init__(self, items):
        super().__init__()
        self.detail = {"detail": "Some item in your cart can't be purchased.", "items": items}

class InvalidTransactionError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This order can't be moved to that status."
    default_code = "invalid_transaction"
