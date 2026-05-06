from fastapi import FastAPI
from prometheus_client import Counter, generate_latest
from starlette.responses import PlainTextResponse

app = FastAPI()
REQUEST_COUNT = Counter("requests_total", "Total requests", ["endpoint"])

@app.get("/")
def root():
    REQUEST_COUNT.labels(endpoint="/").inc()
    return {"status": "ok", "service": "python-api"}

@app.get("/health")
def health():
    return {"healthy": True}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return generate_latest()
