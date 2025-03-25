format:
	ruff format
	ruff check --fix


bnr:
	docker build -t base-gst-01 -f docker/Dockerfile.ubuntu.gstreamer .
	docker run -p 8081:8081 --rm -it base-gst-01 bash
