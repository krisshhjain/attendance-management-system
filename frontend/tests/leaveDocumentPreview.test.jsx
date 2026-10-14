import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { LeaveDocumentPreviewDialog } from "../src/components/LeaveDocumentPreviewDialog.jsx";

function renderPreview(url) {
  const setDocumentModal = vi.fn();
  const notifyError = vi.fn();
  const documentModal = {
    open: true,
    url,
    title: "Leave supporting document",
    fileName: url.split("/").pop(),
  };
  render(
    <LeaveDocumentPreviewDialog
      setDocumentModal={setDocumentModal}
      notifyError={notifyError}
      documentModal={documentModal}
    />,
  );
  return { setDocumentModal, notifyError };
}

test("renders PDF previews and closes the shared dialog through its accessible action", async () => {
  const { setDocumentModal } = renderPreview("https://files.example.test/doctor-note.pdf");
  const frame = screen.getByTitle("PDF Preview");
  expect(frame).toHaveAttribute(
    "src",
    "https://files.example.test/doctor-note.pdf#toolbar=1&navpanes=1&scrollbar=1",
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Close document preview" }));
  expect(setDocumentModal).toHaveBeenCalledWith({ open: false, url: "", title: "", fileName: "" });
});

test("offers download and browser actions for unsupported files", async () => {
  const open = vi.spyOn(window, "open").mockImplementation(() => null);
  renderPreview("https://files.example.test/policy.docx");

  expect(screen.getByText("Preview not available for this file type")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download File" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download document" })).toBeInTheDocument();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Open document in new tab" }));
  expect(open).toHaveBeenCalledWith("https://files.example.test/policy.docx", "_blank");
});

test("downloads a leave attachment with its supplied filename", async () => {
  let clickedLink;
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function () {
    clickedLink = { href: this.href, download: this.download, connected: this.isConnected };
  });
  renderPreview("https://files.example.test/policy.docx");
  const user = userEvent.setup();

  await user.click(screen.getByRole("button", { name: "Download document" }));

  expect(click).toHaveBeenCalledOnce();
  expect(clickedLink).toEqual({
    href: "https://files.example.test/policy.docx",
    download: "policy.docx",
    connected: true,
  });
  expect(document.querySelector('a[download="policy.docx"]')).toBeNull();
});

test("shows a fallback when the image cannot load", () => {
  renderPreview("https://files.example.test/missing-image.png");
  const image = screen.getByRole("img", { name: "Document preview" });
  fireEvent.error(image);
  expect(image).toHaveStyle({ display: "none" });
  expect(image.nextElementSibling).toHaveStyle({ display: "flex" });
  expect(
    within(screen.getByRole("dialog")).getByText("Unable to preview this image"),
  ).toBeInTheDocument();
});

test("reports an unsupported fullscreen request with feedback", async () => {
  const { notifyError } = renderPreview("https://files.example.test/fullscreen.png");
  const preview = document.querySelector("[data-document-preview]");
  preview.requestFullscreen = vi.fn().mockRejectedValue(new Error("Fullscreen blocked"));
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Open document fullscreen" }));
  await waitFor(() =>
    expect(notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Fullscreen blocked" }),
      expect.objectContaining({ title: "Fullscreen unavailable" }),
    ),
  );
});
