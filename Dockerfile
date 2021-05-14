FROM python:3.9-slim-buster AS builder
RUN apt-get update \
&& apt-get install gcc make -y

WORKDIR /app/aiohttp_scrap
RUN python -m venv venv --upgrade-deps
RUN venv/bin/python -m pip install --upgrade pip setuptools

COPY requirements.txt /app/aiohttp_scrap/
RUN venv/bin/pip install --no-cache-dir -r requirements.txt \
&& find /app/aiohttp_scrap/venv \( -type d -a -name test -o -name tests \) \
-o \( -type f -a -name '*.pyc' -o -name '*.pyo' \) -exec rm -rf '{}' \+

FROM python:3.9-slim-buster
WORKDIR /app/aiohttp_scrap

COPY --from=builder /app/aiohttp_scrap /app/aiohttp_scrap

ENV PATH="/app/aiohttp_scrap/venv/bin:$PATH"

COPY . /app/aiohttp_scrap/
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]