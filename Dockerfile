FROM ubuntu:20.04

# Отключаем интерактивные вопросы во время установки
ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем необходимое
RUN apt-get update && apt-get install -y \
    apache2 \
    openssh-server \
    netcat \
    tcpdump \
    curl \
    iputils-ping \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Создаем папку для данных (монтируется как volume)
WORKDIR /data

# Настраиваем SSH (быстрая настройка для демо)
RUN mkdir /var/run/sshd
RUN echo 'root:password' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# SSH keys fix
RUN ssh-keygen -A

CMD ["/bin/bash"]