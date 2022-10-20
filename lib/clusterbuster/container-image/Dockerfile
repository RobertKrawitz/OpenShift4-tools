FROM quay.io/fedora/fedora-minimal:latest

RUN microdnf --setopt=install_weak_deps=0 install -y python3 && \
    microdnf -y clean all && \
    rm -rf /var/cache/yum
