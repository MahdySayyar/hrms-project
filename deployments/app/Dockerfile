FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/hrms
COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt \
    && python -m pip check \
    && groupadd --gid 10001 hrms \
    && useradd --uid 10001 --gid hrms --no-create-home hrms

COPY --chown=hrms:hrms app ./app
COPY --chown=hrms:hrms templates ./templates
COPY --chown=hrms:hrms static ./static
COPY --chown=hrms:hrms deployments/app/entrypoint.py ./entrypoint.py

USER hrms
EXPOSE 8000
CMD ["python", "entrypoint.py"]
