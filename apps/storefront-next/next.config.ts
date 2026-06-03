import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.remaxrd.com",
        pathname: "/media/**",
      },
    ],
  },
};

export default nextConfig;
