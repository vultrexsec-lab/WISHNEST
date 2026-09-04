---
name: Gmail connector bridge
description: The project’s Gmail notification path uses the Node connector SDK instead of a Python package.
---

The connected Gmail integration is accessed through the Node.js connector SDK bridge; do not reintroduce the unavailable Python connector dependency.

**Why:** The Python package is not available in the package registry, and adding it prevents the backend workflow from resolving dependencies.

**How to apply:** Keep Gmail delivery isolated behind the existing service/bridge boundary and verify the backend dependency resolver before changing connector packages.