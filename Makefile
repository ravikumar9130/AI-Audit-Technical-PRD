# Makefile for Audit AI

.PHONY: help build up down logs test clean deploy k8s-deploy k8s-delete

# Default target
help:
	@echo "Audit AI - Available Commands:"
	@echo "  make build        - Build all Docker images"
	@echo "  make up           - Start all services with Docker Compose"
	@echo "  make down         - Stop all services"
	@echo "  make logs         - View logs from all services"
	@echo "  make test         - Run tests"
	@echo "  make clean        - Remove all containers and volumes"
	@echo "  make k8s-deploy   - Deploy to Kubernetes"
	@echo "  make k8s-delete   - Remove from Kubernetes"

# Docker Compose commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	docker-compose exec api pytest tests/

clean:
	docker-compose down -v
	docker system prune -f

# Database commands
migrate:
	docker-compose exec api alembic upgrade head

makemigrations:
	docker-compose exec api alembic revision --autogenerate -m "$(message)"

shell:
	docker-compose exec api bash

# Kubernetes commands
k8s-deploy:
	kubectl apply -f kubernetes/manifests/

k8s-delete:
	kubectl delete -f kubernetes/manifests/

k8s-helm-install:
	helm install audit-ai kubernetes/helm-charts/ -n auditai --create-namespace

k8s-helm-upgrade:
	helm upgrade audit-ai kubernetes/helm-charts/ -n auditai

k8s-helm-delete:
	helm delete audit-ai -n auditai

# Development commands
dev-api:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	cd backend && celery -A workers.celery_app worker --loglevel=info --pool=prefork

dev-frontend:
	cd frontend && npm run dev

# Production build
prod-build:
	docker build -t auditai/api:latest -f backend/Dockerfile backend/
	docker build -t auditai/worker:latest -f backend/Dockerfile.worker backend/
	docker build -t auditai/frontend:latest frontend/

prod-push:
	docker push auditai/api:latest
	docker push auditai/worker:latest
	docker push auditai/frontend:latest
