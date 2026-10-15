import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, SignInPage, SsoCallback } from "@/lib/auth";
import { Home, Shell } from "@/components/Shell";
import { CrtOverlay } from "@/components/Crt";
import Landing from "./pages/Landing";
const Onboarding = lazy(() => import("./pages/Onboarding"));
const Practice = lazy(() => import("./pages/Practice"));
const Connect = lazy(() => import("./pages/Connect"));
const Live = lazy(() => import("./pages/Live"));
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <CrtOverlay />
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<div className="grid min-h-[100dvh] place-items-center font-mono text-sm text-muted-foreground cmd-caret">loading</div>}>
          <Routes>
            <Route path="/sign-in/sso-callback" element={<SsoCallback />} />
            <Route path="/sign-up/sso-callback" element={<SsoCallback />} />
            <Route path="/sign-in/*" element={<SignInPage mode="in" />} />
            <Route path="/sign-up/*" element={<SignInPage mode="up" />} />
            <Route element={<Shell />}>
              <Route path="/app" element={<Home />} />
              <Route path="/onboarding" element={<Onboarding />} />
              <Route path="/practice" element={<Practice />} />
              <Route path="/connect" element={<Connect />} />
              <Route path="/live" element={<Live />} />
            </Route>
            <Route path="/" element={<Landing />} />
            <Route path="/index" element={<Navigate to="/" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;