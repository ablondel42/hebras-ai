---
description: Enforces that all import statements are declared exclusively at the top of the file, never inside functions, methods, or classes.
globs: ["**/*.py"]
always_on: true
---

# Top-Level Imports Invariant

1. **Top-Level Declarations Only**:
   - All `import` and `from ... import ...` statements MUST be declared strictly at the top of the Python module (file scope).
   - NEVER place import statements inside function bodies, methods, or class definitions.

2. **Optional Dependencies & Fallbacks**:
   - If an import is optional or might raise an `ImportError`, wrap it in a `try...except ImportError` block at the module top level rather than inside a function.
