import { useEffect, useRef, useState } from "react";
import { Box, IconButton, Paper, TextField, Tooltip, Typography } from "@mui/material";
import AttachFileRoundedIcon from "@mui/icons-material/AttachFileRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import TableChartOutlinedIcon from "@mui/icons-material/TableChartOutlined";

const ACCEPTED_FILE_TYPES = [
  ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg",
];
const ACCEPTED_FILE_TYPES_ATTRIBUTE = ACCEPTED_FILE_TYPES.join(",");

function createAttachment(file) {
  return {
    id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
    name: file.name,
    type: file.type,
    size: file.size,
    file,
  };
}

function formatFileSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 102.4) / 10} KB`;
  return `${Math.round(size / (102.4 * 102.4)) / 10} MB`;
}

function getFileIcon(file) {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (file.type.startsWith("image/") || ["png", "jpg", "jpeg"].includes(extension)) return <ImageOutlinedIcon fontSize="small" />;
  if (extension === "pdf") return <PictureAsPdfOutlinedIcon fontSize="small" />;
  if (["xls", "xlsx", "csv"].includes(extension)) return <TableChartOutlinedIcon fontSize="small" />;
  if (["doc", "docx", "txt"].includes(extension)) return <DescriptionOutlinedIcon fontSize="small" />;
  return <InsertDriveFileOutlinedIcon fontSize="small" />;
}

export function ChatInput({ value, onChange, onSend, disabled = false, placeholder = "Ask HR Copilot something..." }) {
  const [attachments, setAttachments] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);
  const attachmentsRef = useRef([]);

  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  useEffect(() => () => {
    attachmentsRef.current.forEach((attachment) => {
      if (attachment.file.type.startsWith("image/")) URL.revokeObjectURL(attachment.previewUrl);
    });
  }, []);

  function addFiles(fileList) {
    const acceptedFiles = Array.from(fileList).filter((file) => {
      const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
      return ACCEPTED_FILE_TYPES.includes(extension);
    });
    if (!acceptedFiles.length) return;

    setAttachments((current) => [
      ...current,
      ...acceptedFiles.map((file) => ({ ...createAttachment(file), previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : null })),
    ]);
  }

  function handleFileChange(event) {
    addFiles(event.target.files);
    event.target.value = "";
  }

  function removeAttachment(id) {
    setAttachments((current) => {
      const removed = current.find((attachment) => attachment.id === id);
      if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      return current.filter((attachment) => attachment.id !== id);
    });
  }

  function handleSubmit(event) {
    event.preventDefault();
    const content = value.trim();
    if ((!content && !attachments.length) || disabled) return;
    onSend(content, attachments.map(({ id, name, type, size, file }) => ({ id, name, type, size, file })));
    attachments.forEach((attachment) => {
      if (attachment.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
    });
    setAttachments([]);
  }

  function handleDrop(event) {
    event.preventDefault();
    setIsDragging(false);
    if (!disabled) addFiles(event.dataTransfer.files);
  }

  return (
    <Paper
      component="form"
      onSubmit={handleSubmit}
      onDragOver={(event) => { event.preventDefault(); if (!disabled) setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      variant="outlined"
      sx={{ borderRadius: 3, overflow: "hidden", borderColor: isDragging ? "primary.main" : "divider", bgcolor: isDragging ? "action.hover" : "background.paper", transition: "border-color 120ms ease, background-color 120ms ease" }}
    >
      {attachments.length > 0 && (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, px: 1.5, pt: 1.5 }}>
          {attachments.map((attachment) => (
            <Box key={attachment.id} sx={{ display: "flex", alignItems: "center", gap: 0.75, maxWidth: { xs: "100%", sm: 250 }, px: 1, py: 0.75, border: "1px solid", borderColor: "divider", borderRadius: 1.5, bgcolor: "action.hover" }}>
              {attachment.previewUrl ? <Box component="img" src={attachment.previewUrl} alt="" sx={{ width: 28, height: 28, objectFit: "cover", borderRadius: 0.75 }} /> : <Box sx={{ display: "grid", placeItems: "center", width: 28, height: 28, color: "primary.main" }}>{getFileIcon(attachment.file)}</Box>}
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography variant="caption" fontWeight={600} noWrap display="block">{attachment.name}</Typography>
                <Typography variant="caption" color="text.secondary">{formatFileSize(attachment.size)}</Typography>
              </Box>
              <IconButton size="small" aria-label={`Remove ${attachment.name}`} onClick={() => removeAttachment(attachment.id)} disabled={disabled}><CloseRoundedIcon fontSize="small" /></IconButton>
            </Box>
          ))}
        </Box>
      )}
      <Box sx={{ display: "flex", alignItems: "flex-end", gap: 0.5, px: 1, py: 0.75 }}>
        <input ref={fileInputRef} type="file" multiple accept={ACCEPTED_FILE_TYPES_ATTRIBUTE} onChange={handleFileChange} hidden />
        <Tooltip title="Attach files">
          <IconButton type="button" aria-label="Attach files" onClick={() => fileInputRef.current?.click()} disabled={disabled} sx={{ mb: 0.25 }}><AttachFileRoundedIcon /></IconButton>
        </Tooltip>
        <TextField fullWidth multiline maxRows={4} variant="standard" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} disabled={disabled} InputProps={{ disableUnderline: true }} sx={{ px: 0.75, py: 0.5 }} />
        <Tooltip title="Send message">
          <IconButton type="submit" aria-label="Send message" color="primary" disabled={disabled || (!value.trim() && !attachments.length)} sx={{ mb: 0.25 }}><SendRoundedIcon /></IconButton>
        </Tooltip>
      </Box>
    </Paper>
  );
}