ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:${PATH}"

# The scanners live in a virtual environment and come from requirements.txt, which pins every package, the ones they
# depend on included, with its hashes: a package that changed on PyPI fails the build instead of entering the image
# (ADR-0034). After changing requirements.in, regenerate it:
#   uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes --no-header -o requirements.txt
# PyPI has no armv7 wheel of msgpack, and the image has no compiler: MSGPACK_PUREPYTHON builds it as pure Python
# there. Other platforms install the prebuilt wheels, where the variable changes nothing.
COPY requirements.txt /tmp/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && python3 -m venv /opt/venv \
    && MSGPACK_PUREPYTHON=1 /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY scanner.py guard.py /opt/marketplace_guard/
COPY gate /opt/marketplace_guard/gate
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
