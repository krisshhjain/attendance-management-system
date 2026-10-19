import {
  Attachment as AttachmentIcon,
  Close as CloseIcon,
  Download as DownloadIcon,
  Error as ErrorIcon,
  Fullscreen as FullscreenIcon,
  OpenInNew as OpenInNewIcon,
} from "@mui/icons-material";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Tooltip,
  Typography,
} from "@mui/material";

function getFileExtension(url) {
  return url.split(".").pop().toLowerCase();
}

function isImageFile(url) {
  return ["jpg", "jpeg", "png", "gif", "bmp", "webp"].includes(getFileExtension(url));
}

function isPdfFile(url) {
  return getFileExtension(url) === "pdf";
}

export function LeaveDocumentPreviewDialog({ documentModal, setDocumentModal, notifyError }) {
  const handleDownloadFile = (url, fileName) => {
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName || "document";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Dialog
      open={documentModal.open}
      onClose={() => setDocumentModal({ open: false, url: "", title: "", fileName: "" })}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: "90vh", maxHeight: "90vh" },
      }}
    >
      <DialogTitle
        sx={{
          fontWeight: 700,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: 1,
          borderColor: "divider",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <AttachmentIcon color="primary" />
          <Typography variant="h6" component="span">
            {documentModal.title}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Tooltip title="Download Document">
            <IconButton
              size="small"
              color="primary"
              aria-label="Download document"
              onClick={() => handleDownloadFile(documentModal.url, documentModal.fileName)}
            >
              <DownloadIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Open in New Tab">
            <IconButton
              size="small"
              color="primary"
              aria-label="Open document in new tab"
              onClick={() => window.open(documentModal.url, "_blank")}
            >
              <OpenInNewIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Fullscreen">
            <IconButton
              size="small"
              color="primary"
              aria-label="Open document fullscreen"
              onClick={async () => {
                const elem = document.querySelector("[data-document-preview]");
                if (elem && elem.requestFullscreen) {
                  try {
                    await elem.requestFullscreen();
                  } catch (fullscreenError) {
                    notifyError(fullscreenError, {
                      title: "Fullscreen unavailable",
                      fallback: "Could not open the document preview in fullscreen.",
                    });
                  }
                }
              }}
            >
              <FullscreenIcon />
            </IconButton>
          </Tooltip>
          <IconButton
            size="small"
            aria-label="Close document preview"
            onClick={() => setDocumentModal({ open: false, url: "", title: "", fileName: "" })}
          >
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent sx={{ p: 0, display: "flex", flexDirection: "column", height: "100%" }}>
        {documentModal.url && (
          <Box
            sx={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              backgroundColor: "#f5f5f5",
              position: "relative",
            }}
            data-document-preview
          >
            {isImageFile(documentModal.url) ? (
              <Box
                sx={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  p: 2,
                }}
              >
                <img
                  src={documentModal.url}
                  alt="Document preview"
                  style={{
                    maxWidth: "100%",
                    maxHeight: "100%",
                    objectFit: "contain",
                    borderRadius: "8px",
                    boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                  }}
                  onError={(e) => {
                    e.target.style.display = "none";
                    e.target.nextElementSibling.style.display = "flex";
                  }}
                />
                <Box
                  sx={{
                    display: "none",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 2,
                    p: 4,
                    textAlign: "center",
                  }}
                >
                  <ErrorIcon sx={{ fontSize: 48, color: "text.disabled" }} />
                  <Typography variant="body1" color="text.secondary">
                    Unable to preview this image
                  </Typography>
                </Box>
              </Box>
            ) : isPdfFile(documentModal.url) ? (
              <iframe
                src={`${documentModal.url}#toolbar=1&navpanes=1&scrollbar=1`}
                width="100%"
                height="100%"
                style={{ border: "none", flex: 1 }}
                title="PDF Preview"
                onError={() => {
                  console.log("PDF preview failed");
                }}
              />
            ) : (
              <Box
                sx={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 2,
                  p: 4,
                  textAlign: "center",
                }}
              >
                <AttachmentIcon sx={{ fontSize: 64, color: "primary.main" }} />
                <Typography variant="h6" color="text.primary">
                  {documentModal.fileName}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Preview not available for this file type
                </Typography>
                <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
                  <Button
                    variant="contained"
                    startIcon={<DownloadIcon />}
                    onClick={() => handleDownloadFile(documentModal.url, documentModal.fileName)}
                  >
                    Download File
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<OpenInNewIcon />}
                    onClick={() => window.open(documentModal.url, "_blank")}
                  >
                    Open in Browser
                  </Button>
                </Box>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions
        sx={{
          borderTop: 1,
          borderColor: "divider",
          p: 2,
          backgroundColor: "grey.50",
        }}
      >
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          File: {documentModal.fileName}
        </Typography>
        <Button
          onClick={() => handleDownloadFile(documentModal.url, documentModal.fileName)}
          variant="contained"
          startIcon={<DownloadIcon />}
          sx={{ mr: 1 }}
        >
          Download
        </Button>
        <Button
          onClick={() => window.open(documentModal.url, "_blank")}
          variant="outlined"
          startIcon={<OpenInNewIcon />}
          sx={{ mr: 1 }}
        >
          Open in New Tab
        </Button>
        <Button onClick={() => setDocumentModal({ open: false, url: "", title: "", fileName: "" })}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}
