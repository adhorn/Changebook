import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // "react-hooks/set-state-in-effect" (new in the eslint-plugin-react-hooks
      // v7 that ships with the eslint 10 bump) flags the canonical patterns
      // this app uses:
      //   - fetching data in an effect on mount / when filters change
      //   - syncing state from the external user store (initial read plus a
      //     "user-changed" event subscription)
      // React's own guidance endorses both shapes (the rule targets
      // synchronous prop/state mirroring, not async fetch callbacks or
      // external-system subscriptions). Keep it off until the rule
      // distinguishes those; re-audit when a newer react-hooks releases.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
