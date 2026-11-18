BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE companies (
    name VARCHAR(200) NOT NULL, 
    gstin VARCHAR(15), 
    address TEXT, 
    state_code VARCHAR(2), 
    email VARCHAR(255), 
    phone VARCHAR(40), 
    is_demo BOOLEAN NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_companies_gstin ON companies (gstin);

CREATE TABLE approval_policies (
    company_id VARCHAR(36) NOT NULL, 
    levels JSON NOT NULL, 
    allow_self_approval BOOLEAN NOT NULL, 
    allow_critical_override BOOLEAN NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    UNIQUE (company_id)
);

CREATE TABLE company_settings (
    company_id VARCHAR(36) NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    amount_tolerance NUMERIC(18, 2) NOT NULL, 
    po_price_tolerance_pct NUMERIC(18, 2) NOT NULL, 
    po_qty_tolerance_pct NUMERIC(18, 2) NOT NULL, 
    duplicate_window_days INTEGER NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    UNIQUE (company_id)
);

CREATE TABLE suppliers (
    company_id VARCHAR(36) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    code VARCHAR(40) NOT NULL, 
    gstin VARCHAR(15), 
    email VARCHAR(255), 
    phone VARCHAR(40), 
    address TEXT, 
    contact_person VARCHAR(200), 
    payment_terms_days INTEGER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    CONSTRAINT uq_supplier_company_code UNIQUE (company_id, code)
);

CREATE INDEX ix_suppliers_company_id ON suppliers (company_id);

CREATE INDEX ix_suppliers_gstin ON suppliers (gstin);

CREATE INDEX ix_suppliers_name ON suppliers (name);

CREATE TABLE users (
    company_id VARCHAR(36) NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    full_name VARCHAR(200) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    token_version INTEGER NOT NULL, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX ix_users_company_id ON users (company_id);

CREATE INDEX ix_users_role ON users (role);

CREATE TABLE audit_logs (
    company_id VARCHAR(36), 
    actor_id VARCHAR(36), 
    actor_email VARCHAR(255), 
    action VARCHAR(60) NOT NULL, 
    entity_type VARCHAR(40), 
    entity_id VARCHAR(36), 
    metadata JSON, 
    ip_address VARCHAR(64), 
    request_id VARCHAR(36), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_audit_company_created ON audit_logs (company_id, created_at);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);

CREATE INDEX ix_audit_logs_entity_id ON audit_logs (entity_id);

CREATE TABLE password_reset_tokens (
    user_id VARCHAR(36) NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITH TIME ZONE, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (token_hash)
);

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE TABLE purchase_orders (
    company_id VARCHAR(36) NOT NULL, 
    supplier_id VARCHAR(36) NOT NULL, 
    po_number VARCHAR(60) NOT NULL, 
    po_date DATE NOT NULL, 
    expected_delivery_date DATE, 
    currency VARCHAR(3) NOT NULL, 
    subtotal NUMERIC(18, 2) NOT NULL, 
    tax_total NUMERIC(18, 2) NOT NULL, 
    total_amount NUMERIC(18, 2) NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    notes TEXT, 
    created_by_id VARCHAR(36), 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(created_by_id) REFERENCES users (id), 
    FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
    CONSTRAINT uq_po_company_number UNIQUE (company_id, po_number)
);

CREATE INDEX ix_purchase_orders_company_id ON purchase_orders (company_id);

CREATE INDEX ix_purchase_orders_supplier_id ON purchase_orders (supplier_id);

CREATE TABLE invoices (
    company_id VARCHAR(36) NOT NULL, 
    supplier_id VARCHAR(36), 
    purchase_order_id VARCHAR(36), 
    invoice_number VARCHAR(60), 
    invoice_number_normalized VARCHAR(60), 
    invoice_date DATE, 
    due_date DATE, 
    po_number_ref VARCHAR(60), 
    currency VARCHAR(3) NOT NULL, 
    supplier_name_raw VARCHAR(200), 
    supplier_gstin_raw VARCHAR(15), 
    supplier_address_raw TEXT, 
    buyer_name VARCHAR(200), 
    buyer_gstin VARCHAR(15), 
    buyer_address TEXT, 
    subtotal NUMERIC(18, 2), 
    discount NUMERIC(18, 2), 
    taxable_amount NUMERIC(18, 2), 
    cgst NUMERIC(18, 2), 
    sgst NUMERIC(18, 2), 
    igst NUMERIC(18, 2), 
    other_charges NUMERIC(18, 2), 
    total_tax NUMERIC(18, 2), 
    grand_total NUMERIC(18, 2), 
    status VARCHAR(30) NOT NULL, 
    payment_status VARCHAR(20) NOT NULL, 
    validation_status VARCHAR(20) NOT NULL, 
    duplicate_status VARCHAR(30) NOT NULL, 
    po_match_status VARCHAR(30) NOT NULL, 
    has_critical_errors BOOLEAN NOT NULL, 
    extracted_data JSON, 
    extraction_method VARCHAR(30), 
    needs_review_fields JSON, 
    notes TEXT, 
    is_demo BOOLEAN NOT NULL, 
    created_by_id VARCHAR(36), 
    submitted_by_id VARCHAR(36), 
    submitted_at TIMESTAMP WITH TIME ZONE, 
    decided_at TIMESTAMP WITH TIME ZONE, 
    archived_at TIMESTAMP WITH TIME ZONE, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(created_by_id) REFERENCES users (id), 
    FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id), 
    FOREIGN KEY(submitted_by_id) REFERENCES users (id), 
    FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);

CREATE INDEX ix_invoice_company_date ON invoices (company_id, invoice_date);

CREATE INDEX ix_invoice_company_status ON invoices (company_id, status);

CREATE INDEX ix_invoice_dup_lookup ON invoices (company_id, supplier_id, invoice_number_normalized);

CREATE INDEX ix_invoices_purchase_order_id ON invoices (purchase_order_id);

CREATE INDEX ix_invoices_supplier_id ON invoices (supplier_id);

CREATE TABLE purchase_order_items (
    purchase_order_id VARCHAR(36) NOT NULL, 
    line_no INTEGER NOT NULL, 
    description VARCHAR(500) NOT NULL, 
    hsn_sac VARCHAR(10), 
    quantity NUMERIC(18, 3) NOT NULL, 
    unit VARCHAR(20), 
    unit_price NUMERIC(18, 2) NOT NULL, 
    tax_rate NUMERIC(18, 2) NOT NULL, 
    line_total NUMERIC(18, 2) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id) ON DELETE CASCADE
);

