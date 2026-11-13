import { PrismaClient } from "@prisma/client";
import { Resend } from "resend";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };
const prisma = globalForPrisma.prisma ?? new PrismaClient();
const resend = new Resend(process.env.RESEND_API_KEY);

export async function POST(req: Request) {
  const { ids, users } = (await req.json()) as {
    ids: string[];
    users: Array<{ id: string; email: string }>;
  };

  // BILL007: unbounded findMany without take / limit
  const orders = await prisma.order.findMany({
    orderBy: { createdAt: "desc" },
  });

  // BILL008: uncapped Promise.all fan-out over fetch
  const profiles = await Promise.all(
    ids.map((id) => fetch(`https://api.example.com/users/${id}`, { signal: AbortSignal.timeout(2000) }))
  );

  // BILL004: paid email API call inside unbounded loop
  for (const user of users) {
    await resend.emails.send({
      from: "alerts@example.com",
      to: user.email,
      subject: "Report ready",
      html: "<p>Done</p>",
    });
  }

  // BILL006: N+1 Prisma query inside loop
  const enriched = [];
  for (const item of orders) {
    const owner = await prisma.user.findUnique({ where: { id: item.userId } });
    enriched.push(owner);
  }

  // BILL009: infinite loop making outbound network calls
  while (true) {
    await fetch("https://poll.example.com/status", {
      signal: AbortSignal.timeout(1000),
    });
  }

  return Response.json({ count: enriched.length, profiles: profiles.length });
}
