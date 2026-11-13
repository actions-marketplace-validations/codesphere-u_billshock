import OpenAI from "openai";
import { PrismaClient } from "@prisma/client";

const openai = new OpenAI();

// BILL013: unbounded module-level cache mutated inside handler
const responseCache: Record<string, string> = {};

// BILL011: long function duration wrapping uncapped paid API calls
export const maxDuration = 120;

// BILL005: public endpoint exposing paid AI SDK with no auth or rate limit
export async function POST(req: Request) {
  const { prompt } = (await req.json()) as { prompt: string };

  // BILL012: constructing a fresh PrismaClient per request
  const prisma = new PrismaClient();
  const count = await prisma.order.count();

  // BILL010: outbound HTTP call without timeout or AbortSignal
  const upstream = await fetch("https://upstream.example.com/context");
  const contextText = await upstream.text();

  // BILL003: uncapped LLM completion missing max_tokens / maxOutputTokens
  const completion = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "user", content: `${prompt}\n${count}\n${contextText}` }],
  });

  const answer = completion.choices[0]?.message?.content ?? "";
  responseCache[prompt] = answer;
  return Response.json({ answer });
}
