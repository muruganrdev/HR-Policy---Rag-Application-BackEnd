import logging
import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.rag import ask_question
from app.router import route_question
from app.agent import run_agent
from app.short_term_memory import (
	ShortTermConversationMemory,
	resolve_employee_reference,
	resolve_self_reference,
)
from app.tools import DATABASE_PATH

router = APIRouter()
_logger = logging.getLogger(__name__)
_conversation_memory = ShortTermConversationMemory()
DEMO_MANAGER_NAMES = ("Arun Kumar", "Deepak Sharma")
ALLOWED_DEMO_ROLES = {"Super Admin", "Manager", "Employee"}


def is_demo_super_admin_enabled() -> bool:
	"""Check whether the explicit local demo Super Admin configuration is active.

	Defaults to True for local development/demo. When False, untrusted Super Admin
	requests fail closed until authenticated via a trusted principal.
	"""
	return os.getenv("ENABLE_DEMO_SUPER_ADMIN", "true").lower() in ("true", "1", "yes")


class QuestionRequest(BaseModel):
	question: str
	conversation_id: str | None = Field(default=None, min_length=1, max_length=128)
	role: str | None = Field(default=None, max_length=50)
	employee_id: str | None = Field(default=None, max_length=20)
	employee_name: str | None = Field(default=None, max_length=120)



class RoleAccessContext(BaseModel):
	role: str
	employee_id: str


class RoleAccessPrincipal(BaseModel):
	role: str
	employee_id: str


def get_authenticated_role_access_principal(request: Request) -> RoleAccessPrincipal | None:
	"""Read a principal installed by trusted authentication middleware, if present."""
	principal = getattr(request.state, "role_access_principal", None)
	if principal is None:
		return None
	return RoleAccessPrincipal.model_validate(principal)


class EmployeeCreateRequest(RoleAccessContext):
	employee_id: str = Field(min_length=1, max_length=20)
	employee_name: str = Field(min_length=1, max_length=120)
	email: str = Field(min_length=1, max_length=200)
	phone: str = Field(min_length=1, max_length=50)
	department: str = Field(min_length=1, max_length=120)
	designation: str = Field(min_length=1, max_length=120)
	employment_type: str = Field(min_length=1, max_length=40)
	employment_status: str = Field(min_length=1, max_length=40)
	date_of_joining: str = Field(min_length=1, max_length=30)
	tenure_years: float = Field(ge=0)
	manager_name: str = Field(min_length=1, max_length=120)
	location: str = Field(min_length=1, max_length=120)
	jurisdiction: str = Field(min_length=1, max_length=40)
	leave_balance: float = Field(ge=0)
	sick_leave_balance: float = Field(ge=0)
	annual_salary: float = Field(gt=0)
	work_mode: str = Field(min_length=1, max_length=40)


class EmployeeUpdateRequest(RoleAccessContext):
	employee_name: str | None = Field(default=None, min_length=1, max_length=120)
	email: str | None = Field(default=None, min_length=1, max_length=200)
	phone: str | None = Field(default=None, min_length=1, max_length=50)
	department: str | None = Field(default=None, min_length=1, max_length=120)
	designation: str | None = Field(default=None, min_length=1, max_length=120)
	employment_type: str | None = Field(default=None, min_length=1, max_length=40)
	employment_status: str | None = Field(default=None, min_length=1, max_length=40)
	date_of_joining: str | None = Field(default=None, min_length=1, max_length=30)
	tenure_years: float | None = Field(default=None, ge=0)
	manager_name: str | None = Field(default=None, min_length=1, max_length=120)
	location: str | None = Field(default=None, min_length=1, max_length=120)
	jurisdiction: str | None = Field(default=None, min_length=1, max_length=40)
	leave_balance: float | None = Field(default=None, ge=0)
	sick_leave_balance: float | None = Field(default=None, ge=0)
	annual_salary: float | None = Field(default=None, gt=0)
	work_mode: str | None = Field(default=None, min_length=1, max_length=40)


