-- DB-01: reflected current PostgreSQL DDL, not a migration or a backup.

-- Includes schema only; no account credentials or HR records.

CREATE TABLE branches (
	id SERIAL NOT NULL,
	name VARCHAR(100) NOT NULL,
	seed_key VARCHAR(32),
	CONSTRAINT branches_pkey PRIMARY KEY (id),
	CONSTRAINT branches_name_key UNIQUE NULLS DISTINCT (name),
	CONSTRAINT branches_seed_key_key UNIQUE NULLS DISTINCT (seed_key)
);

CREATE TABLE payroll_rules (
	id SERIAL NOT NULL,
	contract_type VARCHAR(30) NOT NULL,
	calculation_mode VARCHAR(20) NOT NULL,
	monthly_hours NUMERIC(10, 2) NOT NULL,
	overtime_factor NUMERIC(6, 2) NOT NULL,
	insurance_percent NUMERIC(6, 2) NOT NULL,
	tax_percent NUMERIC(6, 2) NOT NULL,
	notes TEXT NOT NULL,
	CONSTRAINT payroll_rules_pkey PRIMARY KEY (id),
	CONSTRAINT payroll_rules_contract_type_key UNIQUE NULLS DISTINCT (contract_type),
	CONSTRAINT payroll_rules_check CHECK (monthly_hours > 0::numeric AND overtime_factor >= 1::numeric AND insurance_percent >= 0::numeric AND insurance_percent <= 100::numeric AND tax_percent >= 0::numeric AND tax_percent <= 100::numeric)
);

CREATE TABLE positions (
	id SERIAL NOT NULL,
	title VARCHAR(100) NOT NULL,
	description TEXT NOT NULL,
	seed_key VARCHAR(32),
	CONSTRAINT positions_pkey PRIMARY KEY (id),
	CONSTRAINT positions_seed_key_key UNIQUE NULLS DISTINCT (seed_key),
	CONSTRAINT positions_title_key UNIQUE NULLS DISTINCT (title)
);

CREATE TABLE shifts (
	id SERIAL NOT NULL,
	name VARCHAR(100) NOT NULL,
	start_time TIME WITHOUT TIME ZONE NOT NULL,
	end_time TIME WITHOUT TIME ZONE NOT NULL,
	break_minutes INTEGER NOT NULL,
	seed_key VARCHAR(40),
	CONSTRAINT shifts_pkey PRIMARY KEY (id),
	CONSTRAINT shifts_name_key UNIQUE NULLS DISTINCT (name),
	CONSTRAINT shifts_seed_key_key UNIQUE NULLS DISTINCT (seed_key)
);

CREATE TABLE trainings (
	id SERIAL NOT NULL,
	title VARCHAR(150) NOT NULL,
	training_date DATE NOT NULL,
	capacity INTEGER NOT NULL,
	description TEXT NOT NULL,
	CONSTRAINT trainings_pkey PRIMARY KEY (id)
);

CREATE TABLE units (
	id SERIAL NOT NULL,
	name VARCHAR(100) NOT NULL,
	branch_id INTEGER NOT NULL,
	seed_key VARCHAR(32),
	CONSTRAINT units_pkey PRIMARY KEY (id),
	CONSTRAINT units_branch_id_fkey FOREIGN KEY(branch_id) REFERENCES branches (id),
	CONSTRAINT units_seed_key_key UNIQUE NULLS DISTINCT (seed_key),
	CONSTRAINT uq_unit_branch_name UNIQUE NULLS DISTINCT (branch_id, name),
	CONSTRAINT uq_unit_id_branch UNIQUE NULLS DISTINCT (id, branch_id)
);

CREATE TABLE admins (
	id SERIAL NOT NULL,
	username VARCHAR(50) NOT NULL,
	display_name VARCHAR(100) NOT NULL,
	password_hash VARCHAR(256) NOT NULL,
	role VARCHAR(20) NOT NULL,
	is_active BOOLEAN NOT NULL,
	branch_scope_id INTEGER,
	unit_scope_id INTEGER,
	CONSTRAINT admins_pkey PRIMARY KEY (id),
	CONSTRAINT admins_branch_scope_id_fkey FOREIGN KEY(branch_scope_id) REFERENCES branches (id),
	CONSTRAINT admins_unit_scope_id_fkey FOREIGN KEY(unit_scope_id) REFERENCES units (id),
	CONSTRAINT admins_username_key UNIQUE NULLS DISTINCT (username)
);

