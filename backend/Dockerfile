FROM python:3.11-slim

WORKDIR /usr/src/app
# copy requirements to container and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# copy app code to container
COPY ./app ./app

ENV PYTHONPATH=/usr/src/app

CMD ["python", "app/main.py"]
