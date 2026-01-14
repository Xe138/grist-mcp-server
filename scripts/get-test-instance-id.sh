#!/usr/bin/env bash
# scripts/get-test-instance-id.sh
# Generate a unique instance ID from git branch for parallel test isolation

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
# Sanitize: replace non-alphanumeric with dash, limit length
echo "$BRANCH" | sed 's/[^a-zA-Z0-9]/-/g' | cut -c1-20
