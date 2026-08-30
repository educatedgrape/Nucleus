/** @type {import('next').NextConfig} */
const nextConfig = {
  // The dashboard proxies agent actions to the FastAPI backend so the browser
  // never needs to know about a second origin.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NUCLEUS_API ?? "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
};
export default nextConfig;
