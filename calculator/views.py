from django.shortcuts import render, redirect
from django.http import Http404
from django.db import connection
from django.contrib.auth.decorators import login_required
from .models import Insulator, Request, RequestInsulator
from django.db.models import Q

MINIO_URL = 'http://localhost:9000/insulation-image/'

@login_required
def insulators_list(request):
    query = request.GET.get('query', '')
    draft_request = Request.objects.filter(client=request.user, status=Request.Status.DRAFT).first()
    request_count = RequestInsulator.objects.filter(request=draft_request).count() if draft_request else 0
    insulators = Insulator.objects.filter(
        is_active=True
    ).filter(
        Q(name__icontains=query)  # Только поиск по имени
    )
    return render(request, 'calculator/insulators_list.html', {
        'insulators': insulators,
        'request_count': request_count,
        'query': query,
        'minio_url': MINIO_URL,
        'current_request_id': draft_request.id if draft_request else None
    })

@login_required
def insulator_detail(request, id):
    insulator = Insulator.objects.filter(id=id, is_active=True).first()
    if not insulator:
        raise Http404("Утеплитель не найден")
    query = request.GET.get('query', '')
    draft_request = Request.objects.filter(client=request.user, status=Request.Status.DRAFT).first()
    request_count = RequestInsulator.objects.filter(request=draft_request).count() if draft_request else 0
    return render(request, 'calculator/insulator_detail.html', {
        'insulator': insulator,
        'minio_url': MINIO_URL,
        'current_request_id': draft_request.id if draft_request else None,
        'request_count': request_count,
        'query': query
    })

@login_required
def request_detail(request, id):
    request_data = Request.objects.filter(id=id, client=request.user, status__in=[Request.Status.DRAFT, Request.Status.FORMED, Request.Status.COMPLETED]).first()
    if not request_data:
        raise Http404("Заявка не найдена")
    insulators = []
    for mm in RequestInsulator.objects.filter(request=request_data).order_by('order'):
        insulator = Insulator.objects.get(id=mm.insulator_id)
        mm.calculated_thickness = round(request_data.required_r_value * insulator.thermal_conductivity * 1000)
        mm.save()
        insulators.append({**insulator.__dict__, **mm.__dict__})
    query = request.GET.get('query', '')
    request_count = RequestInsulator.objects.filter(request=request_data).count()
    return render(request, 'calculator/request_detail.html', {
        'request': request_data,
        'insulators': insulators,
        'minio_url': MINIO_URL,
        'current_request_id': request_data.id,
        'request_count': request_count,
        'query': query
    })

@login_required
def add_insulator_to_request(request, insulator_id):
    if request.method != 'POST':
        return redirect('insulators_list')
    insulator = Insulator.objects.filter(id=insulator_id, is_active=True).first()
    if not insulator:
        raise Http404("Утеплитель не найден")
    draft_request = Request.objects.filter(client=request.user, status=Request.Status.DRAFT).first()
    if not draft_request:
        draft_request = Request.objects.create(
            client=request.user,
            climate_zone='Unknown',
            required_r_value=0.0,
            wall_type='Unknown',
            norm_standard='Unknown'
        )
    # Проверка на существование записи
    if not RequestInsulator.objects.filter(request=draft_request, insulator=insulator).exists():
        order = RequestInsulator.objects.filter(request=draft_request).count() + 1
        RequestInsulator.objects.create(
            request=draft_request,
            insulator=insulator,
            quantity=1,
            order=order,
            is_main=(order == 1),
            comment='Добавлено автоматически'
        )
    return redirect('request_detail', id=draft_request.id)

@login_required
def delete_request(request, id):
    if request.method != 'POST':
        return redirect('insulators_list')
    with connection.cursor() as cursor:
        cursor.execute("UPDATE calculator_request SET status = %s WHERE id = %s AND client_id = %s", 
                       [Request.Status.DELETED, id, request.user.id])
    return redirect('insulators_list')

