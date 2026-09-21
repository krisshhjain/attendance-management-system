import { Box, Paper, Typography, useTheme } from "@mui/material";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

export function AttendanceChart({ data }) {
  const theme = useTheme();

  // Calculate missing people safely (ensure we don't go negative)
  const notArrived = Math.max(0, (data?.active_employees || 0) - ((data?.checked_in_today || 0) + (data?.completed_today || 0)));

  const chartData = [
    { name: "Completed", value: data?.completed_today || 0, color: "#4caf50" }, // Green
    { name: "Currently In", value: data?.checked_in_today || 0, color: theme.palette.primary.main }, // Purple
    { name: "Not Arrived", value: notArrived, color: "#e0e0e0" }, // Grey
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
        boxShadow: "0px 2px 4px rgba(0, 0, 0, 0.02)"
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
          Today's Attendance
        </Typography>
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
