import { Alert } from "@mui/material";

export function ChatError({ message = "Something went wrong. Please try again." }) {
  return <Alert severity="error" sx={{ my: 2 }}>{message}</Alert>;
}
