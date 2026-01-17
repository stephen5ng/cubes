# Project Rules

1. **Explicit Commit Permission**: Do not commit changes without explicit user permission. "Staging" means `git add`, not `git commit`.
2. **Current State Comments Only**: Comments should explain the current state of the code. Do not use comments to describe historical changes, moved logic, or what the code "used to do" (e.g., "Logic moved to X").
3. **No Default Arguments**: Avoid using default arguments in method and function signatures. Arguments should be passed explicitly to improve maintainability and avoid hidden dependencies.
