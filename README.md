```bash
# traditional way to start the API directly
openbb-api --app main.py --exclude '"/api/v1/*"' --reload
```

```bash
openbb-api --app main.py --reload
openbb-api --app src/openbb_app/main.py --reload
```

# using uvx
When openbb-api is executed, the health check endpoint will be available at `http://0.0.0.0:6900/health`.

```bash
uv run openbb-api --app src/openbb_app/main.py
```

Start the virtual environment and run the following command to start the API:
```shell
uvicorn openbb_app.main:app
```

## Using **Docker**

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) installed

### Quick Start

```bash
# Build the Docker image
docker build -t openbb-app .

# Start the service (detached mode)
docker compose up -d

# View logs
docker compose logs -f

# Stop the service
docker compose down
```

### Accessing the Application

Once the container is running, access the API at:
- API: http://localhost:8001/api/docs
- Health Check: http://localhost:8001/api/openapi.json

### Environment Configuration

Create a `.env` file in the project root with your API keys:

```env
TUSHARE_API_KEY=your_tushare_api_key
AGENT_HOST_URL=your_agent_host_url
APP_API_KEY=your_app_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### Development with Live Reload

The Docker setup supports live code reloading. Changes to source files on your host machine will be reflected immediately without rebuilding the image, as long as the volume mount is active.

### Container Security

The container runs as a non-root user (`appuser`) for enhanced security. The application listens on port 8001 inside the container, which is mapped to the same port on the host.

## Using **TestPyPI**

## 1. Configure `uv` for TestPyPI

You can either pass the URL every time or add it to your `pyproject.toml` so `uv` knows where to find it. I recommend adding it to your config:

**Add this to your `pyproject.toml`:**

Ini, TOML

```
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true
```

---

## 2. Build and Publish

Now, build your project and tell `uv` to send it to the `testpypi` index you just defined.

Bash

```
# Clear old builds first
rm -rf dist/

# Build the distribution
uv build

# Publish to TestPyPI
# You'll be prompted for a token (username: __token__)
uv publish --index testpypi
```

---

## 3. The "Moment of Truth": Testing with `uvx`

This is the most important step. You want to see if a user can run your app using `uvx` by pulling it from TestPyPI.

Since TestPyPI often doesn't have all the dependencies (like `openbb` or `fastapi`), you have to tell `uv` to look at **both** TestPyPI (for your app) and the real PyPI (for the dependencies).

**Run this command from a different folder:**

Bash

```
uvx --index https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ openbb-app
```

### What to check:

- **Does the server start?** If it boots to `http://0.0.0.0:8000`, your entry point is correct.

- **Are images/README missing?** Check the project page on `test.pypi.org` to see if your descriptions rendered correctly.

---

## 4. Cleaning Up for the "Real" Launch

Once you are happy with how it looks on TestPyPI:

1. **Change the Version:** Increment the version in `pyproject.toml` (e.g., `0.1.0` -> `0.1.1`).

2. **Publish for real:** ```bash
   
   uv build
   
   uv publish # This defaults to the real PyPI
