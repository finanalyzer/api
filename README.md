```bash
# traditional way to start the API directly
openbb-api --app main.py --exclude '"/api/v1/*"' --reload
```

```bash
openbb-api --app main.py --reload
openbb-api --app src/openbb_app/main.py --reload
```

# using uvx
You can also run the application using the `uvx` runner that comes with the
`uv` build system. This lets you invoke the same command from within the
project environment:

```bash
uvx run openbb-api --app src/openbb_app/main.py
# or simply
uvx openbb-api --app src/openbb_app/main.py
```

Start the virtual environment and run the following command to start the API:
```shell
uvicorn openbb_app.main:app
```