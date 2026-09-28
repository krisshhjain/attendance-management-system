import { QueryClientProvider } from "@tanstack/react-query";
import { Outlet, Link, createRootRouteWithContext, useRouter } from "@tanstack/react-router";
import { AuthProvider } from "../lib/auth.jsx";
import { OrganizationScopeProvider } from "../lib/organizationScope.jsx";
import { Box, Typography, Button, CssBaseline, ThemeProvider, createTheme, useMediaQuery } from "@mui/material";
import { useState, useEffect } from "react";

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

function ThemeProviderWrapper({ children }) {
  const prefersDarkMode = useMediaQuery("(prefers-color-scheme: dark)");
  const [themeMode, setThemeMode] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("themeMode") || (prefersDarkMode ? "dark" : "light");
    }
    return "light";
  });

  useEffect(() => {
    const stored = localStorage.getItem("themeMode");
    if (stored) {
      setThemeMode(stored);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("themeMode", themeMode);
    document.documentElement.setAttribute("data-theme", themeMode);
  }, [themeMode]);

  const theme = createTheme({
    palette: {
      mode: themeMode,
      primary: {
        main: "#4f46e5", // indigo-600
        light: "#818cf8", // indigo-400
        dark: "#4338ca", // indigo-700
        contrastText: "#ffffff",
        ...(themeMode === "light" && {
          "50": "#eef2ff", // indigo-50 for light theme
          "100": "#e0e7ff", // indigo-100 for light theme
        }),
        ...(themeMode === "dark" && {
          "50": "rgba(99, 102, 241, 0.1)", // indigo with opacity for dark theme
          "100": "rgba(99, 102, 241, 0.2)", // indigo with opacity for dark theme
        }),
      },
      success: {
        main: "#10b981", // emerald-500
        light: "#34d399", // emerald-400
        dark: "#059669", // emerald-600
        contrastText: "#ffffff",
      },
      warning: {
        main: "#f59e0b", // amber-500
        light: "#fbbf24", // amber-400
        dark: "#d97706", // amber-600
        contrastText: "#ffffff",
      },
      error: {
        main: "#ef4444", // red-500
        light: "#f87171", // red-400
        dark: "#dc2626", // red-600
        contrastText: "#ffffff",
      },
      info: {
        main: "#3b82f6", // blue-500
        light: "#60a5fa", // blue-400
        dark: "#2563eb", // blue-600
        contrastText: "#ffffff",
      },
      secondary: {
        main: "#64748b", // slate-500
        light: "#94a3b8", // slate-400
        dark: "#475569", // slate-600
        contrastText: "#ffffff",
      },
      background: {
        default: themeMode === "dark" ? "#0f172a" : "#f8fafc", // slate-950 : slate-50
        paper: themeMode === "dark" ? "#1e293b" : "#ffffff", // slate-800 : white
      },
      text: {
        primary: themeMode === "dark" ? "#f1f5f9" : "#0f172a", // slate-100 : slate-900
        secondary: themeMode === "dark" ? "#94a3b8" : "#64748b", // slate-400 : slate-500
        disabled: themeMode === "dark" ? "#64748b" : "#cbd5e1", // slate-500 : slate-300
      },
      divider: themeMode === "dark" ? "#334155" : "#e2e8f0", // slate-700 : slate-200
      action: {
        hover: themeMode === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.04)",
        hoverOpacity: 0.08,
        selected: themeMode === "dark" ? "rgba(255,255,255,0.16)" : "rgba(0,0,0,0.08)",
        selectedOpacity: 0.16,
        disabled: themeMode === "dark" ? "rgba(255,255,255,0.3)" : "rgba(0,0,0,0.38)",
        disabledBackground: themeMode === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)",
        disabledOpacity: 0.38,
        focus: themeMode === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)",
      },
    },
    shape: {
      borderRadius: 8,
    },
    typography: {
      fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica", "Arial", sans-serif',
      fontSize: 14,
      fontWeightLight: 300,
      fontWeightRegular: 400,
      fontWeightMedium: 500,
      fontWeightBold: 700,
      h1: { fontWeight: 700, fontSize: "2.5rem" },
      h2: { fontWeight: 700, fontSize: "2rem" },
      h3: { fontWeight: 700, fontSize: "1.75rem" },
      h4: { fontWeight: 700, fontSize: "1.5rem" },
      h5: { fontWeight: 700, fontSize: "1.25rem" },
      h6: { fontWeight: 700, fontSize: "1rem" },
      subtitle1: { fontWeight: 600, fontSize: "1rem" },
      subtitle2: { fontWeight: 600, fontSize: "0.875rem" },
      body1: { fontWeight: 400, fontSize: "0.875rem" },
      body2: { fontWeight: 400, fontSize: "0.8125rem" },
      button: { fontWeight: 600, fontSize: "0.875rem", textTransform: "none" },
      caption: { fontWeight: 400, fontSize: "0.75rem" },
      overline: { fontWeight: 600, fontSize: "0.625rem", textTransform: "uppercase", letterSpacing: "0.08em" },
    },
    shadows: [
      "none",
      "0 1px 2px 0 rgb(0 0 0 / 0.05)",
      "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
      "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)",
      "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)",
      "0 25px 50px -12px rgb(0 0 0 / 0.25)",
      ...Array(18).fill("0 25px 50px -12px rgb(0 0 0 / 0.25)"),
    ],
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            scrollbarColor: themeMode === "dark" ? "#475569 #1e293b" : "#cbd5e1 #f8fafc",
            "&::-webkit-scrollbar": {
              width: "8px",
              height: "8px",
            },
            "&::-webkit-scrollbar-track": {
              background: themeMode === "dark" ? "#1e293b" : "#f8fafc",
            },
            "&::-webkit-scrollbar-thumb": {
              backgroundColor: themeMode === "dark" ? "#475569" : "#cbd5e1",
              borderRadius: "4px",
              "&:hover": {
                backgroundColor: themeMode === "dark" ? "#64748b" : "#94a3b8",
              },
            },
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: "none",
            fontWeight: 600,
            borderRadius: 8,
            boxShadow: "none",
            "&:hover": {
              boxShadow: "none",
            },
          },
          contained: {
            boxShadow: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
            "&:hover": {
              boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.1)",
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            backgroundImage: "none",
          },
          elevation1: {
            boxShadow: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
          },
          elevation2: {
            boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
          },
          elevation3: {
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            "& .MuiOutlinedInput-root": {
              borderRadius: 8,
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            fontWeight: 600,
            borderRadius: 6,
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            borderRadius: 0,
            backgroundImage: "none",
          },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            borderRadius: 12,
            backgroundImage: "none",
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
          },
        },
      },
    },
  });

  const handleThemeModeChange = (event) => {
    if (event.detail) {
      setThemeMode(event.detail);
    }
  };

  useEffect(() => {
    window.addEventListener("themeModeChanged", handleThemeModeChange);
    return () => window.removeEventListener("themeModeChanged", handleThemeModeChange);
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
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
        <OrganizationScopeProvider>
          <ThemeProviderWrapper>
            <Outlet />
          </ThemeProviderWrapper>
        </OrganizationScopeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
