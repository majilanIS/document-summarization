// Forwards every /api/* request to the FastAPI back-end, so the browser only
// ever talks to this Next.js server. That works however the site is opened
// (localhost, 127.0.0.1 or a network IP) with no CORS or firewall setup.
//
// Uses node:http instead of fetch: fetch gives up after ~5 minutes, and
// summarizing a long document on a CPU can take longer than that.

import http from "node:http";
import https from "node:https";
import { Readable } from "node:stream";

const BACKEND = new URL(process.env.BACKEND_URL ?? "http://127.0.0.1:8000");
const client = BACKEND.protocol === "https:" ? https : http;

// Seconds a request may take when deployed (Vercel): long documents can
// take a while to summarize.
export const maxDuration = 300;

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "host",
]);

function proxy(request) {
  const url = new URL(request.url);

  const headers = {};
  for (const [key, value] of request.headers) {
    if (!HOP_BY_HOP.has(key) && key !== "origin" && key !== "accept-encoding") {
      headers[key] = value;
    }
  }

  return new Promise((resolve) => {
    const upstream = client.request(
      {
        hostname: BACKEND.hostname,
        port: BACKEND.port || (BACKEND.protocol === "https:" ? 443 : 80),
        path: url.pathname + url.search,
        method: request.method,
        headers,
      },
      (response) => {
        const responseHeaders = new Headers();
        for (const [key, value] of Object.entries(response.headers)) {
          if (value === undefined || HOP_BY_HOP.has(key)) continue;
          responseHeaders.set(key, Array.isArray(value) ? value.join(", ") : value);
        }

        const hasBody = ![204, 304].includes(response.statusCode);
        if (!hasBody) response.resume();

        resolve(
          new Response(hasBody ? Readable.toWeb(response) : null, {
            status: response.statusCode,
            headers: responseHeaders,
          })
        );
      }
    );

    upstream.on("error", () => {
      resolve(
        Response.json(
          {
            detail:
              `Can't reach the back-end at ${BACKEND.origin}. ` +
              "Check that it is running and that BACKEND_URL points to it.",
          },
          { status: 502 }
        )
      );
    });

    if (request.body) {
      Readable.fromWeb(request.body).pipe(upstream);
    } else {
      upstream.end();
    }
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