CREATE TABLE employees (
	id SERIAL NOT NULL,
	employee_code VARCHAR(32) NOT NULL,
	first_name VARCHAR(80) NOT NULL,
	last_name VARCHAR(80) NOT NULL,
	national_id VARCHAR(10) NOT NULL,
	phone VARCHAR(11) NOT NULL,
	email VARCHAR(254) NOT NULL,
	hire_date DATE NOT NULL,
	branch_id INTEGER NOT NULL,
	unit_id INTEGER NOT NULL,
	position_id INTEGER NOT NULL,
	contract_type VARCHAR(30) NOT NULL,
	active BOOLEAN NOT NULL,
	seed_key VARCHAR(32),
	CONSTRAINT employees_pkey PRIMARY KEY (id),
	CONSTRAINT employees_branch_id_fkey FOREIGN KEY(branch_id) REFERENCES branches (id),
	CONSTRAINT employees_position_id_fkey FOREIGN KEY(position_id) REFERENCES positions (id),
	CONSTRAINT fk_employee_unit_branch FOREIGN KEY(unit_id, branch_id) REFERENCES units (id, branch_id),
	CONSTRAINT employees_employee_code_key UNIQUE NULLS DISTINCT (employee_code),
	CONSTRAINT employees_seed_key_key UNIQUE NULLS DISTINCT (seed_key)
);

CREATE TABLE assignment_history (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	branch_id INTEGER NOT NULL,
	unit_id INTEGER NOT NULL,
	position_id INTEGER NOT NULL,
	start_date DATE NOT NULL,
	end_date DATE,
	reason TEXT NOT NULL,
	branch_name VARCHAR(100) NOT NULL,
	unit_name VARCHAR(100) NOT NULL,
	position_title VARCHAR(100) NOT NULL,
	CONSTRAINT assignment_history_pkey PRIMARY KEY (id),
	CONSTRAINT assignment_history_branch_id_fkey FOREIGN KEY(branch_id) REFERENCES branches (id),
	CONSTRAINT assignment_history_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT assignment_history_position_id_fkey FOREIGN KEY(position_id) REFERENCES positions (id),
	CONSTRAINT assignment_history_unit_id_branch_id_fkey FOREIGN KEY(unit_id, branch_id) REFERENCES units (id, branch_id)
);

CREATE UNIQUE INDEX uq_employee_current_assignment ON assignment_history (employee_id) WHERE (end_date IS NULL);

CREATE TABLE attendance (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	work_date DATE NOT NULL,
	shift_id INTEGER NOT NULL,
	presence_status VARCHAR(20) NOT NULL,
	clock_in TIME WITHOUT TIME ZONE,
	clock_out TIME WITHOUT TIME ZONE,
	worked_minutes INTEGER NOT NULL,
	overtime_minutes INTEGER NOT NULL,
	required_minutes INTEGER NOT NULL,
	notes TEXT NOT NULL,
	CONSTRAINT attendance_pkey PRIMARY KEY (id),
	CONSTRAINT attendance_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT attendance_shift_id_fkey FOREIGN KEY(shift_id) REFERENCES shifts (id),
	CONSTRAINT attendance_employee_id_work_date_key UNIQUE NULLS DISTINCT (employee_id, work_date),
	CONSTRAINT attendance_check CHECK (worked_minutes >= 0 AND overtime_minutes >= 0)
);

CREATE TABLE audit_log (
	id SERIAL NOT NULL,
	actor_id INTEGER,
	action VARCHAR(40) NOT NULL,
	entity VARCHAR(60) NOT NULL,
	record_id INTEGER,
	details JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT audit_log_pkey PRIMARY KEY (id),
	CONSTRAINT audit_log_actor_id_fkey FOREIGN KEY(actor_id) REFERENCES admins (id)
);

CREATE TABLE candidates (
	id SERIAL NOT NULL,
	first_name VARCHAR(80) NOT NULL,
	last_name VARCHAR(80) NOT NULL,
	national_id VARCHAR(10) NOT NULL,
	phone VARCHAR(11) NOT NULL,
	email VARCHAR(254) NOT NULL,
	branch_id INTEGER NOT NULL,
	unit_id INTEGER NOT NULL,
	position_id INTEGER NOT NULL,
	application_date DATE NOT NULL,
	status VARCHAR(20) NOT NULL,
	notes TEXT NOT NULL,
	employee_id INTEGER,
	seed_key VARCHAR(40),
	CONSTRAINT candidates_pkey PRIMARY KEY (id),
	CONSTRAINT candidates_branch_id_fkey FOREIGN KEY(branch_id) REFERENCES branches (id),
	CONSTRAINT candidates_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT candidates_position_id_fkey FOREIGN KEY(position_id) REFERENCES positions (id),
	CONSTRAINT candidates_unit_id_branch_id_fkey FOREIGN KEY(unit_id, branch_id) REFERENCES units (id, branch_id),
	CONSTRAINT candidates_employee_id_key UNIQUE NULLS DISTINCT (employee_id),
	CONSTRAINT candidates_seed_key_key UNIQUE NULLS DISTINCT (seed_key)
);

CREATE TABLE career_plans (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	target_position_id INTEGER NOT NULL,
	target_date DATE NOT NULL,
	progress INTEGER NOT NULL,
	actions TEXT NOT NULL,
	CONSTRAINT career_plans_pkey PRIMARY KEY (id),
	CONSTRAINT career_plans_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT career_plans_target_position_id_fkey FOREIGN KEY(target_position_id) REFERENCES positions (id),
	CONSTRAINT career_plans_progress_check CHECK (progress >= 0 AND progress <= 100)
);

