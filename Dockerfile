FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY flight_search3.py .
CMD ["python", "-u", "flight_search3.py"]