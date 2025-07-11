FROM python:3.11-slim

WORKDIR /app

COPY app.py hypixel_minion_data.json ./
COPY templates/ templates/
COPY static/ static/

RUN pip install --no-cache-dir flask requests

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
EXPOSE 5000

CMD ["flask", "run"] 