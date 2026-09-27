from types import SimpleNamespace

from hr_copilot.services import employee_resolver as resolver_module


def resolver_with_ids(monkeypatch, ids):
    matches = SimpleNamespace(values_list=lambda *_args, **_kwargs: ids)
    manager = SimpleNamespace(filter=lambda *_args, **_kwargs: matches)
    monkeypatch.setattr(resolver_module.Employee, "objects", manager)
    return resolver_module.EmployeeResolver()


def test_resolver_returns_missing_without_identity():
    assert resolver_module.EmployeeResolver().resolve_employee().as_dict() == {
        "status": "missing", "employee_id": None,
    }


def test_resolver_resolves_email_to_actual_employee_id(monkeypatch):
    resolver = resolver_with_ids(monkeypatch, [12])
    assert resolver.resolve_employee(email="person@example.com").as_dict() == {
        "status": "resolved", "employee_id": 12,
    }


def test_resolver_marks_partial_name_matches_as_ambiguous(monkeypatch):
    resolver = resolver_with_ids(monkeypatch, [5, 8])
    assert resolver.resolve_employee(name="Akansha").as_dict() == {
        "status": "ambiguous", "employee_id": None,
    }


def test_resolver_reports_no_database_match(monkeypatch):
    resolver = resolver_with_ids(monkeypatch, [])
    assert resolver.resolve_employee(name="Missing Person").as_dict() == {
        "status": "not_found", "employee_id": None,
    }
