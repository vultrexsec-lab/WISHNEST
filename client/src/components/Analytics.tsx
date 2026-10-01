import { useEffect } from "react";
import { useLocation } from "wouter";
import { initTracking, trackPageView } from "@/lib/tracking";

/** Loads pixels once; fires page_view on every client route change. */
export function Analytics() {
  const [location] = useLocation();

  useEffect(() => {
    initTracking();
  }, []);

  useEffect(() => {
    trackPageView(location || "/");
  }, [location]);

  return null;
}
