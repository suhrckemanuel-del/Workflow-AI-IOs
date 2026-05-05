/** @type {import('next').NextConfig} */
const apiProxyUrl = process.env.API_PROXY_URL ?? "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    // Keep frontend in production mode while proxying API calls to the local FastAPI server.
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
