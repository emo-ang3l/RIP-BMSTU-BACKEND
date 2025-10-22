# calculator/api/views.py
import uuid
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.utils.text import slugify
from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import BasePermission, SAFE_METHODS, IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from minio import Minio, S3Error

from calculator.models import Insulator, InsulatorRequest, DetailRequestInsulator
from .serializers import (
    InsulatorSerializer, InsulatorRequestSerializer, DetailRequestInsulatorSerializer, 
    UserSerializer, RegisterSerializer, LoginSerializer
)

def get_minio_client():
    return Minio(
        endpoint=f"{settings.MINIO_ENDPOINT}:{settings.MINIO_PORT}",
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )

def generate_image_name(original_filename):
    name_part = original_filename.rsplit('.', 1)[0]
    ext = original_filename.rsplit('.', 1)[1] if '.' in original_filename else ''
    base = slugify(name_part) or 'image'
    unique = uuid.uuid4().hex[:8]
    if ext:
        return f"{base}-{unique}.{ext}"
    return f"{base}-{unique}"

class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        return obj.client == request.user

class IsModerator(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff

class IsModeratorOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

class InsulatorViewSet(viewsets.ModelViewSet):
    queryset = Insulator.objects.all()
    serializer_class = InsulatorSerializer
    permission_classes = [IsModeratorOrReadOnly]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action == 'add_to_request':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsModeratorOrReadOnly]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        qs = Insulator.objects.all()
        only_active = self.request.query_params.get('only_active')
        if only_active in ('1', 'true', 'True'):
            qs = qs.filter(Insulator_active=True)
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(insulator_name__icontains=q)
        return qs.order_by('insulator_name')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        image_key = instance.image_key
        if image_key:
            client = get_minio_client()
            try:
                if client.bucket_exists(settings.MINIO_BUCKET):
                    client.remove_object(settings.MINIO_BUCKET, image_key)
            except S3Error:
                pass
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        method='post',
        manual_parameters=[
            openapi.Parameter(
                name='image',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description='Image file to upload'
            )
        ],
        responses={
            200: openapi.Response(
                description='Image uploaded',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'image_key': openapi.Schema(type=openapi.TYPE_STRING),
                        'url': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    @action(detail=True, methods=['post'], url_path='upload-image', parser_classes=[MultiPartParser])
    def upload_image(self, request, pk=None):
        instance = self.get_object()
        upload = request.FILES.get('image')
        if not upload:
            return Response({"detail": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)

        filename = generate_image_name(upload.name)

        client = get_minio_client()
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)

        if instance.image_key:
            try:
                client.remove_object(settings.MINIO_BUCKET, instance.image_key)
            except S3Error:
                pass

        try:
            client.put_object(
                settings.MINIO_BUCKET,
                filename,
                data=upload.file,
                length=upload.size,
                content_type=upload.content_type or 'application/octet-stream'
            )
        except S3Error as e:
            return Response({"detail": f"Minio error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        instance.image_key = filename
        instance.save(update_fields=['image_key'])

        public_url = f"{settings.MINIO_PUBLIC_URL}{filename}"
        return Response({"image_key": filename, "url": public_url}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='add-to-request')
    def add_to_request(self, request, pk=None):
        insulator = self.get_object()
        user = request.user
        draft = InsulatorRequest.objects.filter(client=user, status_request=InsulatorRequest.Status.DRAFT).first()
        if not draft:
            draft = InsulatorRequest.objects.create(
                client=user,
                climate_zone='',
                required_r_value=0.0,
                wall_type='',
                norm_standard=''
            )

        existing = DetailRequestInsulator.objects.filter(detail_request=draft, insulator=insulator).exists()
        if existing:
            return Response({"detail": "Already added"}, status=status.HTTP_200_OK)

        order = DetailRequestInsulator.objects.filter(detail_request=draft).count() + 1
        DetailRequestInsulator.objects.create(
            detail_request=draft,
            insulator=insulator,
            quantity=1,
            order=order,
            DetailRequestActive=(order == 1),
            user_comment='Добавлено через API'
        )
        return Response({"detail": "Added to draft", "request_id": draft.id}, status=status.HTTP_201_CREATED)

class InsulatorRequestViewSet(viewsets.ModelViewSet):
    queryset = InsulatorRequest.objects.none()
    serializer_class = InsulatorRequestSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def get_permissions(self):
        if self.action in ['complete', 'reject']:
            permission_classes = [IsAuthenticated, IsModerator]
        elif self.action == 'cart_icon':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            qs = InsulatorRequest.objects.all()
        else:
            qs = InsulatorRequest.objects.filter(client=user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status_request=status_filter)
        from_date = self.request.query_params.get('from_date')
        if from_date:
            qs = qs.filter(formation_datetime__gte=from_date)
        to_date = self.request.query_params.get('to_date')
        if to_date:
            qs = qs.filter(formation_datetime__lte=to_date)
        return qs.order_by('-creation_datetime')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == 'retrieve':
            context['include_insulators'] = True
        return context

    def create(self, request, *args, **kwargs):
        return Response({"detail": "POST not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not (instance.client == request.user or request.user.is_staff):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        if instance.status_request not in [InsulatorRequest.Status.DRAFT, InsulatorRequest.Status.FORMED]:
            return Response({"detail": "Cannot edit in this status"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.client == request.user:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        if instance.status_request != InsulatorRequest.Status.DRAFT:
            return Response({"detail": "Can only delete draft"}, status=status.HTTP_400_BAD_REQUEST)
        instance.status_request = InsulatorRequest.Status.DELETED
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='cart-icon')
    def cart_icon(self, request):
        user = request.user
        draft = InsulatorRequest.objects.filter(client=user, status_request=InsulatorRequest.Status.DRAFT).first()
        if not draft:
            return Response({"request_id": None, "count": 0})
        count = DetailRequestInsulator.objects.filter(detail_request=draft).count()
        return Response({"request_id": draft.id, "count": count})

    @action(detail=True, methods=['put'], url_path='form')
    def form(self, request, pk=None):
        instance = self.get_object()
        if not (instance.client == request.user or request.user.is_staff):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        if instance.status_request != InsulatorRequest.Status.DRAFT:
            return Response({"detail": "Only draft can be formed"}, status=status.HTTP_400_BAD_REQUEST)
        if not all([instance.climate_zone, instance.required_r_value > 0, instance.wall_type, instance.norm_standard]):
            return Response({"detail": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
        instance.status_request = InsulatorRequest.Status.FORMED
        instance.formation_datetime = datetime.now()
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['put'], url_path='complete')
    def complete(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Moderator permission required"}, status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        if instance.status_request != InsulatorRequest.Status.FORMED:
            return Response({"detail": "Only formed can be completed"}, status=status.HTTP_400_BAD_REQUEST)
        instance.manager = request.user
        instance.completion_datetime = datetime.now()
        instance.status_request = InsulatorRequest.Status.COMPLETED
        details = DetailRequestInsulator.objects.filter(detail_request=instance)
        for detail in details:
            detail.calculated_thickness = instance.required_r_value * detail.insulator.thermal_conductivity
            detail.save()
        instance.total_thickness = details.aggregate(Sum('calculated_thickness'))['calculated_thickness__sum'] or 0
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['put'], url_path='reject')
    def reject(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Moderator permission required"}, status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        if instance.status_request != InsulatorRequest.Status.FORMED:
            return Response({"detail": "Only formed can be rejected"}, status=status.HTTP_400_BAD_REQUEST)
        instance.manager = request.user
        instance.completion_datetime = datetime.now()
        instance.status_request = InsulatorRequest.Status.REJECTED
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['delete'], url_path='items/(?P<insulator_id>\\d+)')
    def remove_item(self, request, pk=None, insulator_id=None):
        instance = self.get_object()
        if not instance.client == request.user:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        if instance.status_request != InsulatorRequest.Status.DRAFT:
            return Response({"detail": "Only in draft"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            detail = DetailRequestInsulator.objects.get(detail_request=instance, insulator_id=insulator_id)
            detail.delete()
            details = DetailRequestInsulator.objects.filter(detail_request=instance).order_by('order')
            for i, d in enumerate(details, 1):
                d.order = i
                d.DetailRequestActive = (i == 1)
                d.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DetailRequestInsulator.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['put'], url_path='items/(?P<insulator_id>\\d+)')
    def update_item(self, request, pk=None, insulator_id=None):
        instance = self.get_object()
        if not instance.client == request.user:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        if instance.status_request != InsulatorRequest.Status.DRAFT:
            return Response({"detail": "Only in draft"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            detail = DetailRequestInsulator.objects.get(detail_request=instance, insulator_id=insulator_id)
            serializer = DetailRequestInsulatorSerializer(detail, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except DetailRequestInsulator.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

class UserViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ['me', 'update_me']:
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(UserSerializer(request.user).data)

    @action(detail=False, methods=['put'], permission_classes=[IsAuthenticated])
    def update_me(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

@swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'username': openapi.Schema(type=openapi.TYPE_STRING),
            'password': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['username', 'password']
    ),
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                'access': openapi.Schema(type=openapi.TYPE_STRING),
                'sessionid': openapi.Schema(type=openapi.TYPE_STRING),
            }
        ),
        400: 'Invalid credentials'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def auth_login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(request, username=serializer.validated_data['username'], password=serializer.validated_data['password'])
    if user is None:
        return Response({"detail": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Сохраняем сессию
    login(request, user)
    
    # Генерируем JWT
    refresh = RefreshToken.for_user(user)
    
    # Получаем sessionid из текущей сессии
    sessionid = request.session.session_key
    if not sessionid:
        request.session.create()
        sessionid = request.session.session_key
    
    response = Response({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'sessionid': sessionid,
    }, status=status.HTTP_200_OK)
    
    # Устанавливаем куки sessionid
    response.set_cookie(
        'sessionid',
        sessionid,
        max_age=1209600,  # 2 недели
        httponly=True,
        secure=False,  # Установите True для HTTPS
        samesite='Lax'
    )
    
    return response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_logout(request):
    logout(request)
    response = Response({"detail": "Logged out"}, status=status.HTTP_200_OK)
    response.delete_cookie('sessionid')
    return response