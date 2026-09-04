FROM ghcr.io/berriai/litellm:main-latest
COPY litellm-config.yaml /app/config.yaml
ENV PORT=8080
EXPOSE 8080
CMD ["--config", "/app/config.yaml", "--port", "8080", "--num_workers", "1"]
