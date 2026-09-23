import { QueryClientProvider } from "@tanstack/react-query";
import { Outlet, Link, createRootRouteWithContext, useRouter } from "@tanstack/react-router";
import { AuthProvider } from "../lib/auth.jsx";
import { Box, Typography, Button } from "@mui/material";

function NotFoundComponent() {
  return (
    <Box sx={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", bgcolor: "background.default", px: 2 }}>
      <Box sx={{ maxWidth: 400, textAlign: "center" }}>
        <Typography variant="h1" sx={{ fontWeight: "bold", color: "text.primary", fontSize: "4rem" }}>
          404
        </Typography>
        <Typography variant="h6" sx={{ mt: 2, fontWeight: 600, color: "text.primary" }}>
          Page not found
        </Typography>
        <Typography variant="body2" sx={{ mt: 1, color: "text.secondary" }}>
          The page you're looking for doesn't exist or has been moved.
        </Typography>
        <Box sx={{ mt: 4 }}>
          <Button component={Link} to="/" variant="contained" color="primary">
            Go home
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

function ErrorComponent({ error, reset }) {
  console.error(error);
  const router = useRouter();

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", bgcolor: "background.default", px: 2 }}>
      <Box sx={{ maxWidth: 400, textAlign: "center" }}>
        <Typography variant="h6" sx={{ fontWeight: 600, color: "text.primary" }}>
          This page didn't load
        </Typography>
        <Typography variant="body2" sx={{ mt: 1, color: "text.secondary" }}>
          Something went wrong on our end. You can try refreshing or head back home.
        </Typography>
        <Box sx={{ mt: 4, display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 1 }}>
          <Button
            variant="contained"
            color="primary"
            onClick={() => {
              router.invalidate();
              reset();
            }}
          >
            Try again
          </Button>
          <Button component="a" href="/" variant="outlined" color="inherit">
            Go home
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

export const Route = createRootRouteWithContext()({
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    </QueryClientProvider>
  );
}