CREATE INDEX ix_purchase_order_items_purchase_order_id ON purchase_order_items (purchase_order_id);

CREATE TABLE approval_requests (
    company_id VARCHAR(36) NOT NULL, 
    invoice_id VARCHAR(36) NOT NULL, 
    submitted_by_id VARCHAR(36) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    current_level INTEGER NOT NULL, 
    required_levels JSON NOT NULL, 
    submission_note TEXT, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE CASCADE, 
    FOREIGN KEY(submitted_by_id) REFERENCES users (id)
);

CREATE INDEX ix_approval_requests_company_id ON approval_requests (company_id);

CREATE INDEX ix_approval_requests_invoice_id ON approval_requests (invoice_id);

CREATE INDEX ix_approval_requests_status ON approval_requests (status);

CREATE TABLE documents (
    company_id VARCHAR(36) NOT NULL, 
    invoice_id VARCHAR(36), 
    uploaded_by_id VARCHAR(36), 
    original_filename VARCHAR(255) NOT NULL, 
    storage_provider VARCHAR(20) NOT NULL, 
    storage_key VARCHAR(500) NOT NULL, 
    content_type VARCHAR(50) NOT NULL, 
    size_bytes BIGINT NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    page_count INTEGER, 
    status VARCHAR(20) NOT NULL, 
    error_message TEXT, 
    is_demo BOOLEAN NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE SET NULL, 
    FOREIGN KEY(uploaded_by_id) REFERENCES users (id), 
    UNIQUE (storage_key)
);

