from django.shortcuts import render
from django.http import Http404

MINIO_URL = 'http://localhost:9000/insulation-image/'

INSULATORS = [
    {
        'id': 1,
        'name': 'Плиты теплозвукоизоляционные 34',
        'thermal_conductivity': 0.035,
        'price_per_m2': 579,
        'density': 25.0,
        'fire_rating': 'B2',
        'description': 'Лёгкий вспененный утеплитель для стен и крыш.',
        'image_key': 'polystyrene.jpg',
        'availability': True  # В наличии
    },
    {
        'id': 2,
        'name': 'Плиты теплозвукоизоляционные 37PN',
        'thermal_conductivity': 0.040,
        'price_per_m2': 150,
        'density': 100.0,
        'fire_rating': 'A1',
        'description': 'Волокнистый утеплитель на основе базальта.',
        'image_key': 'mineralwool.jpg',
        'availability': True  # В наличии
    },
    {
        'id': 3,
        'name': 'Мат теплоизоляционный 40RN',
        'thermal_conductivity': 0.022,
        'price_per_m2': 300,
        'density': 35.0,
        'fire_rating': 'B1',
        'description': 'Пенополиизоциануратные панели с низкой теплопроводностью.',
        'image_key': 'pir.jpg',
        'availability': False  # Нет в наличии
    },
    {
        'id': 4,
        'name': 'Мат теплоизоляционный 45RN',
        'thermal_conductivity': 0.022,
        'price_per_m2': 300,
        'density': 35.0,
        'fire_rating': 'B1',
        'description': 'Пенополиизоциануратные панели с низкой теплопроводностью.',
        'image_key': 'pir2.jpg',
        'availability': False  # Нет в наличии
    },
        {
        'id': 5,
        'name': 'Мат теплоизоляционный 45RN',
        'thermal_conductivity': 0.022,
        'price_per_m2': 300,
        'density': 35.0,
        'fire_rating': 'B1',
        'description': 'Пенополиизоциануратные панели с низкой теплопроводностью.',
        'image_key': 'pir2.jpg',
        'availability': False  # Нет в наличии
    },
]

CURRENT_REQUEST = {
    'id': 1,
    'climate_zone': 'Moscow Region',
    'required_r_value': 3.5,
    'wall_type': 'Brick',
    'norm_standard': 'SNiP 23-02-2003',
    'insulators_in_request': [
        {'insulator_id': 1, 'comment': 'Для внешней стены', 'calculated_thickness': 120, 'quantity': 1},
        {'insulator_id': 2, 'comment': 'Для крыши', 'calculated_thickness': 140, 'quantity': 1},
        {'insulator_id': 3, 'comment': 'Для крыши', 'calculated_thickness': 140, 'quantity': 1},
        {'insulator_id': 4, 'comment': 'Для крыши', 'calculated_thickness': 140, 'quantity': 1},
        {'insulator_id': 5, 'comment': 'Для крыши', 'calculated_thickness': 140, 'quantity': 1},


    ]
}

def insulators_list(request):
    search = request.GET.get('search', '')
    filtered_insulators = [
        i for i in INSULATORS
        if search.lower() in i['name'].lower() or search == str(i['thermal_conductivity'])
    ]
    request_count = len(CURRENT_REQUEST['insulators_in_request'])  # Количество, как в методичке
    return render(request, 'calculator/insulators_list.html', {
        'insulators': filtered_insulators,
        'request_count': request_count,  # Передаём в шаблон для корзины
        'search': search,
        'minio_url': MINIO_URL,
        'current_request_id': CURRENT_REQUEST['id']
    })

def insulator_detail(request, id):
    insulator = next((i for i in INSULATORS if i['id'] == id), None)
    if not insulator:
        raise Http404("Утеплитель не найден")
    search = request.GET.get('search', '')
    request_count = len(CURRENT_REQUEST['insulators_in_request'])
    return render(request, 'calculator/insulator_detail.html', {
        'insulator': insulator,
        'minio_url': MINIO_URL,
        'current_request_id': CURRENT_REQUEST['id'],
        'request_count': request_count,
        'search': search
    })

def request_detail(request, id):
    if CURRENT_REQUEST['id'] != id:
        raise Http404("Заявка не найдена")
    insulators = [
        {**next(i for i in INSULATORS if i['id'] == mm['insulator_id']), **mm}
        for mm in CURRENT_REQUEST['insulators_in_request']
    ]
    search = request.GET.get('search', '')
    request_count = len(CURRENT_REQUEST['insulators_in_request'])
    return render(request, 'calculator/request_detail.html', {
        'request': CURRENT_REQUEST,
        'insulators': insulators,
        'minio_url': MINIO_URL,
        'current_request_id': CURRENT_REQUEST['id'],
        'request_count': request_count,
        'search': search 
    })