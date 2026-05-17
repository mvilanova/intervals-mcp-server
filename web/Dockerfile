# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS deps
WORKDIR /app
RUN apk add --no-cache libc6-compat openssl
COPY package.json package-lock.json ./
COPY prisma ./prisma
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
RUN apk add --no-cache openssl
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npx prisma generate
RUN npm run build

# Slim runtime image — only the Next.js standalone output + static assets.
# The Prisma client engine is bundled into .next/standalone/node_modules by
# Next.js because it's imported from our app code.
FROM node:22-alpine AS runner
WORKDIR /app
RUN apk add --no-cache openssl
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]

# Separate image for the migrate sidecar. Prisma's CLI loads helper
# assets from node_modules/.bin at runtime, so copy the full installed
# dependency tree instead of a hand-picked subset that can miss internals.
# Built with `--target migrator` in compose.
FROM node:22-alpine AS migrator
WORKDIR /app
RUN apk add --no-cache openssl
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/node_modules ./node_modules
ENV PATH="/app/node_modules/.bin:${PATH}"

CMD ["prisma", "migrate", "deploy"]

# Cron sidecar — runs cron.ts on a 4-hour loop. Reuses the builder stage's
# generated Prisma client + tsx (already in node_modules) so we don't reinstall.
# Built with `--target cron` in compose.
FROM node:22-alpine AS cron
WORKDIR /app
RUN apk add --no-cache openssl
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/tsconfig.json ./tsconfig.json
COPY --from=builder --chown=nextjs:nodejs /app/lib ./lib
COPY --from=builder --chown=nextjs:nodejs /app/cron.ts ./cron.ts
USER nextjs

CMD ["node_modules/.bin/tsx", "cron.ts"]
