#!/usr/bin/env python3
"""
Скрипт для запуска микросервисной системы автосалона
Запуск: python start_services.py
"""

import subprocess
import sys
import time
import os

def run_command(command, description):
    """Запуск команды с выводом статуса"""
    print(f"🚀 {description}...")
    try:
        if sys.platform == "win32":
            # Для Windows используем shell=True
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        else:
            # Для Unix-like систем
            result = subprocess.run(command.split(), check=True, capture_output=True, text=True)
        print(f"✅ {description} - успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ошибка: {e}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return False

def check_docker():
    """Проверка наличия Docker"""
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"🐳 Docker найден: {result.stdout.strip()}")
            return True
        else:
            print("❌ Docker не найден")
            return False
    except FileNotFoundError:
        print("❌ Docker не установлен")
        return False

def check_docker_compose():
    """Проверка наличия Docker Compose"""
    try:
        result = subprocess.run(["docker-compose", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"🐳 Docker Compose найден: {result.stdout.strip()}")
            return True
        else:
            print("❌ Docker Compose не найден")
            return False
    except FileNotFoundError:
        # Попробуем docker compose (новый синтаксис)
        try:
            result = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"🐳 Docker Compose (новый): {result.stdout.strip()}")
                return True
            else:
                print("❌ Docker Compose не найден")
                return False
        except FileNotFoundError:
            print("❌ Docker Compose не установлен")
            return False

def wait_for_services():
    """Ожидание запуска сервисов с health checks"""
    print("⏳ Ожидание запуска сервисов (с health checks)...")

    # Проверяем health каждого сервиса
    services_to_check = [
        ("http://localhost:8001/health", "Auth Service"),
        ("http://localhost:8002/health", "Payment Service"),
        ("http://localhost:8003/health", "Financing Service"),
        ("http://localhost:8004/health", "Insurance Service"),
        ("http://localhost:8000/health", "API Gateway"),
    ]

    import requests
    max_attempts = 30  # 30 попыток по 5 секунд = 2.5 минуты максимум

    for attempt in range(max_attempts):
        all_healthy = True

        for url, name in services_to_check:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print(f"✅ {name} - готов")
                else:
                    print(f"⏳ {name} - статус {response.status_code}")
                    all_healthy = False
            except requests.RequestException:
                print(f"⏳ {name} - не готов")
                all_healthy = False

        if all_healthy:
            print("✅ Все сервисы запущены и готовы!")
            return

        print(f"⏳ Попытка {attempt + 1}/{max_attempts}, ожидание 5 секунд...")
        time.sleep(5)

    print("⚠️ Не все сервисы запустились, но продолжаем...")

def show_service_info():
    """Вывод информации о запущенных сервисах"""
    print("\n" + "=" * 60)
    print("🎉 Микросервисная система Автосалон запущена!")
    print("=" * 60)
    print("\n📍 Доступ к сервисам:")
    print("  🌐 API Gateway:        http://localhost:8000")
    print("  🔐 Auth Service:       http://localhost:8001")
    print("  💳 Payment Service:    http://localhost:8002")
    print("  💰 Financing Service:  http://localhost:8003")
    print("  🛡️  Insurance Service:  http://localhost:8004")
    print("  📊 RabbitMQ:           http://localhost:15672 (guest/guest)")
    print("\n💾 Базы данных (для внешнего доступа):")
    print("  🔐 Auth DB:            localhost:54321 (auth_db)")
    print("  💳 Payment DB:         localhost:54322 (payment_db)")
    print("  💰 Financing DB:       localhost:54323 (financing_db)")
    print("  🛡️  Insurance DB:       localhost:54324 (insurance_db)")
    print("  👤 Username: user, Password: password")
    print("\n📚 API Документация (Swagger UI):")
    print("  🌐 API Gateway:        http://localhost:8000/docs")
    print("  🔐 Auth Service:       http://localhost:8001/docs")
    print("  💳 Payment Service:    http://localhost:8002/docs")
    print("  💰 Financing Service:  http://localhost:8003/docs")
    print("  🛡️  Insurance Service:  http://localhost:8004/docs")
    print("\n🧪 Для тестирования запустите: python test_api.py")
    print("\n🛑 Для остановки: Ctrl+C или docker-compose down")
    print("=" * 60)

def main():
    """Основная функция"""
    print("🚗 Запуск микросервисной системы Автосалон")
    print("=" * 50)

    # Проверка наличия Docker
    if not check_docker():
        print("\n💡 Установите Docker: https://docs.docker.com/get-docker/")
        sys.exit(1)

    # Проверка наличия Docker Compose
    if not check_docker_compose():
        print("\n💡 Установите Docker Compose: https://docs.docker.com/compose/install/")
        sys.exit(1)

    # Проверка наличия docker-compose.yml
    if not os.path.exists("docker-compose.yml"):
        print("❌ Файл docker-compose.yml не найден в текущей директории")
        sys.exit(1)

    print("\n🐳 Запуск Docker Compose...")

    # Остановка предыдущих контейнеров (на всякий случай)
    run_command("docker-compose down", "Остановка предыдущих контейнеров")

    # Сборка и запуск сервисов
    if not run_command("docker-compose up --build -d", "Сборка и запуск сервисов"):
        print("❌ Ошибка запуска сервисов")
        sys.exit(1)

    # Ожидание запуска
    wait_for_services()

    # Вывод информации
    show_service_info()

    # Предложение запустить тестирование
    try:
        input("\n⏳ Нажмите Enter для запуска автоматического тестирования API...")
        print("\n🧪 Запуск тестирования API...")
        run_command("python test_api.py", "Тестирование API")
    except KeyboardInterrupt:
        print("\n\n👋 Выход...")

    print("\n💡 Для остановки сервисов выполните: docker-compose down")

if __name__ == "__main__":
    main()