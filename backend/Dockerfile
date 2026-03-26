FROM python:3.11-slim

WORKDIR /app

# Install git, curl, psmisc, build-essential (for Rust/C linking), Node.js, Docker CLI, Java, Go, Rust, and serve
RUN apt-get update && apt-get install -y git curl psmisc wget build-essential netcat-openbsd && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    curl -fsSL https://get.docker.com | sh && \
    npm install -g serve && \
    apt-get install -y default-jdk-headless maven && \
    wget -q https://go.dev/dl/go1.22.3.linux-amd64.tar.gz -O /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && rm /tmp/go.tar.gz && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/go/bin:/root/.cargo/bin:${PATH}"

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ ./src/

EXPOSE 8001

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
