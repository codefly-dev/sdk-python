# codefly SDK

## Access endpoints

## Access provider information

## Authenticate as a fixture principal

A test resolves a seeded identity by role against the manifests of the packages
the workspace composes, instead of hardcoding one:

```python
principal = codefly.fixture().principal("super_admin")
```

A package bump that renames or drops the principal then fails at resolution,
naming the roles the fixture does seed.

## Development

### Run the tests

```shell
poetry run pytest -v -s
```

### Publishing

Setup the token
```shell
poetry config pypi-token.pypi ${TOKEN}
```

Build
```shell
poetry build
```

Publish
```shell
poetry publish
```