def _row_to_employee(row: sqlite3.Row) -> dict:
	return {
		"employee_id": row["employee_id"],
		"employee_name": row["employee_name"],
		"email": row["email"],
		"phone": row["phone"],
		"department": row["department"],
		"designation": row["designation"],
		"employment_type": row["employment_type"],
		"employment_status": row["employment_status"],
		"date_of_joining": row["date_of_joining"],
		"tenure_years": float(row["tenure_years"]),
		"manager_name": row["manager_name"],
		"location": row["location"],
		"jurisdiction": row["jurisdiction"],
		"leave_balance": float(row["leave_balance"]),
		"sick_leave_balance": float(row["sick_leave_balance"]),
		"annual_salary": float(row["annual_salary"]),
		"work_mode": row["work_mode"],
	}


def _employee_by_id(employee_id: str) -> dict | None:
	with sqlite3.connect(DATABASE_PATH) as connection:
		connection.row_factory = sqlite3.Row
		row = connection.execute(
			"SELECT * FROM employees WHERE employee_id = ?",
			(employee_id,),
		).fetchone()
	return _row_to_employee(row) if row else None


def _list_employees() -> list[dict]:
	with sqlite3.connect(DATABASE_PATH) as connection:
		connection.row_factory = sqlite3.Row
		rows = connection.execute(
			"SELECT * FROM employees ORDER BY employee_id"
		).fetchall()
	return [_row_to_employee(row) for row in rows]


def _list_demo_managers() -> list[dict[str, str]]:
	placeholders = ", ".join("?" for _ in DEMO_MANAGER_NAMES)
	with sqlite3.connect(DATABASE_PATH) as connection:
		rows = connection.execute(
			f"""
			SELECT manager_name, MIN(employee_id)
			FROM employees
			WHERE manager_name IN ({placeholders})
			GROUP BY manager_name
			""",
			DEMO_MANAGER_NAMES,
		).fetchall()
	identity_by_manager = {manager_name: employee_id for manager_name, employee_id in rows}
	return [
		{"manager_name": manager_name, "employee_id": identity_by_manager[manager_name]}
		for manager_name in DEMO_MANAGER_NAMES
		if manager_name in identity_by_manager
	]


def _resolve_role_access_identity(
	requested_role: str,
	requested_employee_id: str,
	principal: RoleAccessPrincipal | None,
) -> tuple[str, str]:
	if principal is not None:
		return principal.role.strip(), principal.employee_id

	role = requested_role.strip()
	if role == "Super Admin":
		raise HTTPException(
			status_code=403,
			detail="Super Admin access requires a trusted authenticated identity.",
		)
	if role not in {"Employee", "Manager"}:
		raise HTTPException(status_code=403, detail="Access denied: unsupported role.")
	return role, requested_employee_id


def _authorize_role_access(role: str, employee_id: str, *, operation: str, target_employee_id: str | None = None) -> None:
	"""Authorize a role-access request at one backend decision point.

	Employee and Manager role selection is demo-only. Super Admin is resolved
	from a principal installed by trusted server-side authentication middleware.
	"""
	normalized_role = role.strip()
	if normalized_role == "Super Admin":
		return
	if operation == "view" and normalized_role == "Manager":
		requesting_employee = _employee_by_id(employee_id)
		if requesting_employee is None:
			raise HTTPException(status_code=404, detail="Employee not found.")
		manager_name = requesting_employee["manager_name"]
		if manager_name not in DEMO_MANAGER_NAMES:
			raise HTTPException(status_code=403, detail="Access denied: unsupported demo manager.")
		if target_employee_id is not None:
			target_employee = _employee_by_id(target_employee_id)
			if target_employee is None:
				raise HTTPException(status_code=404, detail="Employee not found.")
			if target_employee["manager_name"] != manager_name:
				raise HTTPException(
					status_code=403,
					detail="Access denied: employee is outside your authorized team.",
				)
		return
	if operation == "view" and normalized_role == "Employee":
		if employee_id != target_employee_id:
			raise HTTPException(status_code=403, detail="Access denied: your selected role does not have permission to view this employee.")
		return
	if normalized_role in {"Manager", "Employee"}:
		raise HTTPException(status_code=403, detail="Access denied: your selected role does not have permission to perform this operation.")
	raise HTTPException(status_code=403, detail="Access denied: unsupported role.")


