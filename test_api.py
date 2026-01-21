#!/usr/bin/env python3
"""
Простой скрипт для тестирования API микросервисов автосалона
Запуск: python test_api.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_auth_service():
    """Тестирование сервиса аутентификации"""
    print("=== Тестирование Auth Service ===")

    # Регистрация пользователя
    register_data = {
        "email": "test@example.com",
        "full_name": "Тестовый Пользователь",
        "password": "password123",
        "phone": "+7-999-123-45-67",
        "role": "client"
    }

    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        print(f"Регистрация: {response.status_code}")
        if response.status_code == 200:
            print("✓ Пользователь зарегистрирован")
        else:
            print(f"✗ Ошибка: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")
        return None

    # Получение токена
    token_data = {
        "username": "test@example.com",
        "password": "password123"
    }

    try:
        response = requests.post(f"{BASE_URL}/auth/token", data=token_data)
        print(f"Получение токена: {response.status_code}")
        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens["access_token"]
            print("✓ Токен получен")
            return access_token
        else:
            print(f"✗ Ошибка: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")

    return None

def test_payment_service(token):
    """Тестирование сервиса платежей"""
    print("\n=== Тестирование Payment Service ===")

    headers = {"Authorization": f"Bearer {token}"}

    # Создание платежа
    payment_data = {
        "order_id": 1,
        "amount": 1500000.00,
        "method": "card",
        "description": "Тестовый платеж за автомобиль"
    }

    try:
        response = requests.post(f"{BASE_URL}/payment/payments", json=payment_data, headers=headers)
        print(f"Создание платежа: {response.status_code}")
        if response.status_code == 200:
            payment = response.json()
            print(f"✓ Платеж создан, ID: {payment['payment_id']}")
            return payment["payment_id"]
        else:
            print(f"✗ Ошибка: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")

    return None

def test_financing_service(token):
    """Тестирование сервиса кредитования"""
    print("\n=== Тестирование Financing Service ===")

    headers = {"Authorization": f"Bearer {token}"}

    # Расчет кредитных условий
    try:
        response = requests.get(f"{BASE_URL}/financing/calculator?vehicle_price=2000000&down_payment=400000&term_months=36&employment_status=employed")
        print(f"Расчет кредита: {response.status_code}")
        if response.status_code == 200:
            calc = response.json()
            print(f"✓ Расчет выполнен. Ежемесячный платеж: {calc['monthly_payment']} руб.")
        else:
            print(f"✗ Ошибка: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")

    # Создание заявки на кредит
    financing_data = {
        "order_id": 1,
        "vehicle_price": 2000000.00,
        "down_payment": 400000.00,
        "term_months": 36,
        "financing_type": "car_loan",
        "employment_status": "employed",
        "monthly_income": 80000.00
    }

    try:
        response = requests.post(f"{BASE_URL}/financing/applications", json=financing_data, headers=headers)
        print(f"Создание заявки на кредит: {response.status_code}")
        if response.status_code == 200:
            app = response.json()
            print(f"✓ Заявка создана, ID: {app['application_id']}, платеж: {app['monthly_payment']} руб.")
        else:
            print(f"✗ Ошибка: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")

def test_insurance_service(token):
    """Тестирование сервиса страхования"""
    print("\n=== Тестирование Insurance Service ===")

    headers = {"Authorization": f"Bearer {token}"}

    # Расчет страховой премии
    try:
        response = requests.get(f"{BASE_URL}/insurance/calculator?insurance_type=kasko&coverage_amount=2000000&vehicle_year=2023&driver_age=35&accident_history=false")
        print(f"Расчет страховки: {response.status_code}")
        if response.status_code == 200:
            calc = response.json()
            print(f"✓ Расчет выполнен. Премия: {calc['premium_amount']} руб.")
        else:
            print(f"✗ Ошибка: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")

    # Создание страхового полиса
    insurance_data = {
        "order_id": 1,
        "insurance_type": "kasko",
        "coverage_amount": 2000000.00,
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_year": 2023,
        "vehicle_vin": "1HGCM82633A123456"
    }

    try:
        response = requests.post(f"{BASE_URL}/insurance/quotes", json=insurance_data, headers=headers)
        print(f"Создание страховки: {response.status_code}")
        if response.status_code == 200:
            policy = response.json()
            print(f"✓ Полис создан, номер: {policy['policy_number']}, премия: {policy['premium_amount']} руб.")
        else:
            print(f"✗ Ошибка: {response.text}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")

def main():
    """Основная функция тестирования"""
    print("🚗 Тестирование микросервисной системы Автосалон")
    print("=" * 50)

    # Ожидание запуска сервисов
    print("Ожидание запуска сервисов...")
    time.sleep(10)

    # Тестирование auth service
    token = test_auth_service()
    if not token:
        print("❌ Невозможно продолжить тестирование без токена")
        return

    # Тестирование остальных сервисов
    test_payment_service(token)
    test_financing_service(token)
    test_insurance_service(token)

    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
    print("\n📖 Документация API доступна:")
    print(f"  - API Gateway: {BASE_URL}/docs")
    print(f"  - Auth Service: http://localhost:8001/docs")
    print(f"  - Payment Service: http://localhost:8002/docs")
    print(f"  - Financing Service: http://localhost:8003/docs")
    print(f"  - Insurance Service: http://localhost:8004/docs")

if __name__ == "__main__":
    main()