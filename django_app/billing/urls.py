from rest_framework.routers import DefaultRouter

from .views import PayeeViewSet, PaymentViewSet

router = DefaultRouter()
router.register("payees", PayeeViewSet, basename="payee")
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = router.urls
