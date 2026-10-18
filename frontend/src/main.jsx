/**
 * main.jsx — Application entry point.
 *
 * Bootstrap order:
 *   1. A single router instance is created (includes a QueryClient in its context).
 *   2. The global MUI theme is built here; component-level style overrides live
 *      in the `components` block so they stay co-located with palette/typography.
 *   3. The provider tree is: ThemeProvider → CssBaseline → FeedbackProvider →
 *      RouterProvider. FeedbackProvider must wrap RouterProvider so that toast/
 *      snackbar feedback is available to any route component.
 */
import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { getRouter } from "./router.jsx";
import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { FeedbackProvider } from "./feedback/FeedbackProvider.jsx";

// A single router instance is created here and passed directly to RouterProvider.
// getRouter() also constructs a QueryClient that is injected into the TanStack
// Router context so route loaders can share the same cache.
const router = getRouter();

/**
 * Global MUI theme for the application.
 *
 * All palette values are Tailwind Slate / Indigo tokens hardcoded as hex so the
 * design remains deterministic regardless of Tailwind configuration. The palette
 * here is for the main application shell; note that __root.jsx also creates a
 * theme for internal provider wrapping — the two are intentionally independent.
 */
const theme = createTheme({
  palette: {
    // Primary: Indigo-600 / Indigo-400 / Indigo-800 — brand colour used for
    // interactive elements, active nav indicators, and focused input borders.
    primary: { main: "#4f46e5", light: "#818cf8", dark: "#3730a3", contrastText: "#ffffff" },
    secondary: { main: "#64748b", contrastText: "#ffffff" },
    success: { main: "#059669", light: "#d1fae5", contrastText: "#ffffff" },
    warning: { main: "#d97706", light: "#fef3c7", contrastText: "#ffffff" },
    error: { main: "#dc2626", light: "#fee2e2", contrastText: "#ffffff" },
    info: { main: "#0284c7", light: "#e0f2fe", contrastText: "#ffffff" },
    // Slate-50 page background keeps content areas visually distinct from
    // white paper surfaces (cards, dialogs, sidebars).
    background: { default: "#f8fafc", paper: "#ffffff" },
    text: { primary: "#0f172a", secondary: "#64748b", disabled: "#94a3b8" },
    divider: "#e2e8f0",
    action: { hover: "#f1f5f9", selected: "#eef2ff" },
  },
  typography: {
    fontFamily: "'Inter', 'Roboto', 'Helvetica', 'Arial', sans-serif",
    h1: { fontWeight: 700, letterSpacing: "-0.025em" },
    h2: { fontWeight: 700, letterSpacing: "-0.025em" },
    h3: { fontWeight: 700, letterSpacing: "-0.02em" },
    h4: { fontWeight: 700, letterSpacing: "-0.015em" },
    h5: { fontWeight: 600, letterSpacing: "-0.01em" },
    h6: { fontWeight: 600, letterSpacing: "-0.01em" },
    subtitle1: { fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    body1: { lineHeight: 1.6 },
    body2: { lineHeight: 1.6 },
    button: { fontWeight: 600, textTransform: "none", letterSpacing: 0 },
    caption: { color: "#64748b" },
  },
  shape: { borderRadius: 12 },
  // Custom shadow scale using low-opacity Slate-950 to match the light palette.
  // MUI requires exactly 25 shadow entries (elevation 0–24); entries 6–24 are
  // collapsed to "none" because the app does not use those elevation levels.
  shadows: [
    "none",
    "0 1px 3px rgba(15,23,42,0.04), 0 1px 2px rgba(15,23,42,0.06)",
    "0 4px 6px rgba(15,23,42,0.04), 0 2px 4px rgba(15,23,42,0.06)",
    "0 10px 15px rgba(15,23,42,0.04), 0 4px 6px rgba(15,23,42,0.05)",
    "0 20px 25px rgba(15,23,42,0.04), 0 8px 10px rgba(15,23,42,0.04)",
    "0 25px 50px rgba(15,23,42,0.08)",
    ...Array(19).fill("none"),
  ],
  // Component-level overrides: normalise default MUI styling to match the
  // application design system. Each override applies globally — individual
  // components do not need per-instance sx props for these baseline styles.
  components: {
    // Buttons: flat (no box-shadow) by default; elevation only via border/fill.
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          fontWeight: 600,
          fontSize: "0.8125rem",
          padding: "8px 16px",
          boxShadow: "none",
          "&:hover": { boxShadow: "none" },
        },
        containedPrimary: { background: "#4f46e5", "&:hover": { background: "#4338ca" } },
        outlinedPrimary: {
          borderColor: "#c7d2fe",
          "&:hover": { borderColor: "#a5b4fc", background: "#eef2ff" },
        },
        outlinedSecondary: {
          borderColor: "#e2e8f0",
          color: "#475569",
          "&:hover": { borderColor: "#cbd5e1", background: "#f8fafc" },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 8, fontWeight: 600, fontSize: "0.75rem" },
        colorSuccess: { background: "#d1fae5", color: "#065f46" },
        colorWarning: { background: "#fef3c7", color: "#92400e" },
        colorError: { background: "#fee2e2", color: "#991b1b" },
        colorInfo: { background: "#e0f2fe", color: "#075985" },
        colorDefault: { background: "#f1f5f9", color: "#475569" },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 16,
          border: "1px solid #e2e8f0",
          boxShadow: "0 1px 3px rgba(15,23,42,0.04)",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { borderRadius: 16, backgroundImage: "none" },
        elevation1: { boxShadow: "0 1px 3px rgba(15,23,42,0.04), 0 1px 2px rgba(15,23,42,0.06)" },
        elevation2: { boxShadow: "0 4px 6px rgba(15,23,42,0.04), 0 2px 4px rgba(15,23,42,0.06)" },
      },
    },
    // Table headers: all-caps label style (11 px, slate-400) to distinguish
    // column headers from data rows without relying on background colour alone.
    MuiTableHead: {
      styleOverrides: {
        root: {
          "& .MuiTableCell-head": {
            background: "#f8fafc",
            fontWeight: 700,
            fontSize: "0.6875rem",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            color: "#94a3b8",
            borderBottom: "1px solid #e2e8f0",
            padding: "12px 16px",
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: "1px solid #f1f5f9",
          fontSize: "0.8125rem",
          padding: "12px 16px",
          color: "#1e293b",
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: "background 0.1s",
          "&:hover": { background: "#f8fafc" },
          "&:last-child td": { borderBottom: "none" },
        },
      },
    },
    MuiTextField: {
      defaultProps: { size: "small" },
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: 10,
            background: "#fff",
            "& fieldset": { borderColor: "#e2e8f0" },
            "&:hover fieldset": { borderColor: "#c7d2fe" },
            "&.Mui-focused fieldset": { borderColor: "#4f46e5", borderWidth: 1.5 },
          },
        },
      },
    },
    MuiSelect: { defaultProps: { size: "small" }, styleOverrides: { root: { borderRadius: 10 } } },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          "& fieldset": { borderColor: "#e2e8f0" },
          "&:hover fieldset": { borderColor: "#c7d2fe" },
          "&.Mui-focused fieldset": { borderColor: "#4f46e5", borderWidth: 1.5 },
        },
      },
    },
    MuiDialog: { styleOverrides: { paper: { borderRadius: 16, border: "1px solid #e2e8f0" } } },
    MuiDialogTitle: {
      styleOverrides: {
        root: { fontSize: "1rem", fontWeight: 700, padding: "20px 24px 12px", color: "#0f172a" },
      },
    },
    MuiDialogContent: { styleOverrides: { root: { padding: "8px 24px 16px" } } },
    MuiDialogActions: { styleOverrides: { root: { padding: "12px 24px 20px", gap: 8 } } },
    MuiTab: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          fontSize: "0.8125rem",
          textTransform: "none",
          minHeight: 44,
          padding: "0 4px",
          color: "#64748b",
          "&.Mui-selected": { color: "#4f46e5" },
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: { borderBottom: "1px solid #e2e8f0", minHeight: 44 },
        indicator: { height: 2, borderRadius: 2, background: "#4f46e5" },
      },
    },
    MuiAlert: { styleOverrides: { root: { borderRadius: 10, fontSize: "0.8125rem" } } },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          borderRadius: 8,
          fontSize: "0.75rem",
          background: "#1e293b",
          padding: "6px 10px",
        },
      },
    },
    MuiIconButton: {
      styleOverrides: { root: { borderRadius: 10, "&:hover": { background: "#f1f5f9" } } },
    },
    MuiListItemButton: { styleOverrides: { root: { borderRadius: 10 } } },
    MuiInputLabel: {
      styleOverrides: { root: { fontSize: "0.8125rem", fontWeight: 500, color: "#64748b" } },
    },
    MuiFormHelperText: { styleOverrides: { root: { fontSize: "0.75rem" } } },
    MuiLinearProgress: {
      styleOverrides: {
        root: { borderRadius: 99, height: 6, background: "#e2e8f0" },
        bar: { borderRadius: 99 },
      },
    },
    MuiAvatar: { styleOverrides: { root: { fontWeight: 700 } } },
    MuiDivider: { styleOverrides: { root: { borderColor: "#e2e8f0" } } },
    MuiSwitch: {
      styleOverrides: {
        root: { padding: 6 },
        track: { borderRadius: 99, opacity: 1, background: "#cbd5e1" },
        thumb: { boxShadow: "none" },
        switchBase: { "&.Mui-checked + .MuiSwitch-track": { background: "#4f46e5", opacity: 1 } },
      },
    },
  },
});

// Mount the React application into the #root element provided by index.html.
// StrictMode is intentionally kept in production to surface potential issues
// during the review cycle; it adds no runtime overhead in production builds.
ReactDOM.createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      {/* CssBaseline normalises browser default styles before any route renders. */}
      <CssBaseline />
      <FeedbackProvider>
        <RouterProvider router={router} />
      </FeedbackProvider>
    </ThemeProvider>
  </StrictMode>,
);
