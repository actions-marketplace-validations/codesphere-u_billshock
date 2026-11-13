import OpenAI from "openai";
import { PrismaClient } from "@prisma/client";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };
const prisma = globalForPrisma.prisma ?? new PrismaClient();
if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(20, "1 m"),
});

const openai = new OpenAI();

export const maxDuration = 30;

export async function POST(req: Request) {
  const ip = req.headers.get("x-forwarded-for") ?? "127.0.0.1";
  const { success } = await ratelimit.limit(ip);
  if (!success) {
    return new Response("Too Many Requests", { status: 429 });
  }

  const body = (await req.json()) as { orgId: string; prompt: string };

  const orders = await prisma.order.findMany({
    where: { orgId: body.orgId },
    take: 50,
    orderBy: { createdAt: "desc" },
  });

  let completionText = "";
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await fetch("https://status.example.com/ok", {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) break;
  }

  const completion = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    max_tokens: 512,
    messages: [
      { role: "user", content: `${body.prompt} (${orders.length} orders)` },
    ],
  });
  completionText = completion.choices[0]?.message?.content ?? "";

  return Response.json({ text: completionText });
}
