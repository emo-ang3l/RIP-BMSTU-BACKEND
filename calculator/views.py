from django.shortcuts import render, redirect
from django.http import Http404
from django.db import connection
from django.contrib.auth.decorators import login_required
from .models import Insulator, InsulatorRequest, DetailRequestInsulator
from django.db.models import Q

MINIO_URL = 'http://localhost:9000/insulation-image/'

@login_required
def insulators_list(detail_request):
    query = detail_request.GET.get('query', '')
    draft_request = InsulatorRequest.objects.filter(client=detail_request.user, status_request=InsulatorRequest.Status.DRAFT).first()
    request_count = DetailRequestInsulator.objects.filter(detail_request=draft_request).count() if draft_request else 0
    insulators = Insulator.objects.filter(
        Insulator_active=True
    ).filter(
        Q(insulator_name__icontains=query)  # Только поиск по имени
    )
    return render(detail_request, 'calculator/insulators_list.html', {
        'insulators': insulators,
        'request_count': request_count,
        'query': query,
        'minio_url': MINIO_URL,
        'current_request_id': draft_request.id if draft_request else None
    })

@login_required
def insulator_detail(detail_request, id):
    insulator = Insulator.objects.filter(id=id, Insulator_active=True).first()
    if not insulator:
        return render(detail_request, '404.html', {'message': 'Утеплитель не найден'}, status=404)  # Рендер 404.html
    query = detail_request.GET.get('query', '')
    draft_request = InsulatorRequest.objects.filter(client=detail_request.user, status_request=InsulatorRequest.Status.DRAFT).first()
    request_count = DetailRequestInsulator.objects.filter(detail_request=draft_request).count() if draft_request else 0
    return render(detail_request, 'calculator/insulator_detail.html', {
        'insulator': insulator,
        'minio_url': MINIO_URL,
        'current_request_id': draft_request.id if draft_request else None,
        'request_count': request_count,
        'query': query
    })

@login_required
def request_detail(detail_request, id):
    # Проверяем, существует ли заявка и не является ли она удалённой
    request_data = InsulatorRequest.objects.filter(
        id=id,
        client=detail_request.user,
        status_request__in=[
            InsulatorRequest.Status.DRAFT,
            InsulatorRequest.Status.FORMED,
            InsulatorRequest.Status.COMPLETED
        ]
    ).first()
    
    # Если заявка не найдена или имеет статус DELETED, рендерим 404.html
    if not request_data:
        return render(detail_request, '404.html', {'message': 'Заявка не найдена или была удалена'}, status=404)
    
    insulators = []
    for mm in DetailRequestInsulator.objects.filter(detail_request=request_data).order_by('order'):
        insulator = Insulator.objects.get(id=mm.insulator_id)
        mm.calculated_thickness = round(request_data.required_r_value * insulator.thermal_conductivity * 1000)
        mm.save()
        insulators.append({**insulator.__dict__, **mm.__dict__})
    query = detail_request.GET.get('query', '')
    request_count = DetailRequestInsulator.objects.filter(detail_request=request_data).count()
    return render(detail_request, 'calculator/request_detail.html', {
        'insulator_request': request_data,
        'insulators': insulators,
        'minio_url': MINIO_URL,
        'current_request_id': request_data.id,
        'request_count': request_count,
        'query': query
    })

@login_required
def add_insulator_to_request(detail_request, insulator_id):
    if detail_request.method != 'POST':
        return redirect('insulators_list')
    insulator = Insulator.objects.filter(id=insulator_id, Insulator_active=True).first()
    if not insulator:
        return render(detail_request, '404.html', {'message': 'Утеплитель не найден'}, status=404)  # Рендер 404.html
    draft_request = InsulatorRequest.objects.filter(client=detail_request.user, status_request=InsulatorRequest.Status.DRAFT).first()
    if not draft_request:
        draft_request = InsulatorRequest.objects.create(
            client=detail_request.user,
            climate_zone='',
            required_r_value=0.0,
            wall_type='',
            norm_standard=''
        )
    # Проверка на существование записи
    if not DetailRequestInsulator.objects.filter(detail_request=draft_request, insulator=insulator).exists():
        order = DetailRequestInsulator.objects.filter(detail_request=draft_request).count() + 1
        DetailRequestInsulator.objects.create(
            detail_request=draft_request,
            insulator=insulator,
            quantity=1,
            order=order,
            DetailRequestActive_active=(order == 1),
            user_comment='Добавлено автоматически'
        )
    return redirect('request_detail', id=draft_request.id)

@login_required
def delete_request(detail_request, id):
    if detail_request.method != 'POST':
        return redirect('insulators_list')
    with connection.cursor() as cursor:
        cursor.execute("UPDATE calculator_insulatorrequest SET status_request = %s WHERE id = %s AND client_id = %s", 
                       [InsulatorRequest.Status.DELETED, id, detail_request.user.id])
    return redirect('insulators_list')