from av_analyzer.server import MULTIPART_OVERHEAD_BYTES

from .conftest import wav_bytes

BOUNDARY = "testboundary"


def _multipart(parts: list[tuple[str, str, bytes]]) -> bytes:
    body = b""
    for name, filename, payload in parts:
        body += (
            (
                f"--{BOUNDARY}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
            + payload
            + b"\r\n"
        )
    return body + f"--{BOUNDARY}--\r\n".encode()


def _post_raw(client, body, headers=None):
    return client.post(
        "/api/upload",
        content=body,
        headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}", **(headers or {})},
    )


def test_declared_body_over_the_limit_is_413_before_parsing(make_client, settings):
    client = make_client(max_upload_bytes=1024)
    body = _multipart([("audio", "clip.wav", b"\x00" * (MULTIPART_OVERHEAD_BYTES + 2048))])
    assert _post_raw(client, body).status_code == 413
    assert list(settings.upload_dir.iterdir()) == []


def test_chunked_body_over_the_limit_is_413(make_client, settings):
    client = make_client(max_upload_bytes=1024)
    body = _multipart([("audio", "clip.wav", b"\x00" * (MULTIPART_OVERHEAD_BYTES + 2048))])

    def chunks():
        for start in range(0, len(body), 4096):
            yield body[start : start + 4096]

    response = _post_raw(client, chunks())
    assert response.status_code == 413
    assert list(settings.upload_dir.iterdir()) == []


def test_unexpected_file_parts_are_rejected(make_client, settings):
    client = make_client()
    body = _multipart([("audio", "clip.wav", wav_bytes()), ("extra", "more.wav", wav_bytes())])
    assert _post_raw(client, body).status_code == 422
    assert list(settings.upload_dir.iterdir()) == []


def test_repeated_audio_parts_are_rejected(make_client):
    client = make_client()
    body = _multipart([("audio", "a.wav", wav_bytes()), ("audio", "b.wav", wav_bytes())])
    assert _post_raw(client, body).status_code == 422
