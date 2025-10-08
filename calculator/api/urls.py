from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InsulatorViewSet, InsulatorRequestViewSet, UserViewSet, auth_login, auth_logout

router = DefaultRouter()
router.register(r'insulators', InsulatorViewSet, basename='insulator')
router.register(r'insulatorrequests', InsulatorRequestViewSet, basename='request')

urlpatterns = [
    path('', include(router.urls)),
    path('users/register/', UserViewSet.as_view({'post': 'register'}), name='user-register'),
    path('users/me/', UserViewSet.as_view({'get': 'me', 'put': 'update_me'}), name='user-me'),
    path('auth/login/', auth_login, name='auth-login'),
    path('auth/logout/', auth_logout, name='auth-logout'),
]