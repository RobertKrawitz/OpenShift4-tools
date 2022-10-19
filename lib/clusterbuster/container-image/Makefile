.PHONY: build push build-all push-all build-workloads push-workloads

push-all: build-all push push-workloads
build-all: build build-workloads

build:
	buildah bud -t clusterbuster .

push: build
	podman push localhost/clusterbuster quay.io/rkrawitz/clusterbuster:latest

build-workloads: build
	buildah bud -t clusterbuster-workloads -f Dockerfile.workloads .

push-workloads: build
	podman push localhost/clusterbuster-workloads quay.io/rkrawitz/clusterbuster-workloads:latest
