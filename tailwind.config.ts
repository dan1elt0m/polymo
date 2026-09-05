import type { Config } from "tailwindcss";
import { blue, mauve, slate, gray, red, green, amber } from "@radix-ui/colors";

const radixPalette = {
	...flattenRadixScale("blue", blue),
	...flattenRadixScale("mauve", mauve),
	...flattenRadixScale("slate", slate),
	...flattenRadixScale("gray", gray),
	...flattenRadixScale("red", red),
	...flattenRadixScale("green", green),
	...flattenRadixScale("amber", amber),
};

// Theme-aware tokens. The actual colour values live in
// ui/src/styles/index.css as RGB triplets on :root (light) and
// .dark, so a single utility such as `bg-surface` or `text-fg-muted`
// resolves correctly in both themes without any `.dark … !important`
// override layer. `<alpha-value>` keeps `/50`-style opacity modifiers
// working.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
	darkMode: "class",
	content: ["./ui/index.html", "./ui/src/**/*.{ts,tsx}"],
	theme: {
		extend: {
			colors: {
				...radixPalette,
				brand: {
					DEFAULT: blue.blue9,
					foreground: "white",
				},
				// Surfaces
				background: token("c-bg"),
				surface: token("c-surface"),
				field: token("c-field"),
				raised: token("c-raised"),
				// Lines
				border: {
					DEFAULT: token("c-border"),
					strong: token("c-border-strong"),
				},
				// Text
				fg: {
					DEFAULT: token("c-fg"),
					muted: token("c-fg-muted"),
					subtle: token("c-fg-subtle"),
				},
				muted: token("c-fg-muted"),
				// Accent (primary actions, active states)
				accent: {
					DEFAULT: token("c-accent"),
					hover: token("c-accent-hover"),
					fg: token("c-accent-fg"),
					text: token("c-accent-text"),
					soft: token("c-accent-soft"),
					ring: token("c-accent-ring"),
				},
				// Status (text-grade in both themes)
				success: token("c-success"),
				warning: token("c-warning"),
				error: token("c-error"),
				drac: {
					base: '#282a36',
					surface: '#303241',
					border: '#44475a',
					foreground: '#f8f8f2',
					muted: '#6272a4',
					accent: '#bd93f9',
					accent2: '#ff79c6',
					green: '#50fa7b',
					red: '#ff5555',
					yellow: '#f1fa8c',
					orange: '#ffb86c',
					cyan: '#8be9fd'
				},
			},
			fontFamily: {
				sans: ["Inter", "system-ui", "sans-serif"],
				mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
			},
			boxShadow: {
				soft: "0 10px 40px -15px rgb(var(--c-shadow) / 0.35)",
				card: "0 1px 2px rgb(var(--c-shadow) / 0.06), 0 8px 24px -12px rgb(var(--c-shadow) / 0.25)",
			},
			keyframes: {
				"disclosure-in": {
					from: { opacity: "0", transform: "translateY(-3px)" },
					to: { opacity: "1", transform: "translateY(0)" },
				},
			},
			animation: {
				"disclosure-in": "disclosure-in 160ms ease-out",
			},
		},
	},
	plugins: [],
};

export default config;

function flattenRadixScale(name: string, scale: Record<string, string>) {
	return Object.entries(scale).reduce<Record<string, string>>((acc, [key, value]) => {
		acc[`${name}-${key.replace(/\D/g, "")}`] = value;
		return acc;
	}, {});
}
