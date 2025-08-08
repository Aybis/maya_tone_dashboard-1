SHELL := /bin/zsh

.PHONY: dev backend frontend build-frontend

dev:
	chmod +x ./dev.sh || true
	./dev.sh

backend:
	PYTHONUNBUFFERED=1 python backend/app.py

frontend:
	cd frontend && npm run dev

build-frontend:
	cd frontend && npm run build
