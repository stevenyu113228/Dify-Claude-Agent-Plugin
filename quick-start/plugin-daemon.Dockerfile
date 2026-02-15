FROM langgenius/dify-plugin-daemon:0.5.3-local

# Install Node.js 22.x (LTS)
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg gosu && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main' > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user for running Claude CLI
# (Claude CLI refuses --dangerously-skip-permissions when running as root)
RUN useradd -m -s /bin/bash claude-runner && \
    mkdir -p /home/claude-runner/.claude && \
    chown -R claude-runner:claude-runner /home/claude-runner

# Create wrapper script that drops to non-root user via gosu
RUN printf '#!/bin/bash\nexec gosu claude-runner /usr/bin/claude "$@"\n' > /usr/local/bin/claude-wrapper && \
    chmod +x /usr/local/bin/claude-wrapper

# Verify installations
RUN node --version && npm --version && claude --version
