# Coding Standards

This document outlines the coding standards and preferences for the BlockWords Cubes project.

## Method Arguments

**Do not use default arguments in method definitions.**

Explicitly providing all arguments at the call site reduces errors, improves readability, and avoids hidden state or unexpected behavior from changing defaults.

### Bad
```python
def connect(self, timeout: int = 30, retries: int = 3):
    ...
```

### Good
```python
def connect(self, timeout: int, retries: int):
    ...
```

Callers must explicitly provide these values, or you can use `None` as a default if optional behavior is strictly required, but explicit values are preferred.
