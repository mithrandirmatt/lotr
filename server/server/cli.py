import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", "-H", default="0.0.0.0")
    parser.add_argument("--port", "-p", type=int, default=8000)
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    uvicorn.run("server.server.app:app", host=args.host, port=args.port, reload=args.dev)


if __name__ == "__main__":
    main()
