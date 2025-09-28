import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/index.css";

console.log("Main.tsx loading...");

async function enableMocking() {
	// Temporarily disable MSW for debugging
	console.log("MSW disabled for debugging");
	return;

	if (!import.meta.env.DEV) {
		return;
	}
	try {
		const { worker } = await import("./mocks/browser");
		await worker.start({ onUnhandledRequest: "bypass" });
	} catch (error) {
		console.warn(
			"MSW worker failed to start. Run `npm run msw` to install the service worker.",
			error,
		);
	}
}

console.log("About to call enableMocking...");
enableMocking().finally(() => {
	console.log("enableMocking completed, attempting to mount React app...");

	const container = document.getElementById("root");
	console.log("Root container found:", container);

	if (!container) {
		console.error("Failed to find root element");
		throw new Error("Failed to find root element");
	}

	try {
		console.log("Creating React root...");
		const root = ReactDOM.createRoot(container);

		console.log("Rendering App component...");
		root.render(
			<React.StrictMode>
				<App />
			</React.StrictMode>,
		);
		console.log("React app rendered successfully!");
	} catch (error) {
		console.error("Error rendering React app:", error);
	}
});
