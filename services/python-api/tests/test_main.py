from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from main import app

client = TestClient(app)

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["healthy"] == True