def _role_permissions(role: str) -> dict[str, bool]:
	"""Return the permission flags that the UI should display for a demo role."""
	normalized_role = role.strip()
	if normalized_role == "Super Admin":
		return {"view": True, "create": True, "update": True, "delete": True}
	if normalized_role == "Manager":
		return {"view": True, "create": False, "update": False, "delete": False}
	if normalized_role == "Employee":
		return {"view": True, "create": False, "update": False, "delete": False}
	raise HTTPException(status_code=403, detail="Access denied: unsupported role.")


def _extract_employee_error(error: Exception) -> str:
	return str(error).split("\n", maxsplit=1)[0]


def _extract_agent_sources(steps: list[dict]) -> list[dict]:
	"""Extract citations from policy search observations in agent steps."""
	sources = []
	seen = set()
	for step in steps:
		if step.get("tool") == "lookup_annual_leave_policy":
			obs = step.get("observation", {})
			res = obs.get("result", {})
			for item in res.get("results", []):
				src = item.get("source")
				chunk = item.get("chunk_index")
				if src and chunk is not None and (src, chunk) not in seen:
					seen.add((src, chunk))
					sources.append({"source": src, "chunk": chunk})
	return sources


def _validate_role_context(
	request: QuestionRequest,
	principal: RoleAccessPrincipal | None,
) -> dict[str, Any] | None:
	if request.role is None:
		return {
			"role": None,
			"employee_id": None,
			"employee_name": None,
			"is_trusted_principal": False,
			"is_legacy": True,
		}

	role = request.role.strip()
	if role not in ALLOWED_DEMO_ROLES:
		raise HTTPException(
			status_code=400,
			detail=f"Unsupported role '{role}'. Allowed roles: {', '.join(sorted(ALLOWED_DEMO_ROLES))}",
		)

	is_trusted_principal = (principal is not None and principal.role == "Super Admin")

	if role == "Super Admin":
		if not is_trusted_principal and is_demo_super_admin_enabled():
			is_trusted_principal = True
		emp_id = (request.employee_id or "001").strip()
		emp_name = (request.employee_name or "Administrator").strip()
		return {
			"role": "Super Admin",
			"employee_id": emp_id,
			"employee_name": emp_name,
			"is_trusted_principal": is_trusted_principal,
			"is_legacy": False,
		}

	if not request.employee_id or not request.employee_id.strip():
		raise HTTPException(
			status_code=400,
			detail=f"employee_id is required for role '{role}'.",
		)

	emp_id = request.employee_id.strip()
	emp_record = _employee_by_id(emp_id)
	if emp_record is None:
		raise HTTPException(
			status_code=404,
			detail=f"Employee '{emp_id}' not found.",
		)

	if role == "Employee":
		canonical_name = emp_record["employee_name"]
		if request.employee_name and request.employee_name.strip().casefold() != canonical_name.casefold():
			raise HTTPException(
				status_code=400,
				detail=f"Employee name '{request.employee_name}' does not match record for employee ID '{emp_id}'. Expected '{canonical_name}'.",
			)
		emp_name = canonical_name
	elif role == "Manager":
		canonical_manager = emp_record["manager_name"]
		if canonical_manager not in DEMO_MANAGER_NAMES:
			raise HTTPException(
				status_code=400,
				detail=f"Unsupported demo manager for employee ID '{emp_id}'. Allowed managers: {', '.join(sorted(DEMO_MANAGER_NAMES))}.",
			)
		if request.employee_name and request.employee_name.strip().casefold() != canonical_manager.casefold():
			raise HTTPException(
				status_code=400,
				detail=f"Manager identity mismatch for ID '{emp_id}'. Expected '{canonical_manager}'.",
			)
		emp_name = canonical_manager
	else:
		emp_name = emp_record["employee_name"]

	return {
		"role": role,
		"employee_id": emp_id,
		"employee_name": emp_name,
		"is_trusted_principal": False,
		"is_legacy": False,
	}


