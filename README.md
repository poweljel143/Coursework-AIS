# Микросервисная система "Автосалон"

Полнофункциональная микросервисная архитектура для управления автосалоном с использованием Python и FastAPI.

## Архитектура

### Микросервисы

Система состоит из следующих микросервисов, каждый из которых имеет **свою собственную базу данных**:

- **api-gateway-service** - Единая точка входа, маршрутизация запросов и аутентификация
- **auth-service** - Управление пользователями, аутентификация и авторизация
  - **База данных**: `auth_db` (порт 54321)
- **payment-service** - Обработка платежей
  - **База данных**: `payment_db` (порт 54322)
- **financing-service** - Кредитование и расчет графиков платежей
  - **База данных**: `financing_db` (порт 54323)
- **insurance-service** - Страхование автомобилей и управление полисами
  - **База данных**: `insurance_db` (порт 54324)

### Принцип Database-per-Service

Каждый микросервис имеет **изолированную базу данных** - это фундаментальный принцип микросервисной архитектуры:

#### Преимущества:
✅ **Полная изоляция данных** - сервисы не могут случайно повлиять на данные друг друга  
✅ **Независимое масштабирование** - каждый сервис можно масштабировать отдельно  
✅ **Технологическая свобода** - каждый сервис может выбрать оптимальную БД (PostgreSQL, MongoDB, Redis и т.д.)  
✅ **Улучшенная отказоустойчивость** - проблемы в одной БД не влияют на другие сервисы  
✅ **Легче обновления** - можно обновлять схему БД одного сервиса без риска для всей системы  
✅ **Упрощенное тестирование** - каждый сервис можно тестировать с чистой базой данных  

#### В нашей системе:
- `auth-service` → `auth_db` (пользователи, роли, токены)
- `payment-service` → `payment_db` (платежи, транзакции)
- `financing-service` → `financing_db` (кредиты, графики платежей)
- `insurance-service` → `insurance_db` (полисы, страховые случаи)

## Технологии

- **Backend**: Python 3.11, FastAPI
- **Базы данных**: PostgreSQL (Database-per-Service паттерн)
- **Брокер сообщений**: RabbitMQ
- **Контейнеризация**: Docker & Docker Compose
- **Аутентификация**: JWT токены (access + refresh)
- **API**: RESTful с автоматической документацией Swagger
- **Архитектура**: Микросервисы с Event-Driven коммуникацией

## Быстрый запуск

1. **Клонируйте репозиторий и перейдите в директорию**
   ```bash
   cd autosalon-microservices
   ```

2. **Запустите все сервисы**
   ```bash
   docker-compose up --build
   ```

3. **Сервисы будут доступны по адресам:**
   - API Gateway: http://localhost:8000
   - Auth Service: http://localhost:8001
   - Payment Service: http://localhost:8002
   - Financing Service: http://localhost:8003
   - Insurance Service: http://localhost:8004
   - RabbitMQ Management: http://localhost:15672 (guest/guest)
   - PostgreSQL: localhost:5432

## API Документация

После запуска каждый сервис предоставляет автоматическую документацию Swagger UI:

- API Gateway: http://localhost:8000/docs
- Auth Service: http://localhost:8001/docs
- Payment Service: http://localhost:8002/docs
- Financing Service: http://localhost:8003/docs
- Insurance Service: http://localhost:8004/docs

## Использование

### 1. Регистрация пользователя
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "full_name": "Иван Иванов",
    "password": "password123",
    "phone": "+7-999-123-45-67",
    "role": "client"
  }'
```

### 2. Получение токена
```bash
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password123"
```

### 3. Создание платежа
```bash
curl -X POST "http://localhost:8000/payment/payments" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 1,
    "amount": 1500000.00,
    "method": "card",
    "description": "Покупка автомобиля Toyota Camry"
  }'
```

### 4. Создание заявки на кредит
```bash
curl -X POST "http://localhost:8000/financing/applications" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 1,
    "vehicle_price": 2000000.00,
    "down_payment": 400000.00,
    "term_months": 36,
    "financing_type": "car_loan",
    "employment_status": "employed",
    "monthly_income": 80000.00
  }'
```

### 5. Создание страхового полиса
```bash
curl -X POST "http://localhost:8000/insurance/quotes" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 1,
    "insurance_type": "kasko",
    "coverage_amount": 2000000.00,
    "vehicle_make": "Toyota",
    "vehicle_model": "Camry",
    "vehicle_year": 2023,
    "vehicle_vin": "1HGCM82633A123456"
  }'
