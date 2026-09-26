import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../lib/api.js";
import { RequireAuth } from "../components/RequireAuth.jsx";
import {
  Box,
  Typography,
  Avatar,
  Skeleton,
  Alert,
} from "@mui/material";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import BeachAccessOutlinedIcon from "@mui/icons-material/BeachAccessOutlined";
import HourglassEmptyOutlinedIcon from "@mui/icons-material/HourglassEmptyOutlined";

// ── Route ─────────────────────────────────────────────────────────────────────

export const Route = createFileRoute("/my-team")({
  head: () => ({
    meta: [
      { title: "My Team — AttendPro" },
      { name: "description", content: "See today's attendance status for your team." },
    ],
  }),
  component: () => (
    <RequireAuth>
      <MyTeamPage />
    </RequireAuth>
  ),
});

// ── Column config ─────────────────────────────────────────────────────────────

const COLUMNS = [
  {
    key: "CHECKED_IN",
    label: "Checked In",
    countKey: "checked_in_count",
    color: "#166534",
    avatarBg: "#16a34a",
    columnBg: "#f0fdf4",
    headerBg: "#dcfce7",
    borderColor: "#bbf7d0",
    countBadgeBg: "#16a34a",
    icon: <CheckCircleOutlineIcon sx={{ fontSize: 14 }} />,
  },
  {
    key: "YET_TO_CHECK_IN",
    label: "Yet to Check In",
    countKey: "yet_to_check_in_count",
    color: "#9a3412",
    avatarBg: "#ea580c",
    columnBg: "#fff7ed",
    headerBg: "#ffedd5",
    borderColor: "#fed7aa",
    countBadgeBg: "#ea580c",
    icon: <HourglassEmptyOutlinedIcon sx={{ fontSize: 14 }} />,
  },
  {
    key: "ON_LEAVE",
    label: "On Leave",
    countKey: "on_leave_count",
    color: "#075985",
    avatarBg: "#0284c7",
    columnBg: "#f0f9ff",
    headerBg: "#e0f2fe",
    borderColor: "#bae6fd",
    countBadgeBg: "#0284c7",
    icon: <BeachAccessOutlinedIcon sx={{ fontSize: 14 }} />,
  },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(" ");
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : parts[0].slice(0, 2).toUpperCase();
}

// ── Member card ───────────────────────────────────────────────────────────────

