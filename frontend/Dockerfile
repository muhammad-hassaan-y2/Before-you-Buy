FROM node:22-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile=false

COPY . .
# next.config.ts resolves the /api rewrite into the build output, so the gateway
# address has to exist at build time, not only at runtime.
ARG API_GATEWAY_URL=http://localhost:8001
ENV API_GATEWAY_URL=${API_GATEWAY_URL}
RUN pnpm build

ENV HOSTNAME=0.0.0.0
ENV PORT=3000
EXPOSE 3000

CMD ["pnpm", "start"]
