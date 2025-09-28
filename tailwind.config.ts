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

const config: Config = {
	darkMode: "class",
	content: ["./builder-ui/index.html", "./builder-ui/src/**/*.{ts,tsx}"],
	theme: {
		extend: {
			colors: {
				...radixPalette,
				brand: {
					DEFAULT: blue.blue9,
					foreground: "white",
				},
				background: {
					DEFAULT: mauve.mauve2,
					foreground: mauve.mauve12,
				},
				surface: {
					DEFAULT: mauve.mauve3,
					foreground: mauve.mauve12,
				},
				border: mauve.mauve6,
				muted: mauve.mauve8,
				success: green.green9,
				warning: amber.amber9,
				error: red.red9,
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
				soft: "0 10px 40px -15px rgba(15, 23, 42, 0.25)",
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