@router.post("/ask")
def ask(
	request: QuestionRequest,
	principal: RoleAccessPrincipal | None = Depends(get_authenticated_role_access_principal),
):
	"""Route HR policy questions to RAG or employee Agent handling with demo role context."""
	role_context = _validate_role_context(request, principal)
	conversation_id = (request.conversation_id or "").strip()
	role_val = role_context.get("role") if role_context else None
	emp_id_val = role_context.get("employee_id") if role_context else None
	history = (
		_conversation_memory.get_history(conversation_id, role=role_val, employee_id=emp_id_val)
		if conversation_id
		else []
	)
	resolved_question = resolve_employee_reference(request.question, history)
	if role_context and role_context.get("employee_name"):
		resolved_question = resolve_self_reference(resolved_question, role_context["employee_name"])

	selected_route = route_question(resolved_question)
	if conversation_id:
		_logger.info(
			"Short-term conversation context: conversation_id=%s history_turns=%d reference_resolved=%s role=%s",
			conversation_id,
			len(history) // 2,
			resolved_question != request.question,
			role_val,
		)

	if selected_route == "agent":
		if conversation_id:
			agent_res = run_agent(
				resolved_question,
				original_question=request.question,
				conversation_history=history,
				prefer_mcp_tools=True,
				role_context=role_context,
			)
		else:
			agent_res = run_agent(
				resolved_question,
				original_question=request.question,
				prefer_mcp_tools=True,
				role_context=role_context,
			)
		sources = _extract_agent_sources(agent_res.get("steps", []))
		response = {
			"question": request.question,
			"answer": agent_res["answer"],
			"sources": sources,
			"route": "agent",
		}
	else:
		response = ask_question(resolved_question, role_context=role_context)
		response["route"] = "rag"
		if conversation_id:
			response["question"] = request.question

	if conversation_id:
		_conversation_memory.add_exchange(
			conversation_id, request.question, response["answer"], role=role_val, employee_id=emp_id_val
		)
	return response



@router.get("/role-access/employees")
def list_role_access_employees(
	role: str = Query(..., min_length=1),
	employee_id: str = Query(..., min_length=1),
	principal: RoleAccessPrincipal | None = Depends(get_authenticated_role_access_principal),
):
	"""Return role-scoped employee records and permission flags for the UI."""
	role, employee_id = _resolve_role_access_identity(role, employee_id, principal)
	requesting_employee = _employee_by_id(employee_id)
	if requesting_employee is None:
		raise HTTPException(status_code=404, detail="Employee not found.")
	_authorize_role_access(role, employee_id, operation="view", target_employee_id=employee_id)
	if role == "Employee":
		employees = [requesting_employee]
		scope = "own demo identity"
	elif role == "Manager":
		with sqlite3.connect(DATABASE_PATH) as connection:
			connection.row_factory = sqlite3.Row
			rows = connection.execute(
				"SELECT * FROM employees WHERE manager_name = ? ORDER BY employee_id",
				(requesting_employee["manager_name"],),
			).fetchall()
		employees = [_row_to_employee(row) for row in rows]
		scope = "team / supported view"
	else:
		employees = _list_employees()
		scope = "all employees"
	return {
		"employees": employees,
		"employee_names": [employee["employee_name"] for employee in employees],
		"scope": scope,
		"permissions": _role_permissions(role),
	}


@router.get("/role-access/managers")
def list_role_access_demo_managers():
	"""Return the supported demo manager names and their representative identities."""
	return {"managers": _list_demo_managers()}


@router.get("/role-access/employee-options")
def list_role_access_demo_employee_options(
	role: str = Query(..., min_length=1),
	employee_id: str = Query(..., min_length=1),
	principal: RoleAccessPrincipal | None = Depends(get_authenticated_role_access_principal),
):
	"""Return minimal employee identity choices for the Employee demo selector."""
	role, employee_id = _resolve_role_access_identity(role, employee_id, principal)
	if role != "Employee":
		raise HTTPException(status_code=403, detail="Employee options are only available in the Employee demo role.")
	if _employee_by_id(employee_id) is None:
		raise HTTPException(status_code=404, detail="Employee not found.")
	with sqlite3.connect(DATABASE_PATH) as connection:
		rows = connection.execute(
			"SELECT employee_id, employee_name FROM employees ORDER BY employee_id"
		).fetchall()
	return {
		"employees": [
			{"employee_id": row[0], "employee_name": row[1]}
			for row in rows
		]
	}