```

## Структура проекта

```
autosalon-microservices/
├── docker-compose.yml          # Конфигурация Docker Compose
├── requirements.txt            # Python зависимости
├── Dockerfile                  # Docker образ для сервисов
├── shared/                     # Общие модули
│   ├── models.py              # Общие модели данных
│   ├── auth.py                # Утилиты аутентификации
│   ├── database.py            # Настройки базы данных
│   └── messaging.py           # Работа с брокером сообщений
├── auth-service/              # Сервис аутентификации
├── api-gateway-service/       # API Gateway
├── payment-service/           # Сервис платежей
├── financing-service/         # Сервис кредитования
└── insurance-service/         # Сервис страхования
```

## Разработка

### Добавление нового сервиса

1. Создайте директорию для сервиса
2. Создайте модели в `models.py`
3. Реализуйте CRUD операции в `crud.py`
4. Создайте API endpoints в `main.py`
5. Скопируйте `Dockerfile` и `requirements.txt`
6. Добавьте сервис в `docker-compose.yml`

### Переменные окружения

Каждый сервис поддерживает следующие переменные окружения:

- `DATABASE_URL`: URL подключения к PostgreSQL
- `RABBITMQ_URL`: URL подключения к RabbitMQ
- `JWT_SECRET`: Секретный ключ для JWT токенов

## Мониторинг и отладка

### Логи

Все сервисы выводят структурированные логи. Для просмотра логов конкретного сервиса:

```bash
docker-compose logs auth-service
docker-compose logs api-gateway
```

### Базы данных

Каждый микросервис имеет свою базу данных PostgreSQL. Для подключения из внешних инструментов:

- **Auth DB**: localhost:54321, database: `auth_db`
- **Payment DB**: localhost:54322, database: `payment_db`
- **Financing DB**: localhost:54323, database: `financing_db`
- **Insurance DB**: localhost:54324, database: `insurance_db`

Общие параметры подключения:
- Username: `user`
- Password: `password`

**Примечание**: Внутренние сервисы общаются через Docker network, используя внутренние имена хостов.

### Брокер сообщений

RabbitMQ Management доступен по адресу http://localhost:15672
- Username: guest
- Password: guest

## Архитектурные паттерны

Система реализует ключевые паттерны микросервисной архитектуры:

### Database-per-Service
- **Каждый сервис имеет свою базу данных** для полной изоляции данных
- Обеспечивает независимое масштабирование и развертывание
- Позволяет выбирать оптимальную технологию БД для каждого сервиса

### API Gateway
- Единая точка входа для всех клиентов
- Маршрутизация, аутентификация и агрегация запросов
- Балансировка нагрузки между сервисами

### JWT Authentication
- Безопасная аутентификация с access и refresh токенами
- Ролевая модель доступа (client, manager, admin)
- Централизованное управление пользователями

### Event-Driven Architecture
- Асинхронное взаимодействие через RabbitMQ
- События: `payment.created`, `financing.approved`, `insurance.purchased`
- Связывание сервисов через доменные события
- Компенсация транзакций при отказах (Saga паттерн)

### Взаимодействие сервисов
Поскольку каждый сервис имеет свою базу данных, взаимодействие происходит через:
- **Синхронные REST/gRPC вызовы** для непосредственных запросов
- **Асинхронные события** через брокер сообщений для слабосвязанного взаимодействия
- **API Gateway** для внешних клиентов

### Дополнительные паттерны (запланированы)
- **Saga Pattern**: Распределенные транзакции
- **CQRS**: Разделение операций чтения и записи
- **Circuit Breaker**: Защита от каскадных отказов

## Безопасность

- JWT токены с refresh механизмом
- Ролевая модель доступа (client, manager, admin)
- Валидация входных данных через Pydantic
- CORS настройки для веб-клиентов

## TODO для дальнейшего развития

- [ ] Реализация оставшихся 9 микросервисов (sales, inventory, customer, etc.)
- [ ] Добавление Redis для кэширования
- [ ] Реализация Saga паттерна для распределенных транзакций
- [ ] Добавление метрик и мониторинга (Prometheus + Grafana)
- [ ] API rate limiting
- [ ] Интеграция с внешними платежными системами
- [ ] Добавление уведомлений (email/SMS)
- [ ] Разработка фронтенд приложения