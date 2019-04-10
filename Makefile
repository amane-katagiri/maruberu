all: build

conf/server.conf: maruberu/example-server.conf
	mkdir -p ./conf
ifneq ("$(wildcard conf/server.conf)","")
	diff -up ./maruberu/example-server.conf ./conf/server.conf || true
endif
	cp -i ./maruberu/example-server.conf ./conf/server.conf
	touch ./conf/server.conf

docker-compose.yml:
	./scripts/generate_docker-compose.yml $(shell find /dev/bus/usb/ -type c | sort) > docker-compose.yml

.PHONY: build up
build: conf/server.conf docker-compose.yml
	docker-compose build

up:
	docker-compose up
