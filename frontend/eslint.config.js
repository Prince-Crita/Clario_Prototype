import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules", "src/lib/api/schema.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.strict, ...tseslint.configs.stylistic],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // Architecture rule (plan §9.2): features talk to the backend only through lib/api.
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Use the API client in src/lib/api." },
      ],
    },
  },
  {
    // Tests stub and inspect fetch; the ban protects product code only.
    files: ["**/*.test.{ts,tsx}", "src/test/**"],
    rules: { "no-restricted-globals": "off" },
  },
);
