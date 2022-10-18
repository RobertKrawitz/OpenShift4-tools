.PHONY: build push

build:
	buildah bud -t clusterbuster .

push: build
	podman push localhost/clusterbuster quay.io/rkrawitz/clusterbuster:latest
