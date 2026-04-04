import { useState } from "react";
import { useAuth } from "./AuthContext";
import { LoginView } from "./LoginView";
import { SignUpView } from "./SignUpView";

export function AuthEntry() {
  const { allowSignup } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");

  if (mode === "signup" && allowSignup) {
    return <SignUpView onBack={() => setMode("login")} />;
  }

  return <LoginView onCreateAccount={allowSignup ? () => setMode("signup") : undefined} />;
}
