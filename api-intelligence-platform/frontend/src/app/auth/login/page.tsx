"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Lock, Mail, Zap } from "lucide-react";
import { toast } from "sonner";
import { useAuthStore } from "@/store/auth";
import { cn } from "@/lib/utils";

const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();
  const { login, isLoading, error, clearError } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (data: LoginForm) => {
    try {
      clearError();
      await login(data.email, data.password);
      toast.success("Welcome back!", {
        description: "You have successfully logged in.",
      });
      router.push("/");
    } catch {
      // Error is already set in the store
    }
  };

  return (
    <div className="min-h-screen bg-[#080d1a] flex items-center justify-center relative overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 enterprise-grid-bg opacity-40" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-violet-600/10 rounded-full blur-3xl" />

      <div className="relative w-full max-w-md px-6">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 mb-4">
            <Zap className="w-7 h-7 text-indigo-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">API Intelligence</h1>
          <p className="text-slate-400 text-sm mt-1">
            Enterprise API Management Platform
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-slate-900/80 backdrop-blur border border-slate-800 rounded-2xl p-8 shadow-2xl">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-white">Sign in</h2>
            <p className="text-slate-400 text-sm mt-1">
              Enter your credentials to access the platform
            </p>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-400/10 border border-red-400/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  {...register("email")}
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  className={cn(
                    "w-full pl-10 pr-4 py-2.5 bg-slate-800 border rounded-lg text-slate-200 placeholder-slate-500 text-sm",
                    "focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all",
                    errors.email
                      ? "border-red-500/50"
                      : "border-slate-700 hover:border-slate-600"
                  )}
                />
              </div>
              {errors.email && (
                <p className="text-red-400 text-xs mt-1">
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  {...register("password")}
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className={cn(
                    "w-full pl-10 pr-10 py-2.5 bg-slate-800 border rounded-lg text-slate-200 placeholder-slate-500 text-sm",
                    "focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all",
                    errors.password
                      ? "border-red-500/50"
                      : "border-slate-700 hover:border-slate-600"
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-400"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="text-red-400 text-xs mt-1">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Remember me / Forgot password */}
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500/50"
                />
                <span className="text-sm text-slate-400">Remember me</span>
              </label>
              <button
                type="button"
                className="text-sm text-indigo-400 hover:text-indigo-300"
              >
                Forgot password?
              </button>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className={cn(
                "w-full py-2.5 rounded-lg text-sm font-semibold transition-all",
                "bg-indigo-600 hover:bg-indigo-500 text-white",
                "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-900",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                isLoading && "animate-pulse"
              )}
            >
              {isLoading ? "Signing in..." : "Sign in"}
            </button>
          </form>

          {/* Demo credentials */}
          <div className="mt-6 p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
            <p className="text-xs text-slate-500 font-medium mb-1">
              Demo credentials
            </p>
            <p className="text-xs text-slate-400">
              Email: <span className="text-indigo-400">admin@demo.com</span>
            </p>
            <p className="text-xs text-slate-400">
              Password: <span className="text-indigo-400">demo1234</span>
            </p>
          </div>
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
          By signing in, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  );
}
