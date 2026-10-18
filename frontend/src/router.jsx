/**
 * router.jsx — TanStack Router factory.
 *
 * Returns a new router (and a fresh QueryClient) each time it is called.
 * In practice, `getRouter` is called once in main.jsx; the factory pattern
 * keeps the router testable and prevents shared state across test runs.
 */
import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen.js";

export const getRouter = () => {
  // QueryClient is created here (not globally) so each router instance has its
  // own independent cache. It is injected into the router context so that route
  // loaders can call queryClient.ensureQueryData without importing a singleton.
  const queryClient = new QueryClient();

  const router = createRouter({
    routeTree,
    context: { queryClient },
    // Restore scroll position when navigating back to a previously visited route.
    scrollRestoration: true,
    // Always re-fetch loader data on navigation; 0 means the prefetch cache is
    // never considered stale, so loaders run on every visit.
    defaultPreloadStaleTime: 0,
  });

  return router;
};