@router.get("/role-access/employees/{employee_id}")
def get_role_access_employee(
	employee_id: str,
	role: str = Query(..., min_length=1),
	requesting_employee_id: str = Query(..., alias="employee_id", min_length=1),
	principal: RoleAccessPrincipal | None = Depends(get_authenticated_role_access_principal),
):
	"""Return one employee record when the selected role is allowed to view it."""
	role, requesting_employee_id = _resolve_role_access_identity(role, requesting_employee_id, principal)
	_authorize_role_access(role, requesting_employee_id, operation="view", target_employee_id=employee_id)
	employee = _employee_by_id(employee_id)
	if employee is None:
		raise HTTPException(status_code=404, detail="Employee not found.")
	return {"employee": employee, "scope": "all employees" if role == "Super Admin" else "team / supported view" if role == "Manager" else "own demo identity"}


@router.post("/role-access/employees", status_code=201)
def create_role_access_employee(
	request: EmployeeCreateRequest,
	principal: RoleAccessPrincipal | None = Depends(get_authenticated_role_access_principal),
):
	"""Create an employee record for the Super Admin demo role."""
	role, requesting_employee_id = _resolve_role_access_identity(request.role, request.employee_id, principal)
	_authorize_role_access(role, requesting_employee_id, operation="create")
	if _employee_by_id(request.employee_id) is not None:
		raise HTTPException(status_code=400, detail="Employee already exists.")
	fields = request.model_dump(exclude={"role", "employee_id"})
	with sqlite3.connect(DATABASE_PATH) as connection:
		try:
			connection.execute(
				"""
				INSERT INTO employees (
				    employee_id, employee_name, email, phone, department, designation,
				    employment_type, employment_status, date_of_joining, tenure_years,
				    manager_name, location, jurisdiction, leave_balance,
				    sick_leave_balance, annual_salary, work_mode
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					request.employee_id,
					fields["employee_name"],
					fields["email"],
					fields["phone"],
					fields["department"],
					fields["designation"],
					fields["employment_type"],
					fields["employment_status"],
					fields["date_of_joining"],
					fields["tenure_years"],
					fields["manager_name"],
					fields["location"],
					fields["jurisdiction"],
					fields["leave_balance"],
					fields["sick_leave_balance"],
					fields["annual_salary"],
					fields["work_mode"],
				),
			)
			connection.commit()
		except sqlite3.Error as error:
			raise HTTPException(status_code=400, detail=_extract_employee_error(error)) from error
	return {"employee": _employee_by_id(request.employee_id), "message": "Employee created successfully."}


@router.put("/role-access/employees/{employee_id}")
def update_role_access_employee(
	employee_id: str,
	request: EmployeeUpdateRequest,
	principal: RoleAccessPrincipal | None = Depends(get_authenticated_role_access_principal),
):
	"""Update an employee record for the Super Admin demo role."""
	role, requesting_employee_id = _resolve_role_access_identity(request.role, request.employee_id, principal)
	_authorize_role_access(role, requesting_employee_id, operation="update")
	existing = _employee_by_id(employee_id)
	if existing is None:
		raise HTTPException(status_code=404, detail="Employee not found.")
	updates = request.model_dump(exclude_unset=True, exclude={"role", "employee_id"})
	if not updates:
		raise HTTPException(status_code=400, detail="No employee fields were supplied.")
	fields = [f"{key} = ?" for key in updates]
	values = list(updates.values())
	values.append(employee_id)
	with sqlite3.connect(DATABASE_PATH) as connection:
		try:
			connection.execute(
				f"UPDATE employees SET {', '.join(fields)} WHERE employee_id = ?",
				values,
			)
			connection.commit()
		except sqlite3.Error as error:
			raise HTTPException(status_code=400, detail=_extract_employee_error(error)) from error
	return {"employee": _employee_by_id(employee_id), "message": "Employee updated successfully."}


@router.delete("/role-access/employees/{employee_id}")
def delete_role_access_employee(
	employee_id: str,
	request: RoleAccessContext,
	principal: RoleAccessPrincipal | None = Depends(get_authenticated_role_access_principal),
):
	"""Delete an employee record for the Super Admin demo role."""
	role, requesting_employee_id = _resolve_role_access_identity(request.role, request.employee_id, principal)
	_authorize_role_access(role, requesting_employee_id, operation="delete")
	if _employee_by_id(employee_id) is None:
		raise HTTPException(status_code=404, detail="Employee not found.")
	with sqlite3.connect(DATABASE_PATH) as connection:
		connection.execute("DELETE FROM employees WHERE employee_id = ?", (employee_id,))
		connection.commit()
	return {"deleted_employee_id": employee_id, "message": "Employee deleted successfully."}
