import { NextResponse } from "next/server";
import { getHospitalSession } from "@/lib/session";

export async function POST() {
  const session = await getHospitalSession();
  session.destroy();
  return NextResponse.redirect(new URL("/hospital/signin", "http://localhost:3000"), {
    status: 303,
  });
}
