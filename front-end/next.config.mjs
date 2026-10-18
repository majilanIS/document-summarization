/** @type {import('next').NextConfig} */
const nextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  output: "export",
  // Let the dev server work when opened via the machine's network address
  // (e.g. http://10.200.14.100:3000), not just localhost. Without this the
  // page loads but never becomes interactive.
  allowedDevOrigins: [
    "127.0.0.1",
    "10.200.14.100",
    "10.*.*.*",
    "192.168.*.*",
    "172.*.*.*",
  ],
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