function MemberCard({ member, col }) {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        px: 1.5,
        py: 1.25,
        borderRadius: "10px",
        bgcolor: "#fff",
        border: "1px solid #e5e7eb",
        boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
        transition: "box-shadow 0.15s, transform 0.15s",
        "&:hover": {
          boxShadow: "0 3px 8px rgba(0,0,0,0.08)",
          transform: "translateY(-1px)",
        },
      }}
    >
      <Avatar
        sx={{
          width: 36,
          height: 36,
          bgcolor: col.avatarBg,
          fontSize: "0.75rem",
          fontWeight: 700,
          flexShrink: 0,
          boxShadow: `0 0 0 2px ${col.headerBg}`,
        }}
      >
        {initials(member.name)}
      </Avatar>

      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          fontWeight={600}
          noWrap
          sx={{ fontSize: "0.83rem", color: "#111827", lineHeight: 1.3 }}
        >
          {member.name}
        </Typography>

        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mt: 0.25, flexWrap: "wrap" }}>
          {member.subsection && (
            <Typography
              variant="caption"
              sx={{ fontSize: "0.7rem", color: "#6b7280", fontWeight: 500 }}
            >
              {member.subsection}
            </Typography>
          )}

          {member.status === "CHECKED_IN" && member.check_in_time && (
            <>
              {member.subsection && (
                <Box sx={{ width: "3px", height: "3px", borderRadius: "50%", bgcolor: "#d1d5db" }} />
              )}
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.3 }}>
                <AccessTimeIcon sx={{ fontSize: 10, color: "#9ca3af" }} />
                <Typography variant="caption" sx={{ fontSize: "0.7rem", color: "#9ca3af" }}>
                  {formatTime(member.check_in_time)}
                </Typography>
              </Box>
            </>
          )}

          {member.status === "ON_LEAVE" && member.leave_type && (
            <>
              {member.subsection && (
                <Box sx={{ width: "3px", height: "3px", borderRadius: "50%", bgcolor: "#d1d5db" }} />
              )}
              <Typography
                variant="caption"
                sx={{ fontSize: "0.7rem", color: col.color, fontWeight: 600 }}
              >
                {member.leave_type}
              </Typography>
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
}

// ── Column ────────────────────────────────────────────────────────────────────

function Column({ col, members, isLoading }) {
  return (
    <Box
      sx={{
        flex: 1,
        minWidth: 0,
        display: "flex",
        flexDirection: "column",
        borderRadius: "14px",
        border: `1.5px solid ${col.borderColor}`,
        bgcolor: col.columnBg,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 2,
          py: 1.5,
          bgcolor: col.headerBg,
          borderBottom: `1.5px solid ${col.borderColor}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Box sx={{ color: col.color, display: "flex", alignItems: "center" }}>{col.icon}</Box>
          <Typography
            variant="subtitle2"
            fontWeight={700}
            sx={{ color: col.color, fontSize: "0.8rem", letterSpacing: "-0.01em" }}
          >
            {col.label}
          </Typography>
        </Box>

        {isLoading ? (
          <Skeleton variant="rounded" width={22} height={20} sx={{ borderRadius: "6px" }} />
        ) : (
          <Box
            sx={{
              minWidth: 22,
              height: 22,
              px: 0.75,
              borderRadius: "6px",
              bgcolor: col.countBadgeBg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Typography sx={{ fontSize: "0.7rem", fontWeight: 700, color: "#fff" }}>
              {members.length}
            </Typography>
          </Box>
        )}
      </Box>

      {/* Cards */}
      <Box
        sx={{
          flex: 1,
          p: 1.25,
          display: "flex",
          flexDirection: "column",
          gap: 0.75,
          overflowY: "auto",
          minHeight: 160,
        }}
      >
        {isLoading &&
          [...Array(4)].map((_, i) => (
            <Skeleton key={i} variant="rounded" height={54} sx={{ borderRadius: "10px", bgcolor: "rgba(0,0,0,0.06)" }} />
          ))}

        {!isLoading && members.length === 0 && (
          <Box sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", py: 5 }}>
            <Typography variant="caption" sx={{ color: "#9ca3af", fontStyle: "italic", fontSize: "0.75rem" }}>
              No members
            </Typography>
          </Box>
        )}

        {!isLoading && members.map((m) => (
          <MemberCard key={m.id} member={m} col={col} />
        ))}
      </Box>
    </Box>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function MyTeamPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["my-team"],
    queryFn: () => apiRequest("/attendance/my-team/"),
    refetchInterval: 60_000,
    retry: 1,
  });

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const grouped = {
    CHECKED_IN: data?.members?.filter((m) => m.status === "CHECKED_IN") ?? [],
    YET_TO_CHECK_IN: data?.members?.filter((m) => m.status === "YET_TO_CHECK_IN") ?? [],
    ON_LEAVE: data?.members?.filter((m) => m.status === "ON_LEAVE") ?? [],
  };

  return (
    <Box>
      {/* Override EmployeeLayout's inner container to be truly full-width */}
      <Box
        sx={{
          // Pull out of any max-width container the layout imposes
          mx: { xs: -2, sm: -3, md: -4 },
          px: { xs: 2, sm: 3, md: 4 },
          pb: 4,
          minHeight: "100%",
          bgcolor: "#f8fafc",
        }}
      >
        {/* Page header */}
        <Box
          sx={{
            pt: 3,
            pb: 2.5,
            display: "flex",
            alignItems: { xs: "flex-start", sm: "center" },
            justifyContent: "space-between",
            flexDirection: { xs: "column", sm: "row" },
            gap: 1.5,
            borderBottom: "1px solid #e5e7eb",
            mb: 2.5,
          }}
        >
          <Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.25 }}>
              <GroupsOutlinedIcon sx={{ color: "#6366f1", fontSize: 22 }} />
              <Typography
                variant="h6"
                fontWeight={700}
                sx={{ color: "#111827", fontSize: "1.1rem", letterSpacing: "-0.02em" }}
              >
                My Team
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: "#6b7280", fontSize: "0.78rem" }}>
              {today}
              {data && (
                <> &mdash; {data.team_employment_type} · Section {data.team_section}</>
              )}
            </Typography>
          </Box>

          {/* Summary pills */}
          {!isLoading && data && (
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              {COLUMNS.map((col) => (
                <Box
                  key={col.key}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 0.6,
                    px: 1.25,
                    py: 0.6,
                    borderRadius: "99px",
                    bgcolor: col.headerBg,
                    border: `1px solid ${col.borderColor}`,
                  }}
                >
                  <Box sx={{ color: col.color, display: "flex" }}>{col.icon}</Box>
                  <Typography sx={{ fontSize: "0.75rem", fontWeight: 700, color: col.color }}>
                    {data[col.countKey] ?? 0}
                  </Typography>
                  <Typography sx={{ fontSize: "0.73rem", color: "#6b7280" }}>
                    {col.label}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}

          {isLoading && (
            <Box sx={{ display: "flex", gap: 1 }}>
              {[90, 110, 80].map((w, i) => (
                <Skeleton key={i} variant="rounded" width={w} height={30} sx={{ borderRadius: "99px" }} />
              ))}
            </Box>
          )}
        </Box>

        {/* Errors / notices */}
        {isError && (
          <Alert severity="error" sx={{ mb: 2, borderRadius: "10px" }}>
            {error?.message ?? "Failed to load team data. Please try again."}
          </Alert>
        )}
        {!isLoading && !isError && data?.note && (
          <Alert severity="info" sx={{ mb: 2, borderRadius: "10px" }}>
            {data.note} Your team section or employment type may not be configured yet.
          </Alert>
        )}

        {/* 3-column board */}
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" },
            gap: 2,
            alignItems: "start",
          }}
        >
          {COLUMNS.map((col) => (
            <Column
              key={col.key}
              col={col}
              members={grouped[col.key]}
              isLoading={isLoading}
            />
          ))}
        </Box>
      </Box>
    </Box>
  );
}