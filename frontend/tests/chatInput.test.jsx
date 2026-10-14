import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, test, vi } from "vitest";
import { ChatInput } from "../src/components/hr-copilot/ChatInput.jsx";

function Harness({ onSend, disabled = false, initialValue = "" }) {
  const [value, setValue] = useState(initialValue);
  return <ChatInput value={value} onChange={setValue} onSend={onSend} disabled={disabled} />;
}

function renderInput(props = {}) {
  const onSend = props.onSend || vi.fn();
  const view = render(<Harness {...props} onSend={onSend} />);
  return { ...view, onSend };
}

test("trims and sends a text question with Enter or the send control", async () => {
  const user = userEvent.setup();
  const { onSend } = renderInput();
  const input = screen.getByPlaceholderText("Ask HR Copilot something...");
  await user.type(input, "  Who is on leave?  ");
  await user.keyboard("{Enter}");
  expect(onSend).toHaveBeenCalledWith("Who is on leave?", []);
});

test("accepts supported attachments, filters unsupported files, and removes a selected file", async () => {
  const user = userEvent.setup({ applyAccept: false });
  const { onSend } = renderInput();
  const input = document.querySelector('input[type="file"]');
  await user.upload(input, [
    new File(["report"], "report.csv", { type: "text/csv" }),
    new File(["bad"], "payload.exe", { type: "application/octet-stream" }),
  ]);

  expect(screen.getByText("report.csv")).toBeInTheDocument();
  expect(screen.queryByText("payload.exe")).not.toBeInTheDocument();
  expect(screen.getByText("6 B")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Remove report.csv" }));
  expect(screen.queryByText("report.csv")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  expect(onSend).not.toHaveBeenCalled();
});

test("sends text and attachment metadata together and respects the disabled state", async () => {
  const user = userEvent.setup();
  const { onSend } = renderInput({ initialValue: "Summarize this" });
  await user.upload(
    document.querySelector('input[type="file"]'),
    new File(["notes"], "notes.pdf", { type: "application/pdf" }),
  );
  await user.click(screen.getByRole("button", { name: "Send message" }));

  expect(onSend).toHaveBeenCalledWith("Summarize this", [
    expect.objectContaining({
      name: "notes.pdf",
      type: "application/pdf",
      size: 5,
      file: expect.any(File),
    }),
  ]);
});

test("supports dropping an attachment and revokes an image preview when it is removed", async () => {
  const user = userEvent.setup();
  const createObjectURL = vi.fn(() => "blob:preview");
  const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
  const { onSend, unmount } = renderInput();
  const image = new File(["pixels"], "team.png", { type: "image/png" });
  const form = screen.getByPlaceholderText("Ask HR Copilot something...").closest("form");

  fireEvent.drop(form, { dataTransfer: { files: [image] } });
  await screen.findByText("team.png");
  expect(document.querySelector("img")).toHaveAttribute("src", "blob:preview");
  expect(createObjectURL).toHaveBeenCalledWith(image);
  await user.click(screen.getByRole("button", { name: "Remove team.png" }));
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:preview");
  expect(onSend).not.toHaveBeenCalled();
  unmount();
  vi.unstubAllGlobals();
});

test("keeps Shift+Enter in the question and ignores Enter during IME composition", async () => {
  const user = userEvent.setup();
  const { onSend } = renderInput();
  const input = screen.getByPlaceholderText("Ask HR Copilot something...");
  await user.type(input, "first");
  await user.keyboard("{Shift>}{Enter}{/Shift}");
  expect(onSend).not.toHaveBeenCalled();

  fireEvent.keyDown(input, { key: "Enter", isComposing: true });
  expect(onSend).not.toHaveBeenCalled();
});

test("does not submit a blank message or allow input while disabled", async () => {
  const { onSend, rerender } = renderInput({ initialValue: "   " });
  const button = screen.getByRole("button", { name: "Send message" });
  expect(button).toBeDisabled();
  fireEvent.submit(button.closest("form"));
  expect(onSend).not.toHaveBeenCalled();

  rerender(<Harness onSend={onSend} disabled initialValue="question" />);
  expect(screen.getByPlaceholderText("Ask HR Copilot something...")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Attach files" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
});
