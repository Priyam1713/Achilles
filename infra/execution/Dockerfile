FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates git git-lfs curl wget jq ripgrep fd-find \
    python3 python3-pip python3-venv nodejs npm \
    build-essential cmake ninja-build pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1500 -s /bin/bash sandbox
USER sandbox
WORKDIR /workspace
CMD ["bash"]
