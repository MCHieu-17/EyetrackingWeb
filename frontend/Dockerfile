# syntax=docker/dockerfile:1

# ---- 1. Dependencies ----
FROM node:22.14-alpine AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci

# ---- 2. Build (Next.js 16, output: standalone) ----
FROM node:22.14-alpine AS builder
WORKDIR /app
ENV NODE_OPTIONS=--max-old-space-size=2048
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# URL nội bộ cho rewrite phía server (không inlay vào client bundle).
ARG API_INTERNAL_URL=http://backend:8001
ARG GAZE_INTERNAL_URL=http://gaze:8000
# Origin công khai cho browser. Để trống = same-origin qua rewrite.
ARG NEXT_PUBLIC_API_URL=
ARG NEXT_PUBLIC_GAZE_URL=
ENV API_INTERNAL_URL=$API_INTERNAL_URL
ENV GAZE_INTERNAL_URL=$GAZE_INTERNAL_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_GAZE_URL=$NEXT_PUBLIC_GAZE_URL
# Bật standalone CHỈ trong image Docker (Vercel không hỗ trợ standalone).
ENV NEXT_STANDALONE=1

RUN npm run build

# ---- 3. Runner (standalone) ----
FROM node:22.14-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

# server.js + node_modules tối thiểu do Next trace ra.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# static assets + public phải copy thủ công (Next không tự gom).
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

# server.js là entrypoint do Next sinh (output: standalone).
CMD ["node", "server.js"]
