FROM python:3.13-slim
WORKDIR /app
COPY section_01_technical/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY section_01_technical /app/section_01_technical
RUN useradd --uid 10001 --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn","section_01_technical.backend.payment_api:app","--host","0.0.0.0","--port","8000"]
