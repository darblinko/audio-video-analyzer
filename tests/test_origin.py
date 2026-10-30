import pytest
from starlette.websockets import WebSocketDisconnect

ALLOWED = "http://localhost:5173"
UNTRUSTED = "http://attacker.example"


def test_post_from_an_untrusted_origin_is_403_and_starts_nothing(make_client):
    client = make_client()
    response = client.post("/api/samples/tone-440hz/analyze", headers={"origin": UNTRUSTED})
    assert response.status_code == 403
    assert client.get("/api/results").json()["count"] == 0


def test_post_from_the_frontend_origin_is_accepted(make_client):
    client = make_client()
    response = client.post("/api/samples/tone-440hz/analyze", headers={"origin": ALLOWED})
    assert response.status_code == 202


def test_post_without_an_origin_is_accepted(make_client):
    assert make_client().post("/api/samples/tone-440hz/analyze").status_code == 202


def test_websocket_from_an_untrusted_origin_is_refused(make_client):
    client = make_client()
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws", headers={"origin": UNTRUSTED}) as websocket,
    ):
        websocket.receive_json()


def test_websocket_from_the_frontend_origin_connects(make_client):
    client = make_client()
    with client.websocket_connect("/ws", headers={"origin": ALLOWED}) as websocket:
        client.post("/api/samples/tone-440hz/analyze")
        assert websocket.receive_json()["type"] == "progress"
