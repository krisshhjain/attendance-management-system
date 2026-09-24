import { useQueries } from "@tanstack/react-query";
import { Box, Paper, Typography, CircularProgress, useTheme } from "@mui/material";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getAdminAttendance } from "../../lib/attendance.js";

export function WeeklyTrendChart() {
  const theme = useTheme();
  
  // Generate last 7 calendar days dates, skipping weekends
  const dates = [];
  let d = new Date();
  for (let i = 0; i < 7; i++) {
    if (d.getDay() !== 0 && d.getDay() !== 6) {
      dates.unshift(new Date(d));
    }
    d.setDate(d.getDate() - 1);
  }

  const queries = useQueries({
    queries: dates.map((date) => ({
      queryKey: ["adminAttendance", date.toLocaleDateString("en-CA")],
      queryFn: () => getAdminAttendance(date.toLocaleDateString("en-CA")),
      staleTime: 5 * 60 * 1000,
    })),
  });

  const isLoading = queries.some(q => q.isLoading);

  // Process data
  const chartData = dates.map((date, index) => {
    const query = queries[index];
    const records = Array.isArray(query.data) ? query.data : (query.data?.results || []);
    
    // Count Present or Incomplete (checked in)
    const present = records.filter(r => r.status === "PRESENT" || r.status === "INCOMPLETE").length;
    const onLeave = records.filter(r => r.status === "LEAVE").length;
    
    return {
      name: date.toLocaleDateString("en-US", { weekday: "short", day: "numeric" }),
      dateStr: date.toLocaleDateString("en-CA"),
      Present: present,
      "On Leave": onLeave,
    };
  });

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
      }}
    >
      <Box sx={{ mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "#0f172a", fontSize: "16px" }}>
          7-Day Attendance Trend
        </Typography>
        <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5, fontSize: "12px" }}>
          Present vs Leave over the last week
        </Typography>
      </Box>
      
      <Box sx={{ flexGrow: 1, minHeight: 250, position: "relative" }}>
        {isLoading ? (
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
            <CircularProgress size={32} thickness={4} sx={{ color: theme.palette.primary.main }} />
          </Box>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorPresent" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={theme.palette.primary.main} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={theme.palette.primary.main} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis 
                dataKey="name" 
                axisLine={false} 
                tickLine={false} 
                tick={{ fill: "#64748b", fontSize: 12, fontWeight: 500 }} 
                dy={10}
              />
              <YAxis 
                axisLine={false} 
                tickLine={false} 
                tick={{ fill: "#64748b", fontSize: 12, fontWeight: 500 }}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1)", padding: "12px" }}
                itemStyle={{ fontWeight: 600, fontSize: "14px" }}
                labelStyle={{ color: "#64748b", marginBottom: "4px", fontSize: "12px", fontWeight: 600 }}
              />
              <Area 
                type="monotone" 
                dataKey="Present" 
                stroke={theme.palette.primary.main} 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorPresent)" 
                activeDot={{ r: 6, strokeWidth: 0, fill: theme.palette.primary.main }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Box>
    </Paper>
  );
}
