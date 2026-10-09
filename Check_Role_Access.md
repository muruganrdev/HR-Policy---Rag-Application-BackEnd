# Check Role Access

## Validation Summary

| Role | Questions | Passed | Failed |
|---|---:|---:|---:|
| Super Admin | 2 | 2 | 0 |
| Manager | 2 | 2 | 0 |
| Employee | 1 | 1 | 0 |
| **Total** | **5** | **5** | **0** |

---

## Super Admin

### Question 1

**Question:** Can a Super Admin view all employee records?

**Role:** Super Admin

**API/Endpoint:** GET `/role-access/employees?role=Super%20Admin&employee_id=001`

**Request:**

```http
GET /role-access/employees?role=Super%20Admin&employee_id=001
```

**Expected:** The API returns all employees and the full permission set.

**Actual:** The API returned 6 records (`001` through `006`) with `scope: "all employees"` and permissions `{ "view": true, "create": true, "update": true, "delete": true }`.

**HTTP Status:** 200

**Result:** PASS

### Question 2

**Question:** Can a Super Admin create a new employee record?

**Role:** Super Admin

**API/Endpoint:** POST `/role-access/employees`

**Request:**

```json
{
  "role": "Super Admin",
  "employee_id": "001",
  "employee_id": "995",
  "employee_name": "Role Access Test Employee",
  "email": "role.access.test@acmecorp.in",
  "phone": "+91-90000-00995",
  "department": "Engineering",
  "designation": "Role Access Tester",
  "employment_type": "Full-Time",
  "employment_status": "Active",
  "date_of_joining": "2026-01-01",
  "tenure_years": 1.0,
  "manager_name": "Arun Kumar",
  "location": "Bangalore",
  "jurisdiction": "INDIA",
  "leave_balance": 10.0,
  "sick_leave_balance": 5.0,
  "annual_salary": 600000.0,
  "work_mode": "Hybrid"
}
```

**Expected:** The new employee record is created with HTTP 201.

**Actual:** The API returned HTTP 201 and the created employee with `employee_id: "995"`.

**HTTP Status:** 201

**Result:** PASS

---

## Manager

### Question 3

**Question:** Can a Manager view the employees in their permitted team?

**Role:** Manager

**API/Endpoint:** GET `/role-access/employees?role=Manager&employee_id=004`

**Request:**

```http
GET /role-access/employees?role=Manager&employee_id=004
```

**Expected:** The API returns only employees whose `manager_name` is `Arun Kumar`, and reports the Manager permissions as view-only.

**Actual:** The API returned 3 records (`003`, `004`, and the test employee `995`) with `manager_name: "Arun Kumar"`; `scope` was `"team / supported view"`; permissions were `{ "view": true, "create": false, "update": false, "delete": false }`.

**HTTP Status:** 200

**Result:** PASS

### Question 4

**Question:** Can a Manager create an employee record?

**Role:** Manager

**API/Endpoint:** POST `/role-access/employees`

**Request:**

```json
{
  "role": "Manager",
  "employee_id": "004",
  "employee_name": "Blocked Manager Employee",
  "email": "blocked.manager@acmecorp.in",
  "phone": "+91-90000-00996",
  "department": "Engineering",
  "designation": "Blocked Engineer",
  "employment_type": "Full-Time",
  "employment_status": "Active",
  "date_of_joining": "2026-01-01",
  "tenure_years": 1.0,
  "manager_name": "Arun Kumar",
  "location": "Bangalore",
  "jurisdiction": "INDIA",
  "leave_balance": 10.0,
  "sick_leave_balance": 5.0,
  "annual_salary": 600000.0,
  "work_mode": "Hybrid"
}
```

**Expected:** The API rejects the create operation with HTTP 403.

**Actual:** The API returned HTTP 403 with `detail: "Access denied: your selected role does not have permission to perform this operation."`

**HTTP Status:** 403

**Result:** PASS

---

## Employee

### Question 5

**Question:** Can an Employee view their own employee information and cannot access another employee's restricted information?

**Role:** Employee

**API/Endpoint:**

- GET `/role-access/employees?role=Employee&employee_id=001`
- GET `/role-access/employees/002?role=Employee&employee_id=001`

**Request:**

```http
GET /role-access/employees?role=Employee&employee_id=001
GET /role-access/employees/002?role=Employee&employee_id=001
```

**Expected:** The Employee can view only their own record, and the API must reject access to a different employee with HTTP 403.

**Actual:** The own-record request returned HTTP 200 with the `employee_id: "001"` record and `scope: "own demo identity"`. The different-employee request returned HTTP 403 with `detail: "Access denied: your selected role does not have permission to view this employee."`

**HTTP Status:** 200 / 403

**Result:** PASS

---

## Failure Investigation and Fixes

No failures were observed in the five new Role Access validation questions.
