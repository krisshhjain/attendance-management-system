import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { RequireAuth } from "../components/RequireAuth.jsx";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogContent,
  Divider,
  FormControl,
  InputAdornment,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import NotificationsNoneOutlinedIcon from "@mui/icons-material/NotificationsNoneOutlined";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import CalendarTodayOutlinedIcon from "@mui/icons-material/CalendarTodayOutlined";

export const Route = createFileRoute("/regularization")({
  component: () => (
    <RequireAuth>
      <RegularizationPage />
    </RequireAuth>
  ),
});

function StatCard({ label, count, tone }) {
  const palette = {
    warning: { color: "#d97706", border: "rgba(245, 158, 11, 0.25)" },
    success: { color: "#16a34a", border: "rgba(34, 197, 94, 0.25)" },
    error: { color: "#dc2626", border: "rgba(239, 68, 68, 0.25)" },
  };

  const styles = palette[tone] || palette.warning;

  return (
    <Card
      elevation={0}
      sx={{
        flex: 1,
        minWidth: 180,
        borderRadius: "12px",
        border: `1px solid ${styles.border}`,
        backgroundColor: "#fff",
      }}
    >
      <CardContent sx={{ p: 2.25, pb: "16px !important" }}>
        <Typography variant="caption" sx={{ color: "#64748b", fontWeight: 500, display: "block", mb: 1 }}>
          {label}
        </Typography>
        <Typography
          variant="h6"
          sx={{
            color: styles.color,
            fontWeight: 700,
            fontSize: "1.06rem",
            lineHeight: 1.2,
          }}
        >
          {count} requests
        </Typography>
      </CardContent>
    </Card>
  );
}

function makeRecordForDate(dateValue) {
  if (!dateValue) return null;
  const dateObj = new Date(`${dateValue}T00:00:00`);

  return {
    date: dateValue,
    label: dateObj.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    }),
    checkIn: "",
    checkOut: "",
    totalHours: "00h 00m",
    reason: "Forgot to Check Out",
    description: "",
  };
}

