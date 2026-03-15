-- ============================================================
-- LEDGER_AI - COMPLETE DATABASE SCHEMA
-- Run this on a fresh database to recreate everything.
-- ============================================================

-- ============================================================
-- 1. USERS
-- ============================================================
CREATE TABLE users (
    user_id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('USER','ADMIN') NOT NULL DEFAULT 'USER',
    status        ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ============================================================
-- 2. USER SESSIONS
-- ============================================================
CREATE TABLE user_sessions (
    session_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    token      VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ============================================================
-- 3. ACCOUNTS  (needed as FK target for documents)
-- ============================================================
CREATE TABLE accounts (
    account_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    account_name VARCHAR(255) NOT NULL,
    account_type VARCHAR(100) NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ============================================================
-- 4. STATEMENT CATEGORIES  (must exist before documents FK)
-- ============================================================
CREATE TABLE statement_categories (
    statement_id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    statement_type     VARCHAR(50)  NOT NULL,
    format_name        VARCHAR(150) NOT NULL,
    institution_name   VARCHAR(100) NOT NULL,
    ifsc_code          VARCHAR(20)  NULL,
    statement_identifier JSON       NOT NULL,
    extraction_logic   LONGTEXT     NOT NULL,
    match_threshold    DECIMAL(5,2) NOT NULL DEFAULT 65.00,
    logic_version      INT          NOT NULL DEFAULT 1,
    status ENUM('ACTIVE','UNDER_REVIEW','DISABLED','EXPERIMENTAL') NOT NULL DEFAULT 'UNDER_REVIEW',
    success_rate       DECIMAL(5,2) NULL,
    last_verified_at   TIMESTAMP    NULL,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ============================================================
-- 5. DOCUMENTS
-- ============================================================
CREATE TABLE documents (
    document_id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id                  BIGINT  NOT NULL,
    statement_id             BIGINT  NULL,
    account_id               BIGINT  NULL,
    account_match_confidence DECIMAL(5,2) NULL,
    file_name                VARCHAR(255) NOT NULL,
    file_path                VARCHAR(500) NOT NULL,
    is_password_protected    BOOLEAN NOT NULL DEFAULT FALSE,
    transaction_parsed_type  ENUM('CODE','LLM') NULL,
    parser_version           VARCHAR(50) NULL,
    status ENUM(
        'UPLOADED',
        'PASSWORD_REQUIRED',
        'EXTRACTING_TEXT',
        'IDENTIFYING_FORMAT',
        'PARSING_TRANSACTIONS',
        'AWAITING_REVIEW',
        'CATEGORIZING',
        'POSTED',
        'APPROVE',
        'FAILED'
    ) NOT NULL DEFAULT 'UPLOADED',
    is_active                BOOLEAN   NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_started_at    TIMESTAMP NULL,
    processing_completed_at  TIMESTAMP NULL,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)       REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (statement_id)  REFERENCES statement_categories(statement_id) ON DELETE SET NULL,
    FOREIGN KEY (account_id)    REFERENCES accounts(account_id)
);

-- ============================================================
-- 6. DOCUMENT PASSWORDS
-- ============================================================
CREATE TABLE document_password (
    document_id        BIGINT PRIMARY KEY,
    encrypted_password VARCHAR(255) NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

-- ============================================================
-- 7. DOCUMENT TEXT EXTRACTIONS
-- ============================================================
CREATE TABLE document_text_extractions (
    text_extraction_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id        BIGINT NOT NULL,
    extraction_method  ENUM('PDF_TEXT','OCR','HYBRID') NOT NULL DEFAULT 'PDF_TEXT',
    extracted_text     LONGTEXT NOT NULL,
    extraction_status  ENUM('SUCCESS','FAILED') NOT NULL DEFAULT 'SUCCESS',
    error_message      VARCHAR(500),
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

-- ============================================================
-- 8. AI TRANSACTIONS STAGING
--    NOTE: review_status column intentionally omitted
--    (it was created then dropped in the original migration)
-- ============================================================
CREATE TABLE ai_transactions_staging (
    staging_transaction_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id            BIGINT NOT NULL,
    user_id                BIGINT NOT NULL,
    transaction_json       JSON   NOT NULL,
    parser_type            ENUM('LLM','CODE') NOT NULL,
    overall_confidence     DECIMAL(5,2) NOT NULL,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)      REFERENCES users(user_id),
    FOREIGN KEY (document_id)  REFERENCES documents(document_id) ON DELETE CASCADE
);

-- ============================================================
-- 9. RANDOM QC RESULTS
-- ============================================================
CREATE TABLE random_qc_results (
    qc_id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id          BIGINT        NOT NULL,
    statement_id         BIGINT        NULL,
    file_name            VARCHAR(255)  NULL,
    institution_name     VARCHAR(100)  NULL,
    code_txn_count       INT           NOT NULL DEFAULT 0,
    llm_txn_count        INT           NOT NULL DEFAULT 0,
    matched_count        INT           NOT NULL DEFAULT 0,
    unmatched_code_count INT           NOT NULL DEFAULT 0,
    unmatched_llm_count  INT           NOT NULL DEFAULT 0,
    accuracy             DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    qc_status            ENUM('PENDING','FLAGGED','REVIEWED') NOT NULL DEFAULT 'PENDING',
    reconciliation_json  LONGTEXT      NULL,
    code_txn_json        LONGTEXT      NULL,
    llm_txn_json         LONGTEXT      NULL,
    reviewer_notes       TEXT          NULL,
    issue_type           VARCHAR(100)  NULL,
    assigned_to          VARCHAR(100)  NULL,
    reviewed_at          TIMESTAMP     NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id)  REFERENCES documents(document_id) ON DELETE CASCADE,
    FOREIGN KEY (statement_id) REFERENCES statement_categories(statement_id) ON DELETE SET NULL
);

-- ============================================================
-- 10. TRANSACTION OVERRIDES
-- ============================================================
CREATE TABLE transaction_overrides (
    override_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    staging_transaction_id BIGINT       NOT NULL,
    field_name             VARCHAR(100) NOT NULL,
    ai_value               TEXT         NULL,
    user_value             TEXT         NULL,
    overridden_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staging_transaction_id)
        REFERENCES ai_transactions_staging(staging_transaction_id) ON DELETE CASCADE
);
