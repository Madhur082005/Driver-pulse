import { auth } from "./auth";

// Yeh function humare app ka Bouncer hai
export default async function proxy(request: any) {
  return await auth(request);
}

// Kahan-kahan lock lagana hai (Login aur API ko chhod kar sab jagah)
export const config = {
  matcher: ["/((?!login|api|_next/static|_next/image|favicon.ico).*)"],
};