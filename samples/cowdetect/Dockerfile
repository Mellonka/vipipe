FROM ubuntu:22.04

# Избегаем интерактивных запросов при установке пакетов
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    git

RUN rm -rf /var/lib/apt/lists/* 

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY temp/ /app/temp/
COPY main.py /app/

RUN git clone https://github.com/Mellonka/vipipe

WORKDIR /app

ENV PYTHONPATH=/vipipe/src \
    PYTHONUNBUFFERED=1
