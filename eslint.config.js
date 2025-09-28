import eslintPluginReact from "eslint-plugin-react";
import eslintPluginReactHooks from "eslint-plugin-react-hooks";
import eslintPluginJsxA11y from "eslint-plugin-jsx-a11y";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

export default [
	{
		files: ["builder-ui/**/*.{ts,tsx}"],
		ignores: [
			"**/node_modules/**",
			"src/**",
			"builder-ui/public/**",
			"builder-ui/playwright-report/**",
			"builder-ui/test-results/**",
		],
		languageOptions: {
			parser: tsParser,
			parserOptions: {
				ecmaVersion: "latest",
				sourceType: "module",
				ecmaFeatures: {
					jsx: true,
				},
			},
		},
		plugins: {
			"@typescript-eslint": tsPlugin,
			react: eslintPluginReact,
			"react-hooks": eslintPluginReactHooks,
			"jsx-a11y": eslintPluginJsxA11y,
		},
		settings: {
			react: {
				version: "detect",
			},
		},
		rules: {
			"react/react-in-jsx-scope": "off",
			"react/prop-types": "off",
			"react-hooks/rules-of-hooks": "error",
			"react-hooks/exhaustive-deps": "warn",
			"jsx-a11y/no-autofocus": "off",
			"@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
			"@typescript-eslint/consistent-type-imports": ["error", { prefer: "type-imports" }],
		},
	},
];
