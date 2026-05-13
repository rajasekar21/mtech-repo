// ── API Intelligence Platform — Neo4j Schema ──────────────────────────
// Constraints (enforce uniqueness + auto-create indexes)

CREATE CONSTRAINT api_id IF NOT EXISTS
  FOR (a:API) REQUIRE a.id IS UNIQUE;

CREATE CONSTRAINT flow_id IF NOT EXISTS
  FOR (f:Flow) REQUIRE f.id IS UNIQUE;

CREATE CONSTRAINT psp_id IF NOT EXISTS
  FOR (p:PSP) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT bank_id IF NOT EXISTS
  FOR (b:Bank) REQUIRE b.id IS UNIQUE;

CREATE CONSTRAINT auth_method_id IF NOT EXISTS
  FOR (a:AuthenticationMethod) REQUIRE a.id IS UNIQUE;

CREATE CONSTRAINT security_rule_id IF NOT EXISTS
  FOR (s:SecurityRule) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT transaction_type_id IF NOT EXISTS
  FOR (t:TransactionType) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT spec_id IF NOT EXISTS
  FOR (s:Spec) REQUIRE s.id IS UNIQUE;

// ── Performance indexes ────────────────────────────────────────────────
CREATE INDEX api_name IF NOT EXISTS FOR (a:API) ON (a.name);
CREATE INDEX api_spec_id IF NOT EXISTS FOR (a:API) ON (a.spec_id);
CREATE INDEX api_risk_level IF NOT EXISTS FOR (a:API) ON (a.risk_level);
CREATE INDEX flow_spec_id IF NOT EXISTS FOR (f:Flow) ON (f.spec_id);
CREATE INDEX flow_type IF NOT EXISTS FOR (f:Flow) ON (f.type);

// ── Example: UPI Platform seed nodes ─────────────────────────────────
// These represent the typical UPI ecosystem architecture entities

MERGE (npci:PSP {id: 'npci', name: 'NPCI', type: 'switch', description: 'National Payments Corporation of India'})
MERGE (psp1:PSP {id: 'psp-payer', name: 'Payer PSP', type: 'psp', description: 'Payer Payment Service Provider'})
MERGE (psp2:PSP {id: 'psp-payee', name: 'Payee PSP', type: 'psp', description: 'Payee Payment Service Provider'})
MERGE (bank1:Bank {id: 'payer-bank', name: 'Payer Bank', type: 'bank', description: 'Payer account holding bank'})
MERGE (bank2:Bank {id: 'payee-bank', name: 'Payee Bank', type: 'bank', description: 'Payee account holding bank'})

MERGE (auth_mpin:AuthenticationMethod {id: 'mpin', name: 'MPIN', type: 'pin', description: 'Mobile PIN authentication'})
MERGE (auth_biometric:AuthenticationMethod {id: 'biometric', name: 'Biometric', type: 'biometric', description: 'Fingerprint/IRIS authentication'})
MERGE (auth_otp:AuthenticationMethod {id: 'otp', name: 'OTP', type: 'otp', description: 'One-Time Password'})

MERGE (txn_pay:TransactionType {id: 'txn-pay', name: 'Pay', code: 'PAY', description: 'Payment transaction'})
MERGE (txn_bal:TransactionType {id: 'txn-bal', name: 'Balance Enquiry', code: 'BAL', description: 'Account balance enquiry'})
MERGE (txn_mandate:TransactionType {id: 'txn-mandate', name: 'Mandate', code: 'MAN', description: 'Recurring payment mandate'})

// PSP → NPCI routing relationships
MERGE (psp1)-[:ROUTES_TO {type: 'primary'}]->(npci)
MERGE (psp2)-[:ROUTES_TO {type: 'primary'}]->(npci)
MERGE (npci)-[:ROUTES_TO {type: 'settlement'}]->(bank1)
MERGE (npci)-[:ROUTES_TO {type: 'settlement'}]->(bank2)

// Auth method associations
MERGE (txn_pay)-[:AUTHENTICATES_WITH]->(auth_mpin)
MERGE (txn_pay)-[:AUTHENTICATES_WITH]->(auth_biometric)
MERGE (txn_bal)-[:AUTHENTICATES_WITH]->(auth_mpin)
MERGE (txn_mandate)-[:AUTHENTICATES_WITH]->(auth_otp)
