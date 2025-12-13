FROM python:3.11-slim
WORKDIR /usr/src/app
# Copy the requirements to container and install
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt
# Copy the source code to container
COPY . .
ENV PYTHONPATH=/usr/src/app:/usr/src/app/app
CMD ["python", "app/main.py"]