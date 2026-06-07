// proxy-preload.cjs — Load with --require to proxy all Node.js fetch requests
// Node.js 23: node --require ./proxy-preload.cjs server.mjs

try {
  const { setGlobalDispatcher, ProxyAgent } = require('undici');
  const proxyUrl = process.env.HTTP_PROXY || process.env.http_proxy || 'http://127.0.0.1:7890';
  if (proxyUrl) {
    const agent = new ProxyAgent(proxyUrl);
    setGlobalDispatcher(agent);
    console.error('[proxy] Global fetch proxied via', proxyUrl);
  }
} catch (e) {
  // undici might not be directly importable in all Node.js versions
  // Fallback: try using the built-in undici via internal modules
  try {
    const { setGlobalDispatcher, ProxyAgent } = require('node:internal/deps/undici/undici');
    const proxyUrl = process.env.HTTP_PROXY || process.env.http_proxy || 'http://127.0.0.1:7890';
    if (proxyUrl) {
      const agent = new ProxyAgent(proxyUrl);
      setGlobalDispatcher(agent);
      console.error('[proxy] Global fetch proxied via (internal)', proxyUrl);
    }
  } catch (e2) {
    console.error('[proxy] Failed to set up proxy:', e2.message);
  }
}
