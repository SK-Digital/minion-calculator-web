FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app.py hypixel_minion_data.json ./
COPY templates/ templates/
COPY static/ static/

# Create a non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"] 