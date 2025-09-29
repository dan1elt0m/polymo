FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

ARG JAVA_PACKAGE=openjdk-21-jre-headless

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ${JAVA_PACKAGE} \
        build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sfn $(dirname $(dirname $(readlink -f $(which java)))) /usr/lib/jvm/default-jvm

ENV JAVA_HOME=/usr/lib/jvm/default-jvm \
    PATH="${JAVA_HOME}/bin:${PATH}" \
    PYSPARK_PYTHON=python \
    PYSPARK_DRIVER_PYTHON=python

WORKDIR /workspace

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install -e .[builder]

COPY docs ./docs
COPY builder-ui ./builder-ui

EXPOSE 8000

CMD ["uvicorn", "polymo.builder.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