function RegularizationPage() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const [isRequesting, setIsRequesting] = useState(false);
  const [selectedDate, setSelectedDate] = useState("2026-09-28");
  const [workLocation, setWorkLocation] = useState("Office");
  const [attachmentName, setAttachmentName] = useState("");
  const [records, setRecords] = useState(() => [makeRecordForDate("2026-09-28")]);

  const requestSummary = [
    { label: "Pending", count: 0, tone: "warning" },
    { label: "Approved", count: 0, tone: "success" },
    { label: "Rejected", count: 0, tone: "error" },
  ];

  const currentRow = useMemo(() => {
    if (!selectedDate) return null;
    return records.find((row) => row.date === selectedDate) || makeRecordForDate(selectedDate);
  }, [records, selectedDate]);

  const handleDateChange = (value) => {
    setSelectedDate(value);
    const nextRow = makeRecordForDate(value);
    setRecords((prev) => {
      if (!value) return prev;
      const filtered = prev.filter((entry) => entry.date !== value);
      return [...filtered, nextRow];
    });
  };

  const handleAttachment = (event) => {
    const file = event.target.files?.[0];
    setAttachmentName(file ? file.name : "");
  };

  const handleSubmit = () => {
    const payload = {
      date: selectedDate,
      work_location: workLocation,
      attachment: attachmentName,
      records: records.filter((row) => row.date === selectedDate),
    };

    console.log("Regularization payload:", payload);
    setIsRequesting(false);
  };

  return (
    <Box sx={{ maxWidth: 1200, width: "100%", mx: "auto", px: { xs: 2, sm: 3 }, py: 2 }}>
      <Box
        sx={{
          display: "flex",
          alignItems: { xs: "flex-start", sm: "center" },
          justifyContent: "space-between",
          gap: 2,
          mb: 2,
          pb: 1,
          flexDirection: { xs: "column", sm: "row" },
        }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, color: "#111827", fontSize: { xs: "1.75rem", md: "2rem" }, lineHeight: 1.2 }}>
            Regularization
          </Typography>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5 }}>
            Request corrections for missing or incorrect attendance records.
          </Typography>
        </Box>

        <Button
          variant="contained"
          onClick={() => setIsRequesting(true)}
          sx={{
            borderRadius: "10px",
            px: 2.25,
            py: 1,
            background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
            textTransform: "none",
            fontWeight: 700,
            boxShadow: "0 8px 18px rgba(79, 70, 229, 0.22)",
            "&:hover": {
              background: "linear-gradient(135deg, #4338ca 0%, #6d28d9 100%)",
            },
          }}
        >
          + Request Regularization
        </Button>
      </Box>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "repeat(3, minmax(180px, 1fr))" },
          gap: 2,
          mb: 3,
        }}
      >
        {requestSummary.map((item) => (
          <StatCard key={item.label} label={item.label} count={item.count} tone={item.tone} />
        ))}
      </Box>

      <Card
        elevation={0}
        sx={{
          width: "100%",
          borderRadius: "14px",
          border: "1px solid #e2e8f0",
          backgroundColor: "#fff",
          overflow: "hidden",
        }}
      >
        <Box sx={{ px: 2.5, py: 1.8, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#111827", fontSize: "1.03rem" }}>
              My Requests
            </Typography>
            <Typography variant="body2" sx={{ color: "#64748b" }}>
              Track regularization requests and approval status
            </Typography>
          </Box>
        </Box>

        <Divider />

        <Box
          sx={{
            minHeight: 260,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            px: 3,
            py: 4,
          }}
        >
          <Stack spacing={1.75} alignItems="center">
            <Box
              sx={{
                width: 44,
                height: 44,
                borderRadius: "50%",
                backgroundColor: "#f1f5f9",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#64748b",
              }}
            >
              <NotificationsNoneOutlinedIcon fontSize="small" />
            </Box>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#1f2937" }}>
              No regularization requests
            </Typography>
            <Typography variant="body2" sx={{ color: "#64748b", maxWidth: 420 }}>
              Submitted attendance corrections will appear here.
            </Typography>
          </Stack>
        </Box>
      </Card>

      <Dialog
        open={isRequesting}
        onClose={() => setIsRequesting(false)}
        maxWidth="xl"
        fullWidth
        fullScreen={isMobile}
        PaperProps={{
          sx: {
            borderRadius: isMobile ? 0 : 2,
            overflow: "hidden",
            backgroundColor: "#f8fafc",
            boxShadow: "0 12px 30px rgba(15, 23, 42, 0.12)",
            m: isMobile ? 0 : 3,
            width: isMobile ? "100%" : "auto",
          },
        }}
      >
        <DialogContent sx={{ p: 0 }}>
          <Box sx={{ p: 3, pb: 2.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
              <Box>
                <Typography variant="h4" sx={{ fontWeight: 700, color: "#111827", fontSize: "1.2rem", lineHeight: 1.2 }}>
                  Request Regularization
                </Typography>
                <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5 }}>
                  Correct attendance details for the selected work period.
                </Typography>
              </Box>

              <Button
                variant="outlined"
                onClick={() => setIsRequesting(false)}
                sx={{
                  borderRadius: "10px",
                  borderColor: "#dbe3ef",
                  color: "#334155",
                  textTransform: "none",
                  fontWeight: 600,
                }}
              >
                Back to requests
              </Button>
            </Box>

            <Box sx={{ border: "1px solid #e2e8f0", borderRadius: "12px", backgroundColor: "#fff", p: 2.5 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#111827", mb: 1.2 }}>
                Request details
              </Typography>
              <Typography variant="body2" sx={{ color: "#64748b", mb: 2.5 }}>
                Select a period and provide the corrected work records.
              </Typography>

              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" }, gap: 2.5, mb: 2.5 }}>
                <FormControl fullWidth>
                  <TextField
                    select
                    label="Period"
                    defaultValue="Day"
                    size="small"
                    sx={{ backgroundColor: "#fff" }}
                  >
                    <MenuItem value="Day">Day</MenuItem>
                  </TextField>
                </FormControl>

                <TextField
                  label="Date"
                  type="date"
                  size="small"
                  value={selectedDate}
                  onChange={(event) => handleDateChange(event.target.value)}
                  InputLabelProps={{ shrink: true }}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <CalendarTodayOutlinedIcon fontSize="small" sx={{ color: "#64748b" }} />
                      </InputAdornment>
                    ),
                  }}
                />

                <TextField
                  select
                  label="Work location"
                  size="small"
                  value={workLocation}
                  onChange={(event) => setWorkLocation(event.target.value)}
                  sx={{ backgroundColor: "#fff" }}
                >
                  <MenuItem value="Office">Office</MenuItem>
                  <MenuItem value="Remote">Remote</MenuItem>
                  <MenuItem value="Field">Field</MenuItem>
                </TextField>
              </Box>

              <Box
                sx={{
                  border: "1px dashed #93c5fd",
                  borderRadius: "12px",
                  backgroundColor: "#f8fbff",
                  minHeight: 140,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  textAlign: "center",
                  mb: 2.5,
                  p: 2,
                }}
              >
                <Stack alignItems="center" spacing={0.8}>
                  <CloudUploadOutlinedIcon sx={{ fontSize: 26, color: "#4f46e5" }} />
                  <Typography variant="body1" sx={{ fontWeight: 600, color: "#111827" }}>
                    Upload supporting document
                  </Typography>
                  <Typography variant="caption" sx={{ color: "#64748b" }}>
                    PDF, XLS, DOC or image • Maximum 5MB
                  </Typography>
                  <Button
                    component="label"
                    variant="outlined"
                    sx={{
                      borderRadius: "8px",
                      textTransform: "none",
                      borderColor: "#dbe3ef",
                      color: "#334155",
                      mt: 0.5,
                    }}
                  >
                    Choose file
                    <input hidden type="file" onChange={handleAttachment} />
                  </Button>
                  {attachmentName && (
                    <Typography variant="caption" sx={{ color: "#16a34a", fontWeight: 600 }}>
                      {attachmentName}
                    </Typography>
                  )}
                </Stack>
              </Box>

              <Box sx={{ mb: 1.5 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#111827", fontSize: "1rem", mb: 1 }}>
                  Worked Day
                </Typography>
                <Typography variant="caption" sx={{ color: "#64748b" }}>
                  1 attendance record in this day
                </Typography>
              </Box>

              {currentRow ? (
                <Box sx={{ border: "1px solid #e2e8f0", borderRadius: "12px", backgroundColor: "#fff", overflowX: "auto" }}>
                  <TableContainer sx={{ overflowX: "auto" }}>
                    <Table size="small" sx={{ minWidth: { xs: 720, md: 0 } }}>
                      <TableHead>
                        <TableRow sx={{ backgroundColor: "#f8fafc" }}>
                          <TableCell sx={{ fontWeight: 700, color: "#475569", py: 1.25 }}>Date</TableCell>
                          <TableCell sx={{ fontWeight: 700, color: "#475569", py: 1.25 }}>Check-in</TableCell>
                          <TableCell sx={{ fontWeight: 700, color: "#475569", py: 1.25 }}>Check-out</TableCell>
                          <TableCell sx={{ fontWeight: 700, color: "#475569", py: 1.25 }}>Total hours</TableCell>
                          <TableCell sx={{ fontWeight: 700, color: "#475569", py: 1.25 }}>Reason</TableCell>
                          <TableCell sx={{ fontWeight: 700, color: "#475569", py: 1.25 }}>Description</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        <TableRow>
                          <TableCell sx={{ py: 1.5 }}>
                            <TextField
                              size="small"
                              value={currentRow.label}
                              InputProps={{ readOnly: true }}
                              sx={{ minWidth: 120 }}
                            />
                          </TableCell>
                          <TableCell sx={{ py: 1.5 }}>
                            <TextField size="small" value={currentRow.checkIn} placeholder="--:--" sx={{ minWidth: 110 }} />
                          </TableCell>
                          <TableCell sx={{ py: 1.5 }}>
                            <TextField size="small" value={currentRow.checkOut} placeholder="--:--" sx={{ minWidth: 110 }} />
                          </TableCell>
                          <TableCell sx={{ py: 1.5 }}>
                            <TextField size="small" value={currentRow.totalHours} sx={{ minWidth: 110 }} />
                          </TableCell>
                          <TableCell sx={{ py: 1.5 }}>
                            <TextField
                              select
                              size="small"
                              value={currentRow.reason}
                              sx={{ minWidth: 180 }}
                            >
                              <MenuItem value="Forgot to Check Out">Forgot to Check Out</MenuItem>
                              <MenuItem value="Wrong shift time">Wrong shift time</MenuItem>
                              <MenuItem value="Missed punch">Missed punch</MenuItem>
                              <MenuItem value="Travel delay">Travel delay</MenuItem>
                            </TextField>
                          </TableCell>
                          <TableCell sx={{ py: 1.5 }}>
                            <TextField
                              size="small"
                              value={currentRow.description}
                              placeholder="Add explanation"
                              sx={{ minWidth: 200 }}
                            />
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Box>
              ) : (
                <Alert severity="info">Select a date to populate the correction form.</Alert>
              )}

              <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1.5, pt: 3 }}>
                <Button
                  variant="outlined"
                  onClick={() => setIsRequesting(false)}
                  sx={{
                    minWidth: 120,
                    borderRadius: "10px",
                    borderColor: "#dbe3ef",
                    color: "#334155",
                    textTransform: "none",
                    fontWeight: 600,
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  onClick={handleSubmit}
                  sx={{
                    minWidth: 150,
                    borderRadius: "10px",
                    background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
                    textTransform: "none",
                    fontWeight: 700,
                    boxShadow: "0 8px 18px rgba(79, 70, 229, 0.2)",
                    "&:hover": {
                      background: "linear-gradient(135deg, #4338ca 0%, #6d28d9 100%)",
                    },
                  }}
                >
                  Submit Request
                </Button>
              </Box>
            </Box>
          </Box>
        </DialogContent>
      </Dialog>
    </Box>
  );
}
