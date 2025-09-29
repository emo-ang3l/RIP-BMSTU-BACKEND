from django.shortcuts import render
from django.http import Http404

MINIO_URL = 'http://localhost:9000/insulation-image/'

INSULATORS = [
    {
        'id': 1,
        'name': 'Плиты теплозвук- оизоляционные 34',
        'thermal_conductivity': 0.035,
        'price_per_m2': 579,
        'density': 25.0,
        'fire_rating': 'B2',
        'description': 'Лёгкий вспененный утеплитель для стен и крыш.',
        'image_key': 'polystyrene.jpg',
        'availability': True
    },
    {
        'id': 2,
        'name': 'Плиты теплозвук- оизоляционные 37PN',
        'thermal_conductivity': 0.040,
        'price_per_m2': 150,
        'density': 100.0,
        'fire_rating': 'A1',
        'description': 'Волокнистый утеплитель на основе базальта.',
        'image_key': 'mineralwool.jpg',
        'availability': True
    },
    {
        'id': 3,
        'name': 'Мат теплоизол- яционный 40RN',
        'thermal_conductivity': 0.022,
        'price_per_m2': 300,
        'density': 35.0,
        'fire_rating': 'B1',
        'description': 'Пенополиизоциануратные панели с низкой теплопроводностью.',
        'image_key': 'pir.jpg',
        'availability': False
    },
    {
        'id': 4,
        'name': 'Мат теплоизо- ляционный 45RN',
        'thermal_conductivity': 0.022,
        'price_per_m2': 300,
        'density': 35.0,
        'fire_rating': 'B1',
        'description': 'Пенополиизоциануратные панели с низкой теплопроводностью.',
        'image_key': 'pir2.jpg',
        'availability': False
    },
    {
        'id': 5,
        'name': 'Мат теплоизо- ляционный 45RN',
        'thermal_conductivity': 0.022,
        'price_per_m2': 300,
        'density': 35.0,
        'fire_rating': 'B1',
        'description': 'Пенополиизоциануратные панели с низкой теплопроводностью.',
        'image_key': 'pir2.jpg',
        'availability': False
    },
]

CURRENT_REQUESTS = [
    {
        'id': 1,
        'climate_zone': 'Moscow Region',
        'required_r_value': 3.5,
        'wall_type': 'Brick',
        'norm_standard': 'SNiP 23-02-2003',
        'insulators_in_request': [
            {'insulator_id': 1, 'comment': 'Для внешней стены', 'quantity': 1, 'order': 1, 'is_main': True},
            {'insulator_id': 2, 'comment': 'Для крыши', 'quantity': 1, 'order': 2, 'is_main': False},
            {'insulator_id': 3, 'comment': 'Для крыши', 'quantity': 1, 'order': 3, 'is_main': False},
            {'insulator_id': 4, 'comment': 'Для крыши', 'quantity': 1, 'order': 4, 'is_main': False},
            {'insulator_id': 5, 'comment': 'Для крыши', 'quantity': 1, 'order': 5, 'is_main': False},
        ]
    }
]

def insulators_list(request):
    query = request.GET.get('query', '')
    filtered_insulators = [
        i for i in INSULATORS
        if query.lower() in i['name'].lower() or query == str(i['thermal_conductivity']) or query == str(i['price_per_m2'])
    ]
    # Use the first request's insulators count for consistency, or adjust as needed
    request_count = len(CURRENT_REQUESTS[0]['insulators_in_request']) if CURRENT_REQUESTS else 0
    return render(request, 'calculator/insulators_list.html', {
        'insulators': filtered_insulators,
        'request_count': request_count,
        'query': query,
        'minio_url': MINIO_URL,
        'current_request_id': CURRENT_REQUESTS[0]['id'] if CURRENT_REQUESTS else None
    })

def insulator_detail(request, id):
    insulator = next((i for i in INSULATORS if i['id'] == id), None)
    if not insulator:
        raise Http404("Утеплитель не найден")
    query = request.GET.get('query', '')
    # Use the first request's insulators count for consistency, or adjust as needed
    request_count = len(CURRENT_REQUESTS[0]['insulators_in_request']) if CURRENT_REQUESTS else 0
    return render(request, 'calculator/insulator_detail.html', {
        'insulator': insulator,
        'minio_url': MINIO_URL,
        'current_request_id': CURRENT_REQUESTS[0]['id'] if CURRENT_REQUESTS else None,
        'request_count': request_count,
        'query': query
    })

def request_detail(request, id):
    request_data = next((r for r in CURRENT_REQUESTS if r['id'] == id), None)
    if not request_data:
        raise Http404("Заявка не найдена")
    insulators = []
    for mm in request_data['insulators_in_request']:
        insulator = next((i for i in INSULATORS if i['id'] == mm['insulator_id']), None)
        if insulator:
            mm['calculated_thickness'] = round(request_data['required_r_value'] * insulator['thermal_conductivity'] * 1000)
            insulators.append({**insulator, **mm})

    query = request.GET.get('query', '')
    request_count = len(request_data['insulators_in_request'])
    return render(request, 'calculator/request_detail.html', {
        'request': request_data,
        'insulators': insulators,
        'minio_url': MINIO_URL,
        'current_request_id': request_data['id'],
        'request_count': request_count,
        'query': query
    })