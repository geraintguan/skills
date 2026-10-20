#!/bin/sh
# Builds the throwaway git repo that assets/example-config.json describes.
# Usage: sh make_repo.sh <dir>
set -eu
dir=$1
rm -rf "$dir"; mkdir -p "$dir/src"; cd "$dir"
git init -q -b main
git config user.email demo@example.com; git config user.name Demo

cat > src/legacyRetry.ts <<'EOF'
export function retryThreeTimes<T>(fn: () => Promise<T>): Promise<T> {
  return fn().catch(() => fn()).catch(() => fn());
}
EOF
cat > src/client.ts <<'EOF'
import { retryThreeTimes } from "./legacyRetry";

export async function getJson(url: string): Promise<unknown> {
  return retryThreeTimes(async () => {
    const response = await fetch(url);
    return response.json();
  });
}
EOF
git add -A; git commit -qm "Base"

git rm -q src/legacyRetry.ts
cat > src/retry.ts <<'EOF'
export type RetryOptions = { attempts: number; baseDelayMs: number };

export function backoffDelay(attempt: number, baseDelayMs: number): number {
  return baseDelayMs * 2 ** attempt;
}

export async function withRetry<T>(fn: () => Promise<T>, { attempts, baseDelayMs }: RetryOptions): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) await new Promise((r) => setTimeout(r, backoffDelay(attempt, baseDelayMs)));
    }
  }
  console.warn("withRetry gave up", { attempts, error: lastError });
  throw lastError;
}
EOF
cat > src/retry.test.ts <<'EOF'
import { describe, expect, it } from "vitest";
import { backoffDelay } from "./retry";

describe("backoffDelay", () => {
  it("doubles the delay on each attempt", () => {
    expect([0, 1, 2].map((a) => backoffDelay(a, 100))).toEqual([100, 200, 400]);
  });
});
EOF
cat > src/client.ts <<'EOF'
import { withRetry } from "./retry";

export async function getJson(url: string): Promise<unknown> {
  return withRetry(
    async () => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    },
    { attempts: 3, baseDelayMs: 200 },
  );
}
EOF
mkdir -p fixtures
cat > fixtures/flaky-responses.json <<'EOF'
[{"status": 503}, {"status": 503}, {"status": 200, "body": {"ok": true}}]
EOF
printf '%%PDF-1.4\n\0\1\2\3 binary sample\n' > fixtures/invoice.pdf
git add -A; git commit -qm "Retry with exponential backoff"
