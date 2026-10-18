import type { NextRequest } from "next/server";

// Backend-for-frontend proxy: the browser only talks to Next.js, and this route
// forwards to FastAPI with credentials that never leave the server.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const ALLOWED_PATH = /^sessions(\/[A-Za-z0-9_-]{1,64}(\/messages)?)?$/;

async function forward(request: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const { path } = await ctx.params;
  const target = path.join("/");
  if (!ALLOWED_PATH.test(target)) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }

  const headers = new Headers({ "Content-Type": "application/json" });
  const authorization = request.headers.get("authorization");
  if (authorization) headers.set("Authorization", authorization);
  if (process.env.DATA_AGENT_API_KEY) headers.set("X-API-Key", process.env.DATA_AGENT_API_KEY);
  if (process.env.DATA_AGENT_USER_ID) headers.set("X-User-ID", process.env.DATA_AGENT_USER_ID);

  const hasBody = request.method === "POST";
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/${target}`, {
      method: request.method,
      headers,
      body: hasBody ? await request.text() : undefined,
      cache: "no-store",
    });
    return new Response(response.status === 204 ? null : await response.text(), {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return Response.json(
      { detail: "The Data Agent API is unreachable. Is the backend running?" },
      { status: 502 },
    );
  }
}

export { forward as GET, forward as POST, forward as DELETE };
