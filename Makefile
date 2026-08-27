.PHONY: install dev demo smoke-test test deploy

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	cp -n .env.example .env || true

dev:
	.venv/bin/uvicorn warden.gateway:app --reload --port 8080

demo:
	.venv/bin/python -m demo.run_demo

smoke-test:
	.venv/bin/python -m scripts.smoke_test_models

test:
	.venv/bin/pytest -q

deploy:
	bash scripts/setup_gcp.sh
	bash scripts/deploy_cloud_run.sh
