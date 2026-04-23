import { NextResponse } from "next/server";
import { getBuyerSession } from "@/lib/session";

export async function POST() {
  const session = await getBuyerSession();
  session.destroy();
  return NextResponse.redirect(new URL("/", "http://localhost:3000"), { status: 303 });
}
