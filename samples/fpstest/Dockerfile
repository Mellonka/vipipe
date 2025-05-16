FROM ubuntu:22.04

# Избегаем интерактивных запросов при установке пакетов
ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем необходимые пакеты
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    git \
    wget

RUN rm -rf /var/lib/apt/lists/* 

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY detector.py renderer.py /app/

RUN git clone https://github.com/Mellonka/vipipe

WORKDIR /app

ENV PYTHONPATH=/vipipe/src \
PYTHONUNBUFFERED=1
