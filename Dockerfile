FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV FLASK_APP=main.py
ENV PORT=8080
EXPOSE 8080

# Start the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
