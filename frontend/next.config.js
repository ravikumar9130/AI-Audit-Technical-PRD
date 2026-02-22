/**
 * @type {import('next').NextConfig}
 */
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
  env: {
    NEXT_PUBLIC_API_URL: apiUrl,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  },
};

module.exports = nextConfig;
