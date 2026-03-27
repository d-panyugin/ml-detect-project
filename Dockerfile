# Базовый образ
FROM ubuntu:22.04

# Отключаем интерактивные вопросы во время установки (DEBIAN_FRONTEND=noninteractive)
ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем всё сразу: пинги, керл, перф, тсидамп, веб-сервер, ssh
RUN apt-get update && apt-get install -y \
    iputils-ping \
    curl \
    iperf3 \
    tcpdump \
    net-tools \
    apache2 \
    openssh-server \
    iperf3 \
    && rm -rf /var/lib/apt/lists/*

# Создаем папку для данных
RUN mkdir -p /data

# Задаем команду запуска (чтобы контейнер не падал)
CMD tail -f /dev/null
