# Admin Access Verification: Employee and Manager

## Initial Findings (Before Fixes)

The Role Access API returns HTTP `403` for Employee and Manager create, update, and delete requests. The denial happens in backend authorization before database writes; probes against an isolated SQLite backup showed the affected records unchanged.

Read authorization is not consistently enforced:

- Employee list access returns only the Employee's own record, but also returns `employee_names` for all six employees (`200`), exposing names outside the Employee's scope.
- Manager list access returns only two records assigned to Arun Kumar, but also returns all six employee names (`200`).
- A Manager can retrieve a full record outside their team through the single-employee endpoint (`200`); this endpoint does not check team membership.

The role is supplied as a plain request query/body value. `app/api.py` explicitly describes it as a frontend demo role and says it must not be trusted in production. Therefore, the API enforces restrictions for requests that submit `Employee` or `Manager`, but does not authenticate the role claim. The Super Admin results below verify behavior for the submitted `Super Admin` claim, not a separately authenticated Super Admin identity.

## Scope and Method

Inspected the routes, Pydantic request models, `_authorize_role_access`, `_role_permissions`, role-scoped list implementation, existing tests, and [Check_Role_Access.md](Check_Role_Access.md). Both the baseline probes and post-fix retests used the existing FastAPI app through `TestClient` with a temporary SQLite backup for requests that could mutate records. Employee identity discovery and the final relationship check used a read-only connection to the repository database. The test-only Super Admin principal is described in the retest section.

Existing identities used: Employee `001` (Asha Rao), baseline Manager request identity `004` (on Arun Kumar's team), and outside-team target `005` (on Deepak Sharma's team). The current dropdown representatives are `003` for Arun Kumar and `005` for Deepak Sharma. The current role-access tests use isolated database copies. Existing employee records and `Check_Role_Access.md` were not changed; the implementation, role-access tests, and this report were updated for the retest.

## Results

