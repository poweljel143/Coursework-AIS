import httpx
import pytest

# Базовый URL API Gateway
API_GATEWAY_URL = "http://localhost:8000"

# Тестовые данные для пользователя
TEST_USER_EMAIL = "test_user@example.com"
TEST_USER_PASSWORD = "testpassword"
TEST_USER_FULL_NAME = "Test User Integration"
TEST_USER_PHONE = "+7-999-111-22-33"

# Переменные для хранения токенов и ID пользователя
ACCESS_TOKEN = None
REFRESH_TOKEN = None
USER_ID = None

@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=API_GATEWAY_URL, timeout=30.0) as client_instance:
        yield client_instance

@pytest.fixture(scope="session")
def auth_token(client):
    global ACCESS_TOKEN, REFRESH_TOKEN, USER_ID

    # 1. Регистрация тестового пользователя
    register_payload = {
        "email": TEST_USER_EMAIL,
        "full_name": TEST_USER_FULL_NAME,
        "password": TEST_USER_PASSWORD,
        "phone": TEST_USER_PHONE,
        "role": "client"
    }
    try:
        response = client.post("/auth/register", json=register_payload)
        assert response.status_code == 200 or response.status_code == 400  # 400 if already registered
        if response.status_code == 200:
            user_data = response.json()
            USER_ID = user_data["id"]
        elif response.status_code == 400 and "Email already registered" in response.json().get("detail", ""):
            # Если пользователь уже зарегистрирован, просто получаем его ID
            # Для этого нужно будет сделать запрос на получение пользователя по email, но это усложнит фикстуру.
            # Пока что будем считать, что если регистрация вернула 400, то пользователь уже есть.
            pass # Мы пропустим получение USER_ID здесь, если он уже зарегистрирован.

    except Exception as e:
        pytest.fail(f"Failed to register test user: {e}")

    # 2. Получение токенов для тестового пользователя
    token_payload = {
        "username": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    response = client.post("/auth/token", data=token_payload)
    assert response.status_code == 200, f"Failed to get token: {response.text}"
    token_data = response.json()
    ACCESS_TOKEN = token_data["access_token"]
    REFRESH_TOKEN = token_data["refresh_token"]
    
    # 3. Получение USER_ID, если он не был получен при регистрации (если пользователь был уже зарегистрирован)
    if not USER_ID:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 200, f"Failed to get current user info: {response.text}"
        user_data = response.json()
        USER_ID = user_data["id"]

    yield ACCESS_TOKEN


# Тесты для Payment Service
def test_payment_service_health(client):
    response = client.get("/payment/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "payment-service"}

def test_create_and_get_payment(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payment_params = {
        "order_id": 100,
        "amount": 150000.00,
        "method": "card",
        "description": "Тестовый платеж за автомобиль",
    }
    # These fields are defined as query parameters in payment-service
    response = client.post("/payment/payments", headers=headers, params=payment_params)
    assert response.status_code == 200, f"Failed to create payment: {response.text}"
    payment_data = response.json()
    assert payment_data["amount"] == 150000.00
    assert payment_data["status"] == "pending"
    assert "payment_id" in payment_data

    # Получить все платежи пользователя
    response = client.get("/payment/payments", headers=headers)
    assert response.status_code == 200, f"Failed to get user payments: {response.text}"
    payments = response.json()
    assert any(p["order_id"] == 100 for p in payments)


# Тесты для Financing Service
def test_financing_service_health(client):
    response = client.get("/financing/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "financing-service"}

def test_create_and_get_financing_application(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    application_params = {
        "order_id": 200,
        "vehicle_price": 2000000.00,
        "down_payment": 400000.00,
        "term_months": 36,
        "financing_type": "car_loan",
        "employment_status": "employed",
        "monthly_income": 80000.00,
    }
    # These fields are defined as query parameters in financing-service
    response = client.post("/financing/applications", headers=headers, params=application_params)
    assert response.status_code == 200, f"Failed to create financing application: {response.text}"
    application_data = response.json()
    assert application_data["loan_amount"] == 1600000.00
    assert application_data["status"] == "draft"
    assert "application_id" in application_data

    # Получить все заявки пользователя
    response = client.get("/financing/applications", headers=headers)
    assert response.status_code == 200, f"Failed to get user applications: {response.text}"
    applications = response.json()
    assert any(app["order_id"] == 200 for app in applications)


# Тесты для Insurance Service
def test_insurance_service_health(client):
    response = client.get("/insurance/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "insurance-service"}

def test_create_and_get_insurance_policy(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    policy_params = {
        "order_id": 300,
        "insurance_type": "kasko",
        "coverage_amount": 2500000.00,
        "vehicle_make": "BMW",
        "vehicle_model": "X5",
        "vehicle_year": 2023,
        "vehicle_vin": "VIN1234567890",
        # additional_coverages is a dict query param in insurance-service; omit to avoid encoding issues
    }
    response = client.post("/insurance/quotes", headers=headers, params=policy_params)
    assert response.status_code == 200, f"Failed to create insurance quote: {response.text}"
    policy_data = response.json()
    assert policy_data["insurance_type"] == "kasko"
    assert policy_data["coverage_amount"] == 2500000.00
    assert "policy_id" in policy_data

    # Получить все полисы пользователя
    response = client.get("/insurance/policies", headers=headers)
    assert response.status_code == 200, f"Failed to get user policies: {response.text}"
    policies = response.json()
    assert any(p["id"] == policy_data["policy_id"] for p in policies)


# Пример теста для проверки health check Auth Service через API Gateway
def test_auth_service_health(client):
    response = client.get("/auth/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "auth-service"}

# Пример теста для получения информации о текущем пользователе
def test_get_current_user_info(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    user_info = response.json()
    assert user_info["email"] == TEST_USER_EMAIL
    assert user_info["full_name"] == TEST_USER_FULL_NAME
    assert user_info["id"] == USER_ID
    assert user_info["role"] == "client"
