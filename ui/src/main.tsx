import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/index.css";

async function enableMocking() {
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

enableMocking().finally(() => {
	const container = document.getElementById("root");

	if (!container) {
		console.error("Failed to find root element");
		throw new Error("Failed to find root element");
	}

	const root = ReactDOM.createRoot(container);
	root.render(
		<React.StrictMode>
			<App />
		</React.StrictMode>,
	);
});
