# SWE Forge

SWE-bench dataset generator and evaluation harness.

## Installation

```bash
pip install swe-forge
```

## Usage

```bash
swe-forge version
```

## CI/CD Setup

This project automatically builds and publishes Docker images to two registries:

- **GitHub Container Registry (ghcr.io)**: Automatic, no configuration needed
- **Docker Hub**: Optional, requires secrets to be configured

### Docker Hub Configuration (Optional)

To enable Docker Hub publishing, add these secrets in your repository settings:

1. Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
2. Add the following secrets:

| Secret | Description |
|--------|-------------|
| `DOCKER_HUB_USERNAME` | Your Docker Hub username |
| `DOCKER_HUB_TOKEN` | Docker Hub access token (create at https://hub.docker.com/settings/security) |

### Creating a Docker Hub Access Token

1. Log in to [Docker Hub](https://hub.docker.com)
2. Go to **Account Settings** → **Security**
3. Click **New Access Token**
4. Choose **Read, Write, Delete** permissions
5. Copy the token immediately (shown only once)

### Behavior Without Docker Hub Secrets

The workflow will still function correctly:
- Images are published to `ghcr.io/{owner}/{repo}`
- Docker Hub push is skipped gracefully
- All features work with ghcr.io alone
