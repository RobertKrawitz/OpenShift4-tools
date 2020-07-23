FROM quay.io/rkrawitz/bench-army-base:latest

RUN sed -i -e "s/.*PermitRootLogin.*/PermitRootLogin yes ##/" \
           -e "s/.*Port .*/Port 2022 ##/" /etc/ssh/sshd_config && \
    ssh-keygen -A && \
    ssh-keygen -t rsa -q -f "$HOME/.ssh/id_rsa" -N '' -C bench-army-knife && \
    cat "$HOME/.ssh/id_rsa.pub" >> "$HOME/.ssh/authorized_keys" && \
    chmod 600 "$HOME/.ssh/authorized_keys" && \
    mkdir /var/lib/pbench
COPY bootstrap.sh \
     run-pbench-agent \
     run-pbench-agent-ext \
     run-pbench-controller \
     run-pbench-controller-ext \
     sync.pl \
     sync_to.pl \
     /usr/local/bin
