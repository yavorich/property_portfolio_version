celery_services = rabbitmq celery-beat celery
loc_services := postgres backend $(celery_services)
docker_compose := docker-compose -f docker-compose.yml

build:
	$(docker_compose) build $(c)

rebuild:
	$(docker_compose) up -d --build --force-recreate $(c)
	docker image prune -f

up:
	$(docker_compose) up -d $(c)

start:
	$(docker_compose) start $(c)

down:
	$(docker_compose) down $(c)

reup:
	$(docker_compose) down $(c)
	$(docker_compose) up -d $(c)

destroy:
	$(docker_compose) down --rmi all -v $(c)

stop:
	$(docker_compose) stop $(c)

restart:
	$(docker_compose) restart $(c)

restart-celery:
	$(docker_compose) restart $(celery_services)

logs:
	$(docker_compose) logs --tail=1000 -f $(c)

app-logs:
	$(docker_compose) logs --tail=1000 -f backend $(c)

celery-logs:
	$(docker_compose) logs --tail=1000 -f celery $(c)

app-bash:
	docker exec -it backend bash $(c)

db-bash:
	docker exec -it postgres bash $(c)

migrations:
	docker exec -it backend python manage.py makemigrations

migrate:
	docker exec -it backend python manage.py migrate

psql:
	docker exec -it postgres psql -U postgres

push:
	git push origin
	git checkout main-server
	git merge main --no-edit
	git push origin
	git checkout main