| Role | Operation | HTTP Status | Actual BE Response | Expected Access | Result |
|---|---|---:|---|---|---|
| Employee (`001`) | `GET /role-access/employees?role=Employee&employee_id=001` (list/all employees) | 200 | [E1](#e1-employee-list) | Own record only; no directory-wide name disclosure | Partial scope enforced, but all employee names leak |
| Employee (`001`) | `POST /role-access/employees` | 403 | [D1](#d1-denied-write) | Deny | Correctly denied; no mutation |
| Employee (`001`) | `PUT /role-access/employees/002` | 403 | [D1](#d1-denied-write) | Deny | Correctly denied; target unchanged |
| Employee (`001`) | `DELETE /role-access/employees/002` | 403 | [D1](#d1-denied-write) | Deny | Correctly denied; target unchanged |
| Manager (`004`) | `GET /role-access/employees?role=Manager&employee_id=004` (list employees) | 200 | [M1](#m1-manager-team-list) | Team records only; no directory-wide name disclosure | Team records scoped, but all employee names leak |
| Manager (`004`) | `POST /role-access/employees` | 403 | [D1](#d1-denied-write) | Deny | Correctly denied; no mutation |
| Manager (`004`) | `PUT /role-access/employees/005` | 403 | [D1](#d1-denied-write) | Deny | Correctly denied; target unchanged |
| Manager (`004`) | `DELETE /role-access/employees/005` | 403 | [D1](#d1-denied-write) | Deny | Correctly denied; target unchanged |
| Manager (`004`) | `GET /role-access/employees/005?role=Manager&employee_id=004` (outside-team record) | 200 | [M2](#m2-manager-outside-team) | Deny access outside Arun Kumar's team | **Authorization failure:** full outside-team record returned |
| `Super Admin` role claim (`001`) | `GET /role-access/employees?role=Super%20Admin&employee_id=001` | 200 | [A1](#a1-super-admin-list-control) | Allow all employee records | Allowed for submitted role claim |
| `Super Admin` role claim (create payload uses `employee_id=ZZV001`) | `POST /role-access/employees` | 201 | [A2](#a2-super-admin-create-control) | Allow | Allowed; synthetic record created in temporary DB |
| `Super Admin` role claim (`001`) | `PUT /role-access/employees/ZZV001` | 200 | [A3](#a3-super-admin-update-control) | Allow | Allowed; synthetic record updated in temporary DB |
| `Super Admin` role claim (`001`) | `DELETE /role-access/employees/ZZV001` | 200 | [A4](#a4-super-admin-delete-control) | Allow | Allowed; synthetic record deleted from temporary DB |

### Request Payloads for Mutations

Create uses `EmployeeCreateRequest`. Its schema has one `employee_id` field, which is used as the submitted identity for authorization and as the ID to insert. The denied Employee and Manager requests used these exact bodies:

```json
{
  "role": "Employee",
  "employee_id": "001",
  "employee_name": "Authorization Probe",
  "email": "authorization.probe@example.invalid",
  "phone": "0000000000",
  "department": "Test",
  "designation": "Test",
  "employment_type": "Full-Time",
  "employment_status": "Active",
  "date_of_joining": "2026-10-09",
  "tenure_years": 0,
  "manager_name": "Arun Kumar",
  "location": "Test",
  "jurisdiction": "INDIA",
  "leave_balance": 0,
  "sick_leave_balance": 0,
  "annual_salary": 1,
  "work_mode": "Remote"
}
```

The Manager create request was identical except `"role": "Manager"` and `"employee_id": "004"`.

The Employee and Manager update requests were respectively `PUT /role-access/employees/002` with `{"role":"Employee","employee_id":"001","employee_name":"Unauthorized Mutation Probe"}` and `PUT /role-access/employees/005` with `{"role":"Manager","employee_id":"004","employee_name":"Unauthorized Mutation Probe"}`.

The Employee and Manager delete requests were respectively `DELETE /role-access/employees/002` with `{"role":"Employee","employee_id":"001"}` and `DELETE /role-access/employees/005` with `{"role":"Manager","employee_id":"004"}`.

The Super Admin create control used `POST /role-access/employees` with this body; the target was synthetic `ZZV001`:

```json
{
  "role": "Super Admin",
  "employee_id": "ZZV001",
  "employee_name": "Authorization Probe",
  "email": "authorization.probe@example.invalid",
  "phone": "0000000000",
  "department": "Test",
  "designation": "Test",
  "employment_type": "Full-Time",
  "employment_status": "Active",
  "date_of_joining": "2026-10-09",
  "tenure_years": 0,
  "manager_name": "Arun Kumar",
  "location": "Test",
  "jurisdiction": "INDIA",
  "leave_balance": 0,
  "sick_leave_balance": 0,
  "annual_salary": 1,
  "work_mode": "Remote"
}
```

The Super Admin update request was `PUT /role-access/employees/ZZV001` with `{"role":"Super Admin","employee_id":"001","employee_name":"Updated Authorization Probe"}`. The delete request was `DELETE /role-access/employees/ZZV001` with `{"role":"Super Admin","employee_id":"001"}`.

## Exact Backend Response Bodies

### E1: Employee List

Request: `GET /role-access/employees?role=Employee&employee_id=001`

```json
{
  "employees": [
    {
      "employee_id": "001",
      "employee_name": "Asha Rao",
      "email": "asha.rao@acmecorp.in",
      "phone": "+91-98450-11001",
      "department": "Human Resources",
      "designation": "HR Executive",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2023-10-01",
      "tenure_years": 0.25,
      "manager_name": "Sunita Pillai",
      "location": "Bangalore",
      "jurisdiction": "INDIA",
      "leave_balance": 2.0,
      "sick_leave_balance": 10.0,
      "annual_salary": 480000.0,
      "work_mode": "On-Site"
    }
  ],
  "employee_names": [
    "Asha Rao",
    "Vikram Shah",
    "Neha Iyer",
    "Arjun Menon",
    "Priya Nair",
    "Rahul Das"
  ],
  "scope": "own demo identity",
  "permissions": {
    "view": true,
    "create": false,
    "update": false,
    "delete": false
  }
}
```

### D1: Denied Write

Exact response body for each Employee and Manager create, update, and delete request:

```json
{"detail":"Access denied: your selected role does not have permission to perform this operation."}
```

Database check on the isolated copy: Employee and Manager update/delete targets were unchanged. The create requests were rejected before any insert; no write occurred.

### M1: Manager Team List

Request: `GET /role-access/employees?role=Manager&employee_id=004`

```json
{
  "employees": [
    {
      "employee_id": "003",
      "employee_name": "Neha Iyer",
      "email": "neha.iyer@acmecorp.in",
      "phone": "+91-98701-33003",
      "department": "Engineering",
      "designation": "Software Engineer",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2022-04-01",
      "tenure_years": 1.5,
      "manager_name": "Arun Kumar",
      "location": "Hyderabad",
      "jurisdiction": "INDIA",
      "leave_balance": 10.0,
      "sick_leave_balance": 12.0,
      "annual_salary": 840000.0,
      "work_mode": "Hybrid"
    },
    {
      "employee_id": "004",
      "employee_name": "Arjun Menon",
      "email": "arjun.menon@acmecorp.in",
      "phone": "+91-97890-44004",
      "department": "Engineering",
      "designation": "Senior Software Engineer",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2021-01-01",
      "tenure_years": 3.0,
      "manager_name": "Arun Kumar",
      "location": "Bangalore",
      "jurisdiction": "INDIA",
      "leave_balance": 12.0,
      "sick_leave_balance": 12.0,
      "annual_salary": 1200000.0,
      "work_mode": "Hybrid"
    }
  ],
  "employee_names": [
    "Asha Rao",
    "Vikram Shah",
    "Neha Iyer",
    "Arjun Menon",
    "Priya Nair",
    "Rahul Das"
  ],
  "scope": "team / supported view",
  "permissions": {
    "view": true,
    "create": false,
    "update": false,
    "delete": false
  }
}
```

### M2: Manager Outside-Team Record

Request: `GET /role-access/employees/005?role=Manager&employee_id=004`

```json
{
  "employee": {
    "employee_id": "005",
    "employee_name": "Priya Nair",
    "email": "priya.nair@acmecorp.in",
    "phone": "+91-96780-55005",
    "department": "Product",
    "designation": "Product Manager",
    "employment_type": "Full-Time",
    "employment_status": "Active",
    "date_of_joining": "2017-04-01",
    "tenure_years": 6.5,
    "manager_name": "Deepak Sharma",
    "location": "Bangalore",
    "jurisdiction": "INDIA",
    "leave_balance": 20.0,
    "sick_leave_balance": 12.0,
    "annual_salary": 1800000.0,
    "work_mode": "Remote"
  },
  "scope": "team / supported view"
}
```

### A1: Super Admin List Control

Request: `GET /role-access/employees?role=Super%20Admin&employee_id=001`

```json
{
  "employees": [
    {
      "employee_id": "001",
      "employee_name": "Asha Rao",
      "email": "asha.rao@acmecorp.in",
      "phone": "+91-98450-11001",
      "department": "Human Resources",
      "designation": "HR Executive",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2023-10-01",
      "tenure_years": 0.25,
      "manager_name": "Sunita Pillai",
      "location": "Bangalore",
      "jurisdiction": "INDIA",
      "leave_balance": 2.0,
      "sick_leave_balance": 10.0,
      "annual_salary": 480000.0,
      "work_mode": "On-Site"
    },
    {
      "employee_id": "002",
      "employee_name": "Vikram Shah",
      "email": "vikram.shah@acmecorp.in",
      "phone": "+91-99300-22002",
      "department": "Finance",
      "designation": "Finance Analyst",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2023-07-01",
      "tenure_years": 0.5,
      "manager_name": "Ramesh Gupta",
      "location": "Mumbai",
      "jurisdiction": "INDIA",
      "leave_balance": 4.0,
      "sick_leave_balance": 12.0,
      "annual_salary": 600000.0,
      "work_mode": "Hybrid"
    },
    {
      "employee_id": "003",
      "employee_name": "Neha Iyer",
      "email": "neha.iyer@acmecorp.in",
      "phone": "+91-98701-33003",
      "department": "Engineering",
      "designation": "Software Engineer",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2022-04-01",
      "tenure_years": 1.5,
      "manager_name": "Arun Kumar",
      "location": "Hyderabad",
      "jurisdiction": "INDIA",
      "leave_balance": 10.0,
      "sick_leave_balance": 12.0,
      "annual_salary": 840000.0,
      "work_mode": "Hybrid"
    },
    {
      "employee_id": "004",
      "employee_name": "Arjun Menon",
      "email": "arjun.menon@acmecorp.in",
      "phone": "+91-97890-44004",
      "department": "Engineering",
      "designation": "Senior Software Engineer",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2021-01-01",
      "tenure_years": 3.0,
      "manager_name": "Arun Kumar",
      "location": "Bangalore",
      "jurisdiction": "INDIA",
      "leave_balance": 12.0,
      "sick_leave_balance": 12.0,
      "annual_salary": 1200000.0,
      "work_mode": "Hybrid"
    },
    {
      "employee_id": "005",
      "employee_name": "Priya Nair",
      "email": "priya.nair@acmecorp.in",
      "phone": "+91-96780-55005",
      "department": "Product",
      "designation": "Product Manager",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2017-04-01",
      "tenure_years": 6.5,
      "manager_name": "Deepak Sharma",
      "location": "Bangalore",
      "jurisdiction": "INDIA",
      "leave_balance": 20.0,
      "sick_leave_balance": 12.0,
      "annual_salary": 1800000.0,
      "work_mode": "Remote"
    },
    {
      "employee_id": "006",
      "employee_name": "Rahul Das",
      "email": "rahul.das@acmecorp.in",
      "phone": "+91-95670-66006",
      "department": "Sales",
      "designation": "Sales Lead",
      "employment_type": "Full-Time",
      "employment_status": "Active",
      "date_of_joining": "2015-10-01",
      "tenure_years": 8.0,
      "manager_name": "Preethi Nanda",
      "location": "Chennai",
      "jurisdiction": "INDIA",
      "leave_balance": 5.0,
      "sick_leave_balance": 8.0,
      "annual_salary": 1440000.0,
      "work_mode": "On-Site"
    }
  ],
  "employee_names": [
    "Asha Rao",
    "Vikram Shah",
    "Neha Iyer",
    "Arjun Menon",
    "Priya Nair",
    "Rahul Das"
  ],
  "scope": "all employees",
  "permissions": {
    "view": true,
    "create": true,
    "update": true,
    "delete": true
  }
}
```

### A2: Super Admin Create Control

```json
{"employee":{"employee_id":"ZZV001","employee_name":"Authorization Probe","email":"authorization.probe@example.invalid","phone":"0000000000","department":"Test","designation":"Test","employment_type":"Full-Time","employment_status":"Active","date_of_joining":"2026-10-09","tenure_years":0.0,"manager_name":"Arun Kumar","location":"Test","jurisdiction":"INDIA","leave_balance":0.0,"sick_leave_balance":0.0,"annual_salary":1.0,"work_mode":"Remote"},"message":"Employee created successfully."}
```

### A3: Super Admin Update Control

```json
{"employee":{"employee_id":"ZZV001","employee_name":"Updated Authorization Probe","email":"authorization.probe@example.invalid","phone":"0000000000","department":"Test","designation":"Test","employment_type":"Full-Time","employment_status":"Active","date_of_joining":"2026-10-09","tenure_years":0.0,"manager_name":"Arun Kumar","location":"Test","jurisdiction":"INDIA","leave_balance":0.0,"sick_leave_balance":0.0,"annual_salary":1.0,"work_mode":"Remote"},"message":"Employee updated successfully."}
```

### A4: Super Admin Delete Control

```json
{"deleted_employee_id":"ZZV001","message":"Employee deleted successfully."}
```

## Backend Enforcement Assessment

- The create, update, and delete routes call `_authorize_role_access` before their database mutation code. For submitted Employee and Manager roles, actual requests returned `403`; the isolated database checks showed no target changes.
- The API returns `403 Forbidden` rather than `401 Unauthorized` for these denied role operations. It has no authenticated principal or credential check in these routes.
- The list endpoint scopes Employee records and Manager team records, but its `employee_names` field is populated from the entire employees table for both roles.
- The single-employee GET authorizes every Manager for `view` without checking the target's `manager_name`; the observed request returned employee `005`'s full data to Manager `004`.
- Since callers supply `role`, a client can submit `Super Admin`; the code's comment explicitly warns this value must come from a trusted authenticated identity in production. Thus, the 403 results demonstrate backend enforcement against the submitted role value, not a secure authorization boundary against role spoofing.

**Initial conclusion:** Backend checks rejected create/update/delete when the request said Employee or Manager, but employee-name metadata leaked across scopes, the Manager detail route returned outside-team records, and the role claim was not authenticated.

## Retest After Fixes (2026-10-09)

All fresh HTTP requests below used the existing FastAPI routes with a temporary SQLite backup. The repository database was not used for writes.

| Check | Retest result |
|---|---|
| Manager options endpoint | `GET /role-access/managers` returned HTTP `200` with exactly `{"managers":[{"manager_name":"Arun Kumar","employee_id":"003"},{"manager_name":"Deepak Sharma","employee_id":"005"}]}`. Options are sourced from the backend's single `DEMO_MANAGER_NAMES` allowlist and the existing employee rows; the frontend does not maintain a second manager list. |
| Arun Kumar team | `GET /role-access/employees?role=Manager&employee_id=003` returned HTTP `200`, employees `003` Neha Iyer and `004` Arjun Menon, and `employee_names: ["Neha Iyer","Arjun Menon"]`. |
| Deepak Sharma team | `GET /role-access/employees?role=Manager&employee_id=005` returned HTTP `200`, employee `005` Priya Nair, and `employee_names: ["Priya Nair"]`. |
| Employee name scope | `GET /role-access/employees?role=Employee&employee_id=001` returned HTTP `200` and `employee_names: ["Asha Rao"]`; other employee names are no longer included. |
| Employee demo selector directory | `GET /role-access/employee-options?role=Employee&employee_id=001` returns only employee IDs and display names for the demo identity selector. This is an explicit demo directory, not an authorization grant; the selected identity's record remains scoped by `/role-access/employees`, and direct cross-employee detail reads remain `403`. |
| Manager permitted detail | `GET /role-access/employees/004?role=Manager&employee_id=003` returned HTTP `200` with Arjun Menon's record. |
| Manager outside-team detail | `GET /role-access/employees/005?role=Manager&employee_id=003` returned HTTP `403` and `{"detail":"Access denied: employee is outside your authorized team."}`. |
| Employee outside detail | `GET /role-access/employees/002?role=Employee&employee_id=001` returned HTTP `403` and `{"detail":"Access denied: your selected role does not have permission to view this employee."}`. |
| Employee/Manager mutation attempts | Employee create and Manager update/delete returned HTTP `403` and `{"detail":"Access denied: your selected role does not have permission to perform this operation."}`. Focused tests also verified Employee and Manager create/update/delete denials and no database mutation. |
| Super Admin client role claim | `GET /role-access/employees?role=Super%20Admin&employee_id=001` returned HTTP `403` and `{"detail":"Super Admin access requires a trusted authenticated identity."}`. Submitting the role no longer elevates access. |
| Trusted-principal Super Admin control | A test-only server-side dependency override supplying a trusted `Super Admin` principal returned HTTP `200` for the all-employee list with all six records and full permission flags. This verifies the authorization integration point; it is not a live authentication system. |

### Identity and Database Notes

The database has no employee records whose `employee_name` is Arun Kumar or Deepak Sharma. Manager dropdown options therefore use an existing employee ID as a demo team anchor: `003` is the first existing employee reporting to Arun Kumar, and `005` is the first existing employee reporting to Deepak Sharma. The selected manager name is displayed; the anchor is passed to the existing role-access API, which checks the actual `manager_name` relationship before returning records. Rahul Das (`006`) still reports to Preethi Nanda, unchanged; that relationship is retained, but Preethi is not a selectable demo manager. No employee was deleted, re-created, or reassigned.

### Retest Results

- Backend focused suite: `22 passed` (`tests/test_role_access.py`), including scoped employee names, the two manager options, each manager team, inside/outside team detail access, Employee own-record access, mutation denials, Super Admin role-claim rejection, and Super Admin access when a trusted principal is injected by the test.
- Frontend focused suite: `8 passed` for `week9-role-demo.component.spec.ts`, including Employee selection, exactly two backend-provided Manager options, team loading for Arun and Deepak, role-switch reset, empty/error states, and fail-closed Super Admin selection.
- Full frontend suite: `21 passed, 1 failed`. The failure is `architecture-view.component.spec.ts`: it expects 6 pipeline steps while the existing component has 9. It is outside the changed Role Access feature. Angular bundle generation succeeded.
- Full backend suite: `272 passed, 4 failed`. Failures were outside Role Access: one MCP gateway subprocess closed stdout unexpectedly; two query-rewriting checks failed when local Ollama exited because it could not allocate a 3.9 GB CPU buffer; the related misspelled-query check then returned an incomplete answer. The focused Role Access suite passed independently.

### Remaining Authentication Limitation

No authentication middleware, token validation, or trusted principal provider is currently installed in the backend. `get_authenticated_role_access_principal` only reads a principal placed on request state by future trusted server-side middleware; without one, Super Admin requests fail closed. Employee and Manager selectors remain demo-only and still accept client-supplied role/employee values for this demonstration. Those values must not be treated as production identity. Until trusted authentication is integrated, the frontend correctly keeps Super Admin operations unavailable; a real Super Admin cannot sign in through the current application.

**Retest conclusion:** Employee name leakage and Manager outside-team detail access are fixed and covered by focused passing tests. Employee/Manager writes remain denied before mutation. Super Admin cannot be obtained by submitting `role=Super Admin`; privileged access is available only when a trusted principal is injected server-side. The unrelated full-suite failures above remain unresolved and are reported rather than hidden.