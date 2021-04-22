FROM quay.io/rkrawitz/bench-army-base:latest

RUN sed -i -e "s/.*PermitRootLogin.*/PermitRootLogin yes ##/" \
           -e "s/.*Port .*/Port 2022 ##/" /etc/ssh/sshd_config && \
    ssh-keygen -A && \
    ssh-keygen -t rsa -q -f "$HOME/.ssh/id_rsa" -N '' -C bench-army-knife && \
    cat "$HOME/.ssh/id_rsa.pub" >> "$HOME/.ssh/authorized_keys" && \
    chmod 600 "$HOME/.ssh/authorized_keys" && \
    mkdir /var/lib/pbench && \
    echo "export LANG=en_UT.UTF-8" >> /etc/environment && \
    echo "export LANGUAGE=en_UT.UTF-8" >> /etc/environment && \
    echo "export LC_ALL=C" >> /etc/environment && \
    groupadd pbench && \
    useradd -d /var/tmp -g pbench pbench && \
    rm -f /opt/pbench-agent/config/pbench-agent.cfg
COPY bootstrap.sh \
     create-tunnel \
     find-free-ports \
     mini-sshd \
     run-pbench-agent-container \
     run-pbench-controller \
     sync.pl \
     sync_to.pl \
     /usr/local/bin
