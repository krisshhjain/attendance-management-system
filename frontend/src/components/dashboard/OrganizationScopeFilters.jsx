import { useEffect } from "react";
import { Box, FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import { getOrganizationScope, useOrganizationScope } from "../../lib/organizationScope.jsx";

function uniqueValues(employees, field) {
  return [...new Set((employees || []).map((employee) => employee[field]).filter(Boolean))].sort();
}

export function OrganizationScopeFilters({ user, employees = [] }) {
  const { selectedScope, setSelectedScope } = useOrganizationScope();
  const scope = getOrganizationScope(user);
  const assignedBRs = Array.isArray(scope.assignedBRs) ? scope.assignedBRs : [];
  const availableEmployees = employees.filter((employee) => !selectedScope.brId || employee.br_id === selectedScope.brId || employee.brId === selectedScope.brId);
  const sections = uniqueValues(availableEmployees, "section");
  const subsections = uniqueValues(
    availableEmployees.filter((employee) => !selectedScope.sectionId || employee.section === selectedScope.sectionId),
    "subsection",
  );

  useEffect(() => {
    if (selectedScope.sectionId && !sections.includes(selectedScope.sectionId)) {
      setSelectedScope((current) => ({ ...current, sectionId: null, subsectionId: null }));
    } else if (selectedScope.subsectionId && !subsections.includes(selectedScope.subsectionId)) {
      setSelectedScope((current) => ({ ...current, subsectionId: null }));
    }
  }, [selectedScope.sectionId, selectedScope.subsectionId, sections, setSelectedScope, subsections]);

  function updateScope(field, value) {
    setSelectedScope((current) => ({
      brId: field === "brId" ? value || null : current.brId,
      sectionId: field === "brId" || field === "sectionId" ? (field === "sectionId" ? value || null : null) : current.sectionId,
      subsectionId: field === "subsectionId" ? value || null : field === "brId" || field === "sectionId" ? null : current.subsectionId,
    }));
  }

  return (
    <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
      <FormControl size="small" sx={{ minWidth: 170 }}>
        <InputLabel id="dashboard-br-filter-label">BR</InputLabel>
        <Select labelId="dashboard-br-filter-label" value={selectedScope.brId || ""} label="BR" onChange={(event) => updateScope("brId", event.target.value)}>
          <MenuItem value="">All Assigned BRs</MenuItem>
          {assignedBRs.map((br) => <MenuItem key={br.id} value={br.id}>{br.name}</MenuItem>)}
        </Select>
      </FormControl>
      <FormControl size="small" sx={{ minWidth: 170 }}>
        <InputLabel id="dashboard-section-filter-label">Section</InputLabel>
        <Select labelId="dashboard-section-filter-label" value={selectedScope.sectionId || ""} label="Section" onChange={(event) => updateScope("sectionId", event.target.value)}>
          <MenuItem value="">All Sections</MenuItem>
          {sections.map((section) => <MenuItem key={section} value={section}>{section}</MenuItem>)}
        </Select>
      </FormControl>
      <FormControl size="small" sx={{ minWidth: 190 }}>
        <InputLabel id="dashboard-subsection-filter-label">Subsection</InputLabel>
        <Select labelId="dashboard-subsection-filter-label" value={selectedScope.subsectionId || ""} label="Subsection" onChange={(event) => updateScope("subsectionId", event.target.value)}>
          <MenuItem value="">All Subsections</MenuItem>
          {subsections.map((subsection) => <MenuItem key={subsection} value={subsection}>{subsection}</MenuItem>)}
        </Select>
      </FormControl>
    </Box>
  );
}