import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { SystemAdminChatWidget } from "../src/components/SystemAdminChatWidget.jsx";

const state = vi.hoisted(() => ({ navigate: vi.fn(), messages: [] }));

vi.mock("@tanstack/react-router", () => ({ useNavigate: () => state.navigate }));
vi.mock("../src/lib/useOrganizationScope.js", () => ({
  useOrganizationScope: () => ({ selectedScope: { brId: 17, sectionId: 4, subsectionId: 2 } }),
}));
vi.mock("../src/components/hr-copilot/ChatMessage.jsx", () => ({
  ChatMessage: ({ message }) => {
    state.messages.push(message);
    return <div data-testid="chat-message">{message.content}</div>;
  },
}));

beforeEach(() => {
  state.navigate.mockClear();
  state.messages = [];
});

test("opens the preview, sends a scoped message, and minimizes and restores it", async () => {
  const user = userEvent.setup();
  render(<SystemAdminChatWidget />);

  await user.click(screen.getByRole("button", { name: "Open HR assistant" }));
  expect(screen.getByText(/Preview only/)).toBeInTheDocument();
  const composer = screen.getByPlaceholderText("Write a message");
  await user.type(composer, "  Show my team's leave balance  ");
  await user.click(screen.getByRole("button", { name: "Send message" }));

  expect(await screen.findByTestId("chat-message")).toHaveTextContent(
    "Show my team's leave balance",
  );
  expect(state.messages.at(-1)).toMatchObject({
    role: "user",
    content: "Show my team's leave balance",
    scope: { brId: 17, sectionId: 4, subsectionId: 2 },
  });
  expect(screen.getByPlaceholderText("Write a message")).toHaveValue("");

  await user.click(screen.getByRole("button", { name: "Minimize assistant" }));
  expect(screen.queryByText("HR Assistant")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Restore HR assistant" }));
  expect(screen.getByText("Show my team's leave balance")).toBeInTheDocument();
});

test("opens the full copilot route and closes the preview", async () => {
  const user = userEvent.setup();
  render(<SystemAdminChatWidget />);
  await user.click(screen.getByRole("button", { name: "Open HR assistant" }));
  await user.click(screen.getByText("Open HR Copilot"));

  expect(state.navigate).toHaveBeenCalledWith({ to: "/hr-copilot" });
  expect(screen.queryByText("HR Assistant")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Open HR assistant" }));
  await user.click(screen.getByRole("button", { name: "Close assistant" }));
  expect(screen.queryByText("Preview only")).not.toBeInTheDocument();
});
