.PHONY: indexes

DOCKER_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

indexes:
	LOCAL_UID="$$(id -u)" LOCAL_GID="$$(id -g)" docker compose -f "$(DOCKER_DIR)/compose.yaml" run --build --rm indexes