CREATE TABLE employment_contracts (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	contract_type VARCHAR(30) NOT NULL,
	start_date DATE NOT NULL,
	end_date DATE,
	status VARCHAR(20) NOT NULL,
	base_salary BIGINT NOT NULL,
	notes TEXT NOT NULL,
	renewed_from_id INTEGER,
	termination_reason TEXT NOT NULL,
	CONSTRAINT employment_contracts_pkey PRIMARY KEY (id),
	CONSTRAINT employment_contracts_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT employment_contracts_renewed_from_id_fkey FOREIGN KEY(renewed_from_id) REFERENCES employment_contracts (id)
);

CREATE UNIQUE INDEX uq_employee_active_contract ON employment_contracts (employee_id) WHERE ((status)::text = 'active'::text);

CREATE TABLE evaluations (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	review_date DATE NOT NULL,
	score INTEGER NOT NULL,
	feedback TEXT NOT NULL,
	goals TEXT NOT NULL,
	CONSTRAINT evaluations_pkey PRIMARY KEY (id),
	CONSTRAINT evaluations_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT evaluations_score_check CHECK (score >= 0 AND score <= 100)
);

CREATE TABLE hr_requests (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	kind VARCHAR(20) NOT NULL,
	start_date DATE NOT NULL,
	end_date DATE NOT NULL,
	leave_type VARCHAR(20) NOT NULL,
	destination VARCHAR(150) NOT NULL,
	description TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	review_notes TEXT NOT NULL,
	reviewed_by INTEGER,
	reviewed_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT hr_requests_pkey PRIMARY KEY (id),
	CONSTRAINT hr_requests_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT hr_requests_reviewed_by_fkey FOREIGN KEY(reviewed_by) REFERENCES admins (id)
);

CREATE TABLE login_attempts (
	admin_id INTEGER NOT NULL,
	failure_count INTEGER NOT NULL,
	window_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	blocked_until TIMESTAMP WITH TIME ZONE,
	CONSTRAINT login_attempts_pkey PRIMARY KEY (admin_id),
	CONSTRAINT login_attempts_admin_id_fkey FOREIGN KEY(admin_id) REFERENCES admins (id) ON DELETE CASCADE
);

CREATE TABLE payroll_profiles (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	base_salary BIGINT NOT NULL,
	hourly_rate BIGINT NOT NULL,
	benefits BIGINT NOT NULL,
	deductions BIGINT NOT NULL,
	CONSTRAINT payroll_profiles_pkey PRIMARY KEY (id),
	CONSTRAINT payroll_profiles_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT payroll_profiles_employee_id_key UNIQUE NULLS DISTINCT (employee_id)
);

CREATE TABLE payslips (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	period VARCHAR(7) NOT NULL,
	base_amount BIGINT NOT NULL,
	overtime_amount BIGINT NOT NULL,
	benefits BIGINT NOT NULL,
	insurance BIGINT NOT NULL,
	tax BIGINT NOT NULL,
	deductions BIGINT NOT NULL,
	net_amount BIGINT NOT NULL,
	input_snapshot JSON NOT NULL,
	rule_snapshot JSON NOT NULL,
	created_by INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT payslips_pkey PRIMARY KEY (id),
	CONSTRAINT payslips_created_by_fkey FOREIGN KEY(created_by) REFERENCES admins (id),
	CONSTRAINT payslips_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT payslips_employee_id_period_key UNIQUE NULLS DISTINCT (employee_id, period)
);

CREATE TABLE training_enrollments (
	id SERIAL NOT NULL,
	employee_id INTEGER NOT NULL,
	training_id INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	notes TEXT NOT NULL,
	CONSTRAINT training_enrollments_pkey PRIMARY KEY (id),
	CONSTRAINT training_enrollments_employee_id_fkey FOREIGN KEY(employee_id) REFERENCES employees (id),
	CONSTRAINT training_enrollments_training_id_fkey FOREIGN KEY(training_id) REFERENCES trainings (id),
	CONSTRAINT training_enrollments_employee_id_training_id_key UNIQUE NULLS DISTINCT (employee_id, training_id)
);

CREATE TABLE interviews (
	id SERIAL NOT NULL,
	candidate_id INTEGER NOT NULL,
	scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	interviewer VARCHAR(100) NOT NULL,
	result VARCHAR(20) NOT NULL,
	notes TEXT NOT NULL,
	CONSTRAINT interviews_pkey PRIMARY KEY (id),
	CONSTRAINT interviews_candidate_id_fkey FOREIGN KEY(candidate_id) REFERENCES candidates (id)
);

CREATE TABLE onboarding_tasks (
	id SERIAL NOT NULL,
	candidate_id INTEGER NOT NULL,
	title VARCHAR(150) NOT NULL,
	completed BOOLEAN NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT onboarding_tasks_pkey PRIMARY KEY (id),
	CONSTRAINT onboarding_tasks_candidate_id_fkey FOREIGN KEY(candidate_id) REFERENCES candidates (id),
	CONSTRAINT onboarding_tasks_candidate_id_title_key UNIQUE NULLS DISTINCT (candidate_id, title)
);
