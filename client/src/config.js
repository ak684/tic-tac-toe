// Minimal client-side config used at runtime
// Keep this lightweight and avoid importing package.json in the browser build
export function getConfig() {
  return {
    version: '1.0.0'
  };
}
