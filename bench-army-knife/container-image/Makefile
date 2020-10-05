.PHONY: build push

build:
	buildah bud -t bench-army-knife .

push: build
	podman push localhost/bench-army-knife quay.io/rkrawitz/bench-army-knife:latest

base:
	buildah bud -t bench-army-base -f Dockerfile.base

push-base: base
	podman push localhost/bench-army-base quay.io/rkrawitz/bench-army-base:latest

