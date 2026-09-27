import { useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../lib/api.js";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { Box, Typography, Avatar, Skeleton, Alert } from "@mui/material";
import GroupsRoundedIcon from "@mui/icons-material/GroupsRounded";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import ScheduleRoundedIcon from "@mui/icons-material/ScheduleRounded";
import BeachAccessRoundedIcon from "@mui/icons-material/BeachAccessRounded";
import AccessTimeRoundedIcon from "@mui/icons-material/AccessTimeRounded";
import InboxRoundedIcon from "@mui/icons-material/InboxRounded";

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

// ── Font loader ───────────────────────────────────────────────────────────────
// Inter reads as a crisp, considered enterprise typeface. Loaded once, quietly.

function useInterFont() {
  useEffect(() => {
    if (document.getElementById("inter-font-link")) return;
    const link = document.createElement("link");
    link.id = "inter-font-link";
    link.rel = "stylesheet";
    link.href =
      "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap";
    document.head.appendChild(link);
  }, []);
}

const FONT = '"Inter", -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';

// ── Design tokens ─────────────────────────────────────────────────────────────

const INK = "#101828";
const TEXT_2 = "#475467";
const TEXT_3 = "#98a2b3";
const BORDER = "#e4e7ec";
const BORDER_LIGHT = "#eef0f3";
const SURFACE = "#ffffff";
const PAGE_BG = "#f8f9fb";
const PRIMARY = "#3555e6";
const PRIMARY_SOFT = "#eef1fd";

const COLUMNS = [
  {
    key: "CHECKED_IN",
    label: "Checked in",
    countKey: "checked_in_count",
    icon: CheckRoundedIcon,
    solid: "#17b26a",
    soft: "#eafcf3",
  },
  {
    key: "YET_TO_CHECK_IN",
    label: "Yet to check in",
    countKey: "yet_to_check_in_count",
    icon: ScheduleRoundedIcon,
    solid: "#f79009",
    soft: "#fffaeb",
  },
  {
    key: "ON_LEAVE",
    label: "On leave",
    countKey: "on_leave_count",
    icon: BeachAccessRoundedIcon,
    solid: "#2e90fa",
    soft: "#eff8ff",
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

// Calm, name-derived avatar tint pairs (bg / text) — a muted palette so the
// roster feels considered rather than randomly colorful.
const AVATAR_TINTS = [
  ["#eef1fd", "#3555e6"],
  ["#f4f3ff", "#6938ef"],
  ["#ecfdf3", "#079455"],
  ["#fff6ed", "#b93815"],
  ["#fdf2fa", "#c11574"],
  ["#f0f9ff", "#026aa2"],
];
function avatarTint(name) {
  const sum = [...(name || "")].reduce((a, c) => a + c.charCodeAt(0), 0);
  return AVATAR_TINTS[sum % AVATAR_TINTS.length];
}

// ── Member row ────────────────────────────────────────────────────────────────

function MemberRow({ member, currentUserId, isLast }) {
  const isCurrentUser = member.id === currentUserId;
  const [avatarBg, avatarFg] = avatarTint(member.name);

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        px: 1.25,
        py: 1.1,
        borderBottom: isLast ? "none" : `1px solid ${BORDER_LIGHT}`,
        transition: "background-color 0.12s ease",
        "&:hover": { bgcolor: "#fafbfc" },
      }}
    >
      <Avatar
        sx={{
          width: 34,
          height: 34,
          bgcolor: avatarBg,
          color: avatarFg,
          fontSize: "0.72rem",
          fontWeight: 700,
          flexShrink: 0,
          fontFamily: FONT,
        }}
      >
        {initials(member.name)}
      </Avatar>

      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Typography
            noWrap
            sx={{ fontFamily: FONT, fontSize: "0.84rem", fontWeight: 600, color: INK, lineHeight: 1.35 }}
          >
            {member.name}
          </Typography>
          {isCurrentUser && (
            <Box
              sx={{
                fontFamily: FONT,
                fontSize: "0.65rem",
                fontWeight: 700,
                color: PRIMARY,
                bgcolor: PRIMARY_SOFT,
                borderRadius: "5px",
                px: 0.7,
                py: 0.15,
                flexShrink: 0,
              }}
            >
              You
            </Box>
          )}
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mt: 0.2, flexWrap: "wrap" }}>
          {member.subsection && (
            <Typography sx={{ fontFamily: FONT, fontSize: "0.72rem", color: TEXT_3, fontWeight: 500 }}>
              {member.subsection}
            </Typography>
          )}

          {member.status === "WEEKEND" && (
            <>
              {member.subsection && <Box sx={{ width: 3, height: 3, borderRadius: "50%", bgcolor: BORDER }} />}
              <Typography sx={{ fontFamily: FONT, fontSize: "0.72rem", color: TEXT_3, fontWeight: 500 }}>
                Weekend
              </Typography>
            </>
          )}

          {member.status === "CHECKED_IN" && member.check_in_time && (
            <>
              {member.subsection && <Box sx={{ width: 3, height: 3, borderRadius: "50%", bgcolor: BORDER }} />}
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.3 }}>
                <AccessTimeRoundedIcon sx={{ fontSize: 12, color: TEXT_3 }} />
                <Typography sx={{ fontFamily: FONT, fontSize: "0.72rem", color: TEXT_3, fontWeight: 500 }}>
                  {formatTime(member.check_in_time)}
                </Typography>
              </Box>
            </>
          )}

          {member.status === "ON_LEAVE" && member.leave_type && (
            <>
              {member.subsection && <Box sx={{ width: 3, height: 3, borderRadius: "50%", bgcolor: BORDER }} />}
              <Typography sx={{ fontFamily: FONT, fontSize: "0.72rem", color: TEXT_2, fontWeight: 600 }}>
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

function Column({ col, members, isLoading, currentUserId }) {
  const Icon = col.icon;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        borderRadius: "14px",
        border: `1px solid ${BORDER}`,
        bgcolor: SURFACE,
        overflow: "hidden",
        boxShadow: "0 1px 2px rgba(16,24,40,0.04)",
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 2,
          py: 1.6,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: `1px solid ${BORDER_LIGHT}`,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.1 }}>
          <Box
            sx={{
              width: 28,
              height: 28,
              borderRadius: "8px",
              bgcolor: col.soft,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Icon sx={{ fontSize: 16, color: col.solid }} />
          </Box>
          <Typography sx={{ fontFamily: FONT, fontSize: "0.86rem", fontWeight: 700, color: INK }}>
            {col.label}
          </Typography>
        </Box>

        {isLoading ? (
          <Skeleton variant="rounded" width={26} height={20} sx={{ borderRadius: "6px" }} />
        ) : (
          <Box
            sx={{
              minWidth: 24,
              height: 22,
              px: 0.85,
              borderRadius: "999px",
              bgcolor: col.soft,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Typography sx={{ fontFamily: FONT, fontSize: "0.72rem", fontWeight: 700, color: col.solid }}>
              {members.length}
            </Typography>
          </Box>
        )}
      </Box>

      {/* Rows */}
      <Box sx={{ flex: 1, overflowY: "auto", minHeight: 200, px: 0.75 }}>
        {isLoading &&
          [...Array(4)].map((_, i) => (
            <Box key={i} sx={{ px: 0.5, py: 1 }}>
              <Skeleton variant="rounded" height={44} sx={{ borderRadius: "8px", bgcolor: "#f2f3f6" }} />
            </Box>
          ))}

        {!isLoading && members.length === 0 && (
          <Box
            sx={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 1,
              py: 6,
            }}
          >
            <InboxRoundedIcon sx={{ fontSize: 22, color: BORDER }} />
            <Typography sx={{ fontFamily: FONT, color: TEXT_3, fontSize: "0.78rem", fontWeight: 500 }}>
              No members
            </Typography>
          </Box>
        )}

        {!isLoading &&
          members.map((m, i) => (
            <MemberRow key={m.id} member={m} currentUserId={currentUserId} isLast={i === members.length - 1} />
          ))}
      </Box>
    </Box>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function MyTeamPage() {
  useInterFont();

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
    YET_TO_CHECK_IN: data?.members?.filter((m) => m.status === "YET_TO_CHECK_IN" || m.status === "WEEKEND") ?? [],
    ON_LEAVE: data?.members?.filter((m) => m.status === "ON_LEAVE") ?? [],
  };

  return (
    <Box sx={{ fontFamily: FONT }}>
      {/* Override EmployeeLayout's inner container to be truly full-width */}
      <Box
        sx={{
          // Pull out of any max-width container the layout imposes
          mx: { xs: -2, sm: -3, md: -4 },
          px: { xs: 2, sm: 3, md: 4 },
          pb: 4,
          minHeight: "100%",
          bgcolor: PAGE_BG,
        }}
      >
        {/* Page header */}
        <Box
          sx={{
            pt: 3.5,
            pb: 2.5,
            display: "flex",
            alignItems: { xs: "flex-start", sm: "center" },
            justifyContent: "space-between",
            flexDirection: { xs: "column", sm: "row" },
            gap: 2,
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: "10px",
                bgcolor: PRIMARY_SOFT,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <GroupsRoundedIcon sx={{ color: PRIMARY, fontSize: 21 }} />
            </Box>
            <Box>
              <Typography
                sx={{ fontFamily: FONT, color: INK, fontSize: "1.2rem", fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.2 }}
              >
                My Team
              </Typography>
              <Typography sx={{ fontFamily: FONT, color: TEXT_2, fontSize: "0.8rem", fontWeight: 500, mt: 0.2 }}>
                {today}
                {data && (
                  <span style={{ color: TEXT_3 }}>
                    {" "}
                    · {data.team_employment_type} · Section {data.team_section}
                  </span>
                )}
              </Typography>
            </Box>
          </Box>

          {/* Summary stat cards */}
          {!isLoading && data && (
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              {COLUMNS.map((col) => {
                const Icon = col.icon;
                return (
                  <Box
                    key={col.key}
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      pl: 1.4,
                      pr: 1.8,
                      py: 1,
                      borderRadius: "10px",
                      bgcolor: SURFACE,
                      border: `1px solid ${BORDER}`,
                      boxShadow: "0 1px 2px rgba(16,24,40,0.04)",
                    }}
                  >
                    <Box
                      sx={{
                        width: 26,
                        height: 26,
                        borderRadius: "7px",
                        bgcolor: col.soft,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <Icon sx={{ fontSize: 14, color: col.solid }} />
                    </Box>
                    <Box>
                      <Typography sx={{ fontFamily: FONT, fontSize: "0.95rem", fontWeight: 800, color: INK, lineHeight: 1.1 }}>
                        {data[col.countKey] ?? 0}
                      </Typography>
                      <Typography sx={{ fontFamily: FONT, fontSize: "0.68rem", color: TEXT_3, fontWeight: 600, whiteSpace: "nowrap" }}>
                        {col.label}
                      </Typography>
                    </Box>
                  </Box>
                );
              })}
            </Box>
          )}

          {isLoading && (
            <Box sx={{ display: "flex", gap: 1 }}>
              {[120, 130, 110].map((w, i) => (
                <Skeleton key={i} variant="rounded" width={w} height={52} sx={{ borderRadius: "10px" }} />
              ))}
            </Box>
          )}
        </Box>

        {/* Errors / notices */}
        {isError && (
          <Alert severity="error" sx={{ mb: 2, borderRadius: "10px", fontFamily: FONT }}>
            {error?.message ?? "Failed to load team data. Please try again."}
          </Alert>
        )}
        {!isLoading && !isError && data?.note && (
          <Alert severity="info" sx={{ mb: 2, borderRadius: "10px", fontFamily: FONT }}>
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
              currentUserId={data?.current_user_id}
            />
          ))}
        </Box>
      </Box>
    </Box>
  );
}