# Build image
FROM python:3.7-slim as builder

# Setup virtualenv
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install build deps
RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential

# Install runtime deps
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Production image
FROM python:3.7-slim as lnbits

# Run as non-root
USER 1000:1000

# Copy over virtualenv
ENV VIRTUAL_ENV="/opt/venv"
COPY --from=builder --chown=1000:1000 $VIRTUAL_ENV $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy in app source
WORKDIR /app
COPY --chown=1000:1000 src /app/src

EXPOSE 5002

CMD python src/app.py