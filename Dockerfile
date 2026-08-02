FROM denoland/deno:bin-2.3.0 AS deno
FROM python:3.12-slim
COPY --from=deno /deno /usr/local/bin/deno
WORKDIR /app
COPY . .
RUN python -m pip install --no-cache-dir .
ENTRYPOINT ["aitube-transcript"]
