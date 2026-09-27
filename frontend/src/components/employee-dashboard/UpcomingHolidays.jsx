import { Box, Paper, Typography } from "@mui/material";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";

const HOLIDAYS = [
  { name: "Company Holiday", date: "Oct 16, 2026", color: "#6366f1" },
  { name: "Regional Holiday", date: "Nov 21, 2026", color: "#f59e0b" },
  { name: "Year-End Holiday", date: "Jan 01, 2027", color: "#10b981" },
];

export function UpcomingHolidays() {
  return (
    <Paper sx={{ overflow: "hidden", borderRadius: 3, border: "1px solid", borderColor: "#dbe3ee", boxShadow: "0 2px 8px rgba(15, 23, 42, 0.06)" }}>
      <Box sx={{ px: 2.5, py: 1.75, borderBottom: "1px solid", borderColor: "#e5ebf2" }}>
        <Typography sx={{ fontSize: 15, fontWeight: 700, color: "#1e293b" }}>Upcoming Holidays</Typography>
        <Typography sx={{ fontSize: 11, color: "#718096", mt: 0.25 }}>Company holiday calendar</Typography>
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
        {HOLIDAYS.map((holiday) => (
          <Box key={holiday.name} sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, px: 2.5, py: 1.5, borderRight: { md: "1px solid" }, borderBottom: { xs: "1px solid", md: 0 }, borderColor: "#e5ebf2", "&:last-child": { borderRight: 0, borderBottom: 0 } }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, minWidth: 0 }}>
              <Box sx={{ width: 8, height: 8, flexShrink: 0, borderRadius: "50%", bgcolor: holiday.color }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: 11, fontWeight: 700, color: "#475569", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{holiday.name}</Typography>
                <Typography sx={{ fontSize: 10, color: "#94a3b8", mt: 0.25 }}>{holiday.date}</Typography>
              </Box>
            </Box>
            <CalendarMonthOutlinedIcon sx={{ fontSize: 16, flexShrink: 0, color: "#94a3b8" }} />
          </Box>
        ))}
      </Box>
    </Paper>
  );
}