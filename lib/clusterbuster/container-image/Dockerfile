FROM quay.io/fedora/fedora-minimal:latest

RUN microdnf --setopt=install_weak_deps=0 install -y \
    python3 \
    util-linux \
    && \
    microdnf -y clean all && \
    rm -rf /var/cache/yum