CREATE INDEX ix_documents_company_id ON documents (company_id);

CREATE INDEX ix_documents_invoice_id ON documents (invoice_id);

CREATE INDEX ix_documents_sha256 ON documents (sha256);

CREATE TABLE duplicate_matches (
    company_id VARCHAR(36) NOT NULL, 
    invoice_id VARCHAR(36) NOT NULL, 
    matched_invoice_id VARCHAR(36) NOT NULL, 
    match_type VARCHAR(30) NOT NULL, 
    score INTEGER NOT NULL, 
    reasons JSON NOT NULL, 
    resolution VARCHAR(30), 
    resolution_note TEXT, 
    resolved_by_id VARCHAR(36), 
    resolved_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE CASCADE, 
    FOREIGN KEY(matched_invoice_id) REFERENCES invoices (id) ON DELETE CASCADE, 
    FOREIGN KEY(resolved_by_id) REFERENCES users (id)
);

CREATE INDEX ix_duplicate_matches_company_id ON duplicate_matches (company_id);

CREATE INDEX ix_duplicate_matches_invoice_id ON duplicate_matches (invoice_id);

CREATE TABLE invoice_items (
    invoice_id VARCHAR(36) NOT NULL, 
    line_no INTEGER NOT NULL, 
    description VARCHAR(500), 
    hsn_sac VARCHAR(10), 
    quantity NUMERIC(18, 3), 
    unit VARCHAR(20), 
    unit_price NUMERIC(18, 2), 
    discount NUMERIC(18, 2), 
    taxable_value NUMERIC(18, 2), 
    tax_rate NUMERIC(18, 2), 
    tax_amount NUMERIC(18, 2), 
    line_total NUMERIC(18, 2), 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE CASCADE
);

CREATE INDEX ix_invoice_items_invoice_id ON invoice_items (invoice_id);

CREATE TABLE po_match_results (
    company_id VARCHAR(36) NOT NULL, 
    invoice_id VARCHAR(36) NOT NULL, 
    purchase_order_id VARCHAR(36), 
    status VARCHAR(30) NOT NULL, 
    report JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE CASCADE, 
    FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id)
);

CREATE INDEX ix_po_match_results_company_id ON po_match_results (company_id);

CREATE INDEX ix_po_match_results_invoice_id ON po_match_results (invoice_id);

CREATE TABLE validation_results (
    company_id VARCHAR(36) NOT NULL, 
    invoice_id VARCHAR(36) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    report JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE CASCADE
);

CREATE INDEX ix_validation_results_company_id ON validation_results (company_id);

CREATE INDEX ix_validation_results_invoice_id ON validation_results (invoice_id);

CREATE TABLE approval_steps (
    request_id VARCHAR(36) NOT NULL, 
    level INTEGER NOT NULL, 
    approver_id VARCHAR(36) NOT NULL, 
    decision VARCHAR(20) NOT NULL, 
    comment TEXT, 
    override_critical BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(approver_id) REFERENCES users (id), 
    FOREIGN KEY(request_id) REFERENCES approval_requests (id) ON DELETE CASCADE
);

CREATE INDEX ix_approval_steps_request_id ON approval_steps (request_id);

CREATE TABLE processing_records (
    company_id VARCHAR(36) NOT NULL, 
    document_id VARCHAR(36) NOT NULL, 
    invoice_id VARCHAR(36), 
    status VARCHAR(20) NOT NULL, 
    text_method VARCHAR(20), 
    extraction_method VARCHAR(30), 
    ocr_confidence FLOAT, 
    duration_ms INTEGER, 
    warnings JSON, 
    error_message TEXT, 
    raw_text TEXT, 
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE SET NULL
);

CREATE INDEX ix_processing_records_company_id ON processing_records (company_id);

CREATE INDEX ix_processing_records_document_id ON processing_records (document_id);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

