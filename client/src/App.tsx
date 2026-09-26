import { Switch, Route, useLocation, Redirect } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/not-found";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { PremiumEditorial } from "@/pages/PremiumEditorial";
import { ArticlePage } from "@/pages/ArticlePage";
import { ArticleDetailPage } from "@/pages/ArticleDetailPage";
import { DestinationsPage } from "@/pages/DestinationsPage";
import { BestOfPage } from "@/pages/BestOfPage";
import { IntelligencePage } from "@/pages/IntelligencePage";
import { ReviewDashboard } from "@/pages/ReviewDashboard";
import { ReviewsPage } from "@/pages/ReviewsPage";
import { ContributorsPage } from "@/pages/ContributorsPage";
import { ReimaginedPage } from "@/pages/ReimaginedPage";
import { LoginPage } from "@/pages/LoginPage";
import { ReimagingPage } from "@/pages/ReimagingPage";

/** Redirects to /login when not authenticated. */
function ProtectedDashboard() {
  const { isAdmin } = useAuth();
  if (!isAdmin) return <Redirect to="/login" />;
  return <ReviewDashboard />;
}

function Router() {
  return (
    <Switch>
      <Route path="/" component={PremiumEditorial} />
      <Route path="/article/seclude-ramgarh-willows" component={ArticlePage} />
      <Route path="/article/:id" component={ArticleDetailPage} />
      <Route path="/reviews" component={ReviewsPage} />
      <Route path="/destinations" component={DestinationsPage} />
      <Route path="/best-of" component={BestOfPage} />
      <Route path="/intelligence" component={IntelligencePage} />
      <Route path="/contributors" component={ContributorsPage} />
      <Route path="/reimagined" component={ReimaginedPage} />
      <Route path="/login" component={LoginPage} />
      <Route path="/dashboard" component={ProtectedDashboard} />
      <Route path="/reimaging" component={ReimagingPage} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
