import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { OrganizationScopeFilters } from "../src/components/dashboard/OrganizationScopeFilters.jsx";
import { OrganizationScopeProvider, useOrganizationScope } from "../src/lib/organizationScope.jsx";

function ScopeDisplay() {
  const { selectedScope } = useOrganizationScope();
  return <output>{JSON.stringify(selectedScope)}</output>;
}

function renderFilters() {
  return render(
    <OrganizationScopeProvider>
      <OrganizationScopeFilters
        user={{
          organizational_scope: {
            assignedBRs: [
              { id: 2, name: "BR 2" },
              { id: 10, name: "BR 10" },
            ],
          },
        }}
        employees={[
          { br_id: 2, section: "People", subsection: "Hiring" },
          { br_id: 2, section: "People", subsection: "Payroll" },
          { br_id: 10, section: "Engineering", subsection: "Platform" },
        ]}
      />
      <ScopeDisplay />
    </OrganizationScopeProvider>,
  );
}

test("filters dependent organization choices and clears stale subsections", async () => {
  const user = userEvent.setup();
  renderFilters();

  await user.click(screen.getByRole("combobox", { name: "BR" }));
  await user.click(screen.getByRole("option", { name: "BR 2" }));
  await waitFor(() =>
    expect(screen.getByRole("combobox", { name: "BR" })).toHaveTextContent("BR 2"),
  );
  await user.click(screen.getByRole("combobox", { name: "Section" }));
  expect(screen.getByRole("option", { name: "People" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Engineering" })).not.toBeInTheDocument();
  await user.keyboard("{Escape}");

  await user.click(screen.getByRole("combobox", { name: "Section" }));
  await user.click(screen.getByRole("option", { name: "People" }));
  await user.click(screen.getByRole("combobox", { name: "Subsection" }));
  await user.click(screen.getByRole("option", { name: "Hiring" }));
  expect(
    screen.getByText('{"brId":2,"sectionId":"People","subsectionId":"Hiring"}'),
  ).toBeInTheDocument();

  await user.click(screen.getByRole("combobox", { name: "Section" }));
  await user.click(screen.getByRole("option", { name: "All Sections" }));
  expect(screen.getByText('{"brId":2,"sectionId":null,"subsectionId":null}')).toBeInTheDocument();
});

test("uses the user's assigned organization hierarchy and handles users without assignments", () => {
  const { rerender } = render(
    <OrganizationScopeProvider>
      <OrganizationScopeFilters user={{ scope: { assignedBRs: [{ id: 7, name: "BR 7" }] } }} />
    </OrganizationScopeProvider>,
  );
  expect(screen.getByRole("combobox", { name: "BR" })).toBeInTheDocument();
  rerender(
    <OrganizationScopeProvider>
      <OrganizationScopeFilters user={{ organizational_scope: { assignedBRs: "invalid" } }} />
    </OrganizationScopeProvider>,
  );
  expect(screen.getByRole("combobox", { name: "Section" })).toBeInTheDocument();
});
