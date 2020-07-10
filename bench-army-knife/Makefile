.PHONY: build push

build:
	buildah bud -t bench-army-knife .

push:
	podman push localhost/bench-army-knife quay.io/rkrawitz/bench-army-knife:latest
