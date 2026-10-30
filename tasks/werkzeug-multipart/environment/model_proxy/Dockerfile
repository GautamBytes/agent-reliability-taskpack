FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
COPY proxy.py /opt/proxy.py
RUN mkdir -p /logs/proxy
HEALTHCHECK --interval=2s --timeout=2s --retries=20 CMD python3 -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:3128/health').status == 200"
CMD ["python3", "-I", "/opt/proxy.py"]
