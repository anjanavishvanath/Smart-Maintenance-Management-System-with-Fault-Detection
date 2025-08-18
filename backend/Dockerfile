FROM python:3.11-slim

WORKDIR /usr/src/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app
ENV PYTHONPATH=/usr/src/app

CMD ["python", "app/main.py"]
