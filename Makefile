.PHONY: help up down reset logs status test frontend-install frontend-dev frontend-build

help:
	@echo "make up             构建并启动全部 Docker 服务"
	@echo "make down           停止服务并保留数据"
	@echo "make reset          停止服务并删除 Docker 数据卷"
	@echo "make logs           跟踪全部服务日志"
	@echo "make status         查看容器状态"
	@echo "make test           运行后端测试"
	@echo "make frontend-build 构建前端生产包"

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down --volumes

logs:
	docker compose logs -f

status:
	docker compose ps

test:
	.venv/bin/python -m pytest -q

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
