import { Box, Paper, Typography } from "@mui/material";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import { formatHolidayDate, useUpcomingHolidays } from "../../data/holidayCalendar.js";

export function UpcomingHolidays() {
  const { holidays, isLoading, isError } = useUpcomingHolidays();

  return (
    <Paper sx={{ overflow: "hidden", minHeight: { xs: 190, md: 180 }, flexShrink: 0, borderRadius: 3, border: "1px solid", borderColor: "#dbe3ee", boxShadow: "0 2px 8px rgba(15, 23, 42, 0.06)" }}>
      <Box sx={{ px: 2.5, py: 1.75, minHeight: 72, boxSizing: "border-box", borderBottom: "1px solid", borderColor: "#e5ebf2" }}>
        <Typography sx={{ fontSize: 15, fontWeight: 700, color: "#1e293b" }}>Upcoming Holidays</Typography>
        <Typography sx={{ fontSize: 11, color: "#718096", mt: 0.25 }}>Company holiday calendar</Typography>
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" } }}>
        {isLoading ? (
          <Typography sx={{ px: 2.5, py: 3, color: "#94a3b8", fontSize: 13 }}>Loading holidays...</Typography>
        ) : isError ? (
          <Typography sx={{ px: 2.5, py: 3, color: "#b91c1c", fontSize: 13 }}>Could not load holidays.</Typography>
        ) : holidays.length === 0 ? (
          <Typography sx={{ px: 2.5, py: 3, color: "#94a3b8", fontSize: 13 }}>
            No upcoming holidays for this year.
          </Typography>
        ) : holidays.map((holiday) => (
          <Box key={holiday.name} sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, minHeight: 56, px: 2.5, py: 1.5, boxSizing: "border-box", borderRight: { md: "1px solid" }, borderBottom: { xs: "1px solid", md: 0 }, borderColor: "#e5ebf2", "&:last-child": { borderRight: 0, borderBottom: 0 } }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, minWidth: 0 }}>
              <Box sx={{ width: 8, height: 8, flexShrink: 0, borderRadius: "50%", bgcolor: holiday.color }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: 11, fontWeight: 700, color: "#475569", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{holiday.name}</Typography>
                <Typography sx={{ fontSize: 10, color: "#94a3b8", mt: 0.25 }}>{formatHolidayDate(holiday.date)}</Typography>
              </Box>
            </Box>
            <CalendarMonthOutlinedIcon sx={{ fontSize: 16, flexShrink: 0, color: "#94a3b8" }} />
          </Box>
        ))}
      </Box>
    </Paper>
  );
}
