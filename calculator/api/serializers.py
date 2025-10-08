from rest_framework import serializers
from django.contrib.auth.models import User
from calculator.models import Insulator, InsulatorRequest, DetailRequestInsulator

class InsulatorSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Insulator
        fields = ('id', 'insulator_name', 'insulator_description', 'is_active',
                  'image_key', 'image_url', 'thermal_conductivity', 'price_per_m2',
                  'density', 'fire_rating')
        read_only_fields = ('id', 'image_key', 'image_url')

    def get_image_url(self, obj):
        if obj.image_key:
            from django.conf import settings
            return f"{settings.MINIO_PUBLIC_URL}{obj.image_key}"
        return None

class InsulatorRequestSerializer(serializers.ModelSerializer):
    client_username = serializers.SerializerMethodField()
    manager_username = serializers.SerializerMethodField()
    insulators = serializers.SerializerMethodField()

    class Meta:
        model = InsulatorRequest
        fields = ('id', 'status_request', 'creation_datetime', 'formation_datetime',
                  'completion_datetime', 'client_username', 'manager_username',
                  'climate_zone', 'required_r_value', 'wall_type', 'norm_standard',
                  'total_thickness', 'insulators')
        read_only_fields = ('id', 'status_request', 'creation_datetime', 'formation_datetime',
                            'completion_datetime', 'client_username', 'manager_username',
                            'total_thickness')

    def get_client_username(self, obj):
        return obj.client.username if obj.client else None

    def get_manager_username(self, obj):
        return obj.manager.username if obj.manager else None

    def get_insulators(self, obj):
        if self.context.get('include_insulators'):
            details = DetailRequestInsulator.objects.filter(detail_request=obj).order_by('order')
            return DetailRequestInsulatorSerializer(details, many=True).data
        return None

class DetailRequestInsulatorSerializer(serializers.ModelSerializer):
    insulator = InsulatorSerializer(read_only=True)

    class Meta:
        model = DetailRequestInsulator
        fields = ('insulator', 'quantity', 'order', 'is_main', 'user_comment', 'calculated_thickness')
        read_only_fields = ('calculated_thickness',)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = ('id',)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'first_name', 'last_name')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data.get('email'),
            first_name=validated_data.get('first_name'),
            last_name=validated_data.get('last_name')
        )
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)