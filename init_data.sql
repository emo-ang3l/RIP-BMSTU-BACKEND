-- Insulator
INSERT INTO calculator_insulator (id, insulator_name, insulator_description , is_active, image_key, thermal_conductivity, price_per_m2, density, fire_rating) VALUES
(1, 'Плиты теплозвук- оизоляционные 34', 'Лёгкий вспененный утеплитель для стен и крыш.', TRUE, 'polystyrene.jpg', 0.035, 579.00, 25.0, 'B2'),
(2, 'Плиты теплозвук- оизоляционные 37PN', 'Волокнистый утеплитель на основе базальта.', TRUE, 'mineralwool.jpg', 0.040, 150.00, 100.0, 'A1'),
(3, 'Мат теплоизол- яционный 40RN', 'Пенополиизоциануратные панели с низкой теплопроводностью.', FALSE, 'pir.jpg', 0.022, 300.00, 35.0, 'B1'),
(4, 'Мат теплоизол- яционный 45RN', 'Пенополиизоциануратные панели с низкой теплопроводностью.', FALSE, 'pir2.jpg', 0.022, 300.00, 35.0, 'B1'),
(5, 'Мат теплоизол- яционный 45RN', 'Пенополиизоциануратные панели с низкой теплопроводностью.', FALSE, 'pir2.jpg', 0.022, 300.00, 35.0, 'B1');

-- Request
INSERT INTO calculator_insulatorrequest (id, status_request, creation_datetime, client_id, climate_zone, required_r_value, wall_type, norm_standard) VALUES
(1, 'DRAFT', NOW(), 1, 'Moscow Region', 3.5, 'Brick', 'SNiP 23-02-2003');

-- RequestInsulator
INSERT INTO calculator_detailrequestinsulator (insulatorrequest_id, insulator_id, quantity, "order", is_main, user_comment) VALUES
(1, 1, 1, 1, TRUE, 'Для внешней стены'),
(1, 2, 1, 2, FALSE, 'Для крыши'),
(1, 3, 1, 3, FALSE, 'Для крыши'),
(1, 4, 1, 4, FALSE, 'Для крыши'),
(1, 5, 1, 5, FALSE, 'Для крыши');