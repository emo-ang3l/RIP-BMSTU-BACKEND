import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.utils.text import slugify
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q, Sum
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from minio import Minio, S3Error

from calculator.models import Insulator, InsulatorRequest, DetailRequestInsulator
from .serializers import InsulatorSerializer, InsulatorRequestSerializer, DetailRequestInsulatorSerializer, UserSerializer, RegisterSerializer, LoginSerializer

# Minio client singleton
def get_minio_client():
    return Minio(
        endpoint=f"{settings.MINIO_ENDPOINT}:{settings.MINIO_PORT}",
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )

# Singleton for fixed creator
_creator_user = None
def get_creator_user():
    global _creator_user
    if _creator_user is None:
        from django.contrib.auth.models import User
        _creator_user, _ = User.objects.get_or_create(username='creator', defaults={'password': 'fixpass'})
    return _creator_user

# Singleton for moderator
_moderator_user = None
def get_moderator_user():
    global _moderator_user
    if _moderator_user is None:
        from django.contrib.auth.models import User
        _moderator_user, _ = User.objects.get_or_create(username='moderator', defaults={'password': 'fixedpass'})
    return _moderator_user

# Utility for generating Latin file name
def generate_image_name(original_filename):
    name_part = original_filename.rsplit('.', 1)[0]
    ext = original_filename.rsplit('.', 1)[1] if '.' in original_filename else ''
    base = slugify(name_part) or 'image'
    unique = uuid.uuid4().hex[:8]
    if ext:
        return f"{base}-{unique}.{ext}"
    return f"{base}-{unique}"

class InsulatorViewSet(viewsets.ModelViewSet):
    """
    /api/insulators/
    GET list (с фильтрацией по имени и Insulator_active)
    POST create (без изображения)
    GET /{id}/ retrieve
    PUT /{id}/ update
    DELETE /{id}/ destroy (удаляет изображение из minio если есть)
    POST /{id}/upload-image/ - загрузка/замена изображения
    POST /{id}/add-to-request/ - добавляет услугу в черновик текущего пользователя
    """
    queryset = Insulator.objects.all()
    serializer_class = InsulatorSerializer
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

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

    @action(detail=True, methods=['post'], url_path='upload-image')
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
        user = get_creator_user()

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
    """
    /api/insulatorrequests/
    GET list (с фильтрацией по статусу и диапазону даты формирования, все статусы)
    GET /{id}/ retrieve (с услугами и картинками)
    PUT /{id}/ update (изменение полей заявки)
    DELETE /{id}/ destroy (только DRAFT -> DELETED)
    GET /cart-icon/ (id черновика и количество услуг)
    PUT /{id}/form/ (перевод в FORMED, проверка полей)
    PUT /{id}/complete/ (модератор завершает, вычисления)
    PUT /{id}/reject/ (модератор отклоняет)
    DELETE /{id}/items/{insulator_id}/ (удаление м-м)
    PUT /{id}/items/{insulator_id}/ (изменение м-м)
    """
    queryset = InsulatorRequest.objects.none()
    serializer_class = InsulatorRequestSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = get_creator_user()
        qs = InsulatorRequest.objects.filter(client=user)  # Убрана проверка на DRAFT и DELETED
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status_request=status_filter)
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        if from_date:
            qs = qs.filter(formation_datetime__gte=from_date)
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
        if instance.status_request not in [InsulatorRequest.Status.DRAFT, InsulatorRequest.Status.FORMED]:
            return Response({"detail": "Cannot edit in this status"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status_request != InsulatorRequest.Status.DRAFT:
            return Response({"detail": "Can only delete draft"}, status=status.HTTP_400_BAD_REQUEST)
        instance.status_request = InsulatorRequest.Status.DELETED
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='cart-icon')
    def cart_icon(self, request):
        user = get_creator_user()
        draft = InsulatorRequest.objects.filter(client=user, status_request=InsulatorRequest.Status.DRAFT).first()
        if not draft:
            return Response({"request_id": None, "count": 0})
        count = DetailRequestInsulator.objects.filter(detail_request=draft).count()
        return Response({"request_id": draft.id, "count": count})

    @action(detail=True, methods=['put'], url_path='form')
    def form(self, request, pk=None):
        instance = self.get_object()
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
        instance = self.get_object()
        if instance.status_request != InsulatorRequest.Status.FORMED:
            return Response({"detail": "Only formed can be completed"}, status=status.HTTP_400_BAD_REQUEST)
        moderator = get_moderator_user()
        instance.manager = moderator
        instance.completion_datetime = datetime.now()
        instance.status_request = InsulatorRequest.Status.COMPLETED
        details = DetailRequestInsulator.objects.filter(detail_request=instance)
        total_cost = Decimal(0)
        for detail in details:
            detail.calculated_thickness = instance.required_r_value * detail.insulator.thermal_conductivity
            detail.save()
            total_cost += detail.insulator.price_per_m2 * Decimal(detail.quantity)
        instance.total_thickness = details.aggregate(Sum('calculated_thickness'))['calculated_thickness__sum'] or 0
        delivery_date = datetime.now() + timedelta(days=15)
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['put'], url_path='reject')
    def reject(self, request, pk=None):
        instance = self.get_object()
        if instance.status_request != InsulatorRequest.Status.FORMED:
            return Response({"detail": "Only formed can be rejected"}, status=status.HTTP_400_BAD_REQUEST)
        moderator = get_moderator_user()
        instance.manager = moderator
        instance.completion_datetime = datetime.now()
        instance.status_request = InsulatorRequest.Status.REJECTED
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['delete'], url_path='items/(?P<insulator_id>\d+)')
    def remove_item(self, request, pk=None, insulator_id=None):
        instance = self.get_object()
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

    @action(detail=True, methods=['put'], url_path='items/(?P<insulator_id>\d+)')
    def update_item(self, request, pk=None, insulator_id=None):
        instance = self.get_object()
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

@api_view(['POST'])
@permission_classes([AllowAny])
def auth_login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(username=serializer.validated_data['username'], password=serializer.validated_data['password'])
    if user:
        login(request, user)
        return Response({"detail": "Logged in successfully"}, status=status.HTTP_200_OK)
    return Response({"detail": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_logout(request):
    logout(request)
    return Response({"detail": "Logged out"})