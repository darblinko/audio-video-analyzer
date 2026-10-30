"""Start the API server: uv run av-analyzer."""

import argparse
import logging
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the audio/video analyzer API server.")
    parser.add_argument("--host", default=os.getenv("AVA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("AVA_PORT", "8000")))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run("av_analyzer.server:create_app", factory=True, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
