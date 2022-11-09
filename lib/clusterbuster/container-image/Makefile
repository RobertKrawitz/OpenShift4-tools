.PHONY: build push build-all push-all build-workloads push-workloads

push-all: build-all push push-workloads
build-all: build build-workloads
ARCH=$(shell uname -m)

build:
	buildah bud --build-arg ARCH=$(ARCH) -t clusterbuster .

push: build
	podman push localhost/clusterbuster quay.io/rkrawitz/clusterbuster:$(ARCH)-latest

build-workloads: push
	buildah bud --build-arg ARCH=$(ARCH) -t clusterbuster-workloads -f Dockerfile.workloads .

push-workloads: build
	podman push localhost/clusterbuster-workloads quay.io/rkrawitz/clusterbuster-workloads:$(ARCH)-latest
