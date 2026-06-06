# Spec: Contract Generation Engine & DocuSign E2E

## Status: SHIPPED
**Roadmap:** STREAM 6 PHASE 1.0  
**Branch:** `feat/stream-6-phase-1.0-contract-generation-docusign` ← `develop`  
**Apps:** `apps/api-fastapi/`, `apps/storefront-next/`  
**Feature README:** `docs/features/contract-generation/README.md`

---

## 1. Objective

Enable real estate agents and admins to generate legally binding DocuSign contract envelopes directly from a property listing's detail page on the storefront with a single click. This integrates a stateless FastAPI contract generation backend with a Next.js storefront client using Supabase JWT Bearer token authentication and DocuSign's Machine-to-Machine JWT Grant authentication.

**In scope**
- `DocuSignJWTAuthenticator`: A stateless class that exchanges DocuSign integration key, user ID, and RSA private key for an OAuth access token.
- `ContractEnvelopeBuilder`: A stateless mapper converting a `PropertyListing` model and authenticated agent/admin credentials into a valid DocuSign `EnvelopeDefinition`.
- `ContractDispatcher`: An execution service that sends the generated envelope using the authorized `ApiClient` and returns the envelope ID.
- Endpoint `POST /api/v1/contracts/generate` protected by `RoleChecker([UserRole.AGENT, UserRole.ADMIN])`.
- Additive database changes to `LegalContract` in `models.py` and `database.py` (adding `property_id` and `user_id` columns, making `transaction_session_id` nullable).
- Storefront integration: "Generar Contrato" button on property detail view using React Query `useMutation` and displaying a success toast.
- High-density unit testing with absolute network isolation.

**Out of scope**
- Customer signing ceremony UI (handled in Stream 4 Phase 5.1).
- Multi-template conditional rendering based on sector or price.
- Live DocuSign sandbox calls in unit tests (fully mocked).

---

## 2. API / Data contracts

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/contracts/generate` | Generates a DocuSign envelope from a property listing. Returns `201 Created`. Scoped to agent/admin. |

**Request Body (`ContractGenerateRequest`):**
```json
{
  "property_id": "string"
}
```

**Response Body (`ContractGenerateResponse`):**
```json
{
  "envelope_id": "string",
  "status": "string",
  "contract_id": "string"
}
```

**Models / tables:**
`LegalContract` in `models.py` modified:
- `transaction_session_id`: updated to `Optional[str]` (nullable).
- `property_id`: `Optional[str]` (foreign_key to `real_estate.properties.id`, index=True).
- `user_id`: `Optional[str]` (index=True).

---

## 3. Storefront

- **Component changes**: Update `PropertyDetailClient.tsx` to display a "Generar Contrato" button next to existing action buttons (only visible if user has `agent` or `admin` role, or enabled for test/demo).
- **React Query Mutation**: `useMutation` calling `api.generateContract(propertyId)` which executes a `POST` to `/api/v1/contracts/generate`.
- **Query keys**: Cache invalidation on transaction/contract collections if applicable.

---

## 4. Security & boundaries

- **Auth**: Endpoint is strictly guarded by `RoleChecker([UserRole.AGENT, UserRole.ADMIN])`.
- **Tenant Isolation**: The authenticated agent's `user_id` from the JWT claims is persisted in `LegalContract.user_id`.
- **DocuSign Secrets**: Credentials (`DOCUSIGN_PRIVATE_KEY_PATH`, `DOCUSIGN_INTEGRATION_KEY`, etc.) are resolved server-side from gitignored `.env` variables.
- **SSRF**: Input validation enforces that the `property_id` must match a valid active `PropertyListing` in the database.

---

## 5. Verification gates

| Gate | Command / check |
|------|-----------------|
| API tests | `pytest apps/api-fastapi/tests/test_docusign_contracts.py` (100% mocked, 0 network calls) |
| Full pytest gate | `cd apps/api-fastapi; .\.venv\Scripts\python.exe -m pytest -q --tb=no` (70+ passed, 0 failures) |
| Storefront build | `npm run build` under `apps/storefront-next` |
| Manual | Agent clicks "Generar Contrato" -> success toast with envelope ID and transaction status. |

**No** memory/session file updates until Manual Success.

---

## 6. Drift policy

If implementation diverges from this spec, update spec **or** code in the same PR — never silent drift.
All new classes must maintain 100% PEP 257 docstring compliance.
