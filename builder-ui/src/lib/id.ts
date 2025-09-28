export function createId(prefix: string): string {
	if (globalThis.crypto?.randomUUID) {
		return `${prefix}-${globalThis.crypto.randomUUID()}`;
	}
	const random = Math.random().toString(36).slice(2, 10);
	const timestamp = Date.now().toString(36);
	return `${prefix}-${timestamp}-${random}`;
}
