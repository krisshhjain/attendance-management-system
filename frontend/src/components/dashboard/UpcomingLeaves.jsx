import { Box, Paper, Typography, Divider, useTheme } from "@mui/material";
import EventNoteIcon from '@mui/icons-material/EventNote';
import CelebrationIcon from '@mui/icons-material/Celebration';
import { formatHolidayDate, useUpcomingHolidays } from "../../data/holidayCalendar.js";

export function UpcomingLeaves() {
  const theme = useTheme();

  const { holidays: futureLeaves, isLoading, isError } = useUpcomingHolidays();

  return (
    <Paper
      elevation={0}
      sx={{
        p: 3,
        borderRadius: "16px",
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "white",
        boxShadow: "0px 1px 3px rgba(15,23,42,0.03)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        maxHeight: "400px",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "#0f172a", fontSize: "16px" }}>
            Upcoming Holidays
          </Typography>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5, fontSize: "12px" }}>
            Company-wide holiday schedule
          </Typography>
        </Box>
        <Box sx={{ 
          width: 36, height: 36, borderRadius: "10px", 
          bgcolor: "#f0fdfa", color: "#0d9488", 
          display: "flex", alignItems: "center", justifyContent: "center" 
        }}>
          <CelebrationIcon fontSize="small" />
        </Box>
      </Box>
      
      <Box sx={{ flexGrow: 1, overflowY: "auto", pr: 1, mt: 1 }}>
        {isLoading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}><Typography sx={{ color: "#94a3b8", fontSize: 14 }}>Loading holidays...</Typography></Box>
        ) : isError ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}><Typography sx={{ color: "#b91c1c", fontSize: 14 }}>Could not load holidays.</Typography></Box>
        ) : futureLeaves.length === 0 ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
             <Typography sx={{ color: "#94a3b8", fontSize: "14px" }}>No upcoming holidays for this year.</Typography>
          </Box>
        ) : (
          futureLeaves.map((leave, index) => (
            <Box key={index}>
              <Box sx={{ 
                display: "flex", alignItems: "center", justifyContent: "space-between", 
                py: 1.5,
                transition: "background-color 0.15s",
                borderRadius: "8px",
                px: 1,
                "&:hover": { bgcolor: "#f8fafc" }
              }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                  <Box sx={{ 
                    width: 10, height: 10, borderRadius: "50%", 
                    bgcolor: leave.color, boxShadow: `0 0 0 4px ${leave.color}20` 
                  }} />
                  <Typography sx={{ fontWeight: 600, color: "#334155", fontSize: "14px" }}>
                    {leave.name}
                  </Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <EventNoteIcon sx={{ fontSize: 14, color: "#94a3b8" }} />
                  <Typography sx={{ fontSize: "13px", color: "#64748b", fontWeight: 500 }}>
                    {formatHolidayDate(leave.date)}
                  </Typography>
                </Box>
              </Box>
              {index < futureLeaves.length - 1 && <Divider sx={{ borderColor: "#f1f5f9" }} />}
            </Box>
          ))
        )}
      </Box>
    </Paper>
  );
}
