# Contribution Guide

In this guide you will get an overview of the contribution workflow from opening an issue, creating a PR, reviewing, and merging the PR.

## Commit your update

This app uses [pre-commit](https://github.com/pre-commit/pre-commit) to run a series of checks on your code before you commit it. This helps to ensure that your code is clean and consistent with the rest of the codebase.

To setup pre-commit locally, run the following commands:

```bash
> pip install pre-commit # (or pip3 install pre-commit)
> cd shipstation_integration
> pre-commit install
```

This will setup Git hooks locally in the app to run the pre-commit checks on your code before you commit it.
