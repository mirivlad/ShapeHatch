# ShapeHatch в Portainer

ShapeHatch состоит из двух контейнеров: `web` (Nginx + интерфейс) и `api` (FastAPI). Приложение доступно по HTTP на порту 8086, API проксируется через Nginx. Постоянных Docker-томов на текущем этапе нет: настройки редактора сохраняются в браузере.

## Развёртывание

1. В Portainer выберите **Stacks → Add stack → Repository**.
2. Имя стека: `shapehatch`.
3. Repository URL: `https://github.com/mirivlad/ShapeHatch`.
4. Repository reference: `refs/heads/main`; Compose path: `portainer-stack.yml`.
5. При необходимости задайте переменную `SHAPEHATCH_HTTP_PORT` (по умолчанию `8086`).
6. Нажмите **Deploy the stack**. Дождитесь запуска двух контейнеров.
7. Откройте `http://<адрес-Docker-хоста>:8086` и проверьте `/api/health`.

Для закрытых образов GHCR требуется реестр с доступом к пакетам. В Portainer он задаётся через **Registries → Add registry → GitHub**; для публичных образов отдельная авторизация не нужна.

## Обновления

Пуш в `main` запускает GitHub Actions `Publish Docker images`. После успешного прохождения тестов публикуются образы `ghcr.io/mirivlad/shapehatch-api:latest` и `ghcr.io/mirivlad/shapehatch-web:latest`, а также теги с SHA коммита.

В Portainer откройте **Stacks → shapehatch → Pull and redeploy**; убедитесь, что включено повторное скачивание образов (re-pull image), и подтвердите обновление. Стек загружает новые готовые образы и пересоздаёт контейнеры — выполнять `docker compose build/up` на сервере не нужно.

Файл `compose.yaml` оставлен для локальной разработки и сборки из исходников, а `portainer-stack.yml` — для развёртывания из готовых образов.

## Проверка и диагностика

- `GET http://<адрес-Docker-хоста>:8086/api/health` должен вернуть `{"ok":true,...}`.
- Логи доступны в **Containers → shapehatch-api-1 / shapehatch-web-1 → Logs**.
- Если обновление не видно, проверьте успешность workflow и какой digest образа используется в контейнере.
- Если порт 8086 занят, измените переменную `SHAPEHATCH_HTTP_PORT` в стеке.
