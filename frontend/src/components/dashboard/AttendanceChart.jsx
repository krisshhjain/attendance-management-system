import { Box, Paper, Typography, useTheme } from "@mui/material";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

export function AttendanceChart({ data }) {
  const theme = useTheme();

  const isWorkingDay = data?.is_working_day ?? true;

  // Calculate missing people safely (ensure we don't go negative)
  // If it's a holiday, nobody is expected, so missing is 0.
  const notArrived = isWorkingDay ? Math.max(0, (data?.active_employees || 0) - ((data?.checked_in_today || 0) + (data?.completed_today || 0))) : 0;

  const chartData = [
    { name: "Completed", value: data?.completed_today || 0, color: "#4caf50" }, // Green
    { name: "Currently In", value: data?.checked_in_today || 0, color: theme.palette.primary.main }, // Purple
    { name: isWorkingDay ? "Not Arrived" : "Holiday", value: isWorkingDay ? notArrived : data?.active_employees || 0, color: "#e0e0e0" }, // Grey
  ];

  return (
    <Paper
      elevation={0}
      sx={{
        p: 3,
        borderRadius: "16px",
        border: "1px solid",
        borderColor: "divider",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "white",
        boxShadow: "0px 1px 3px rgba(15,23,42,0.03)",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "#0f172a", fontSize: "16px" }}>
            Attendance Overview
          </Typography>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5, fontSize: "12px" }}>
            Today's attendance status
          </Typography>
        </Box>
      </Box>
      <Box sx={{ flexGrow: 1, minHeight: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={70}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip 
              contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
              itemStyle={{ fontWeight: 500 }}
            />
            <Legend 
              verticalAlign="bottom" 
              height={36} 
              iconType="circle"
              formatter={(value, entry) => <span style={{ color: "#4b5563", fontWeight: 500, fontSize: "0.875rem" }}>{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  );
}
