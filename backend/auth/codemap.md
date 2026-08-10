# Auth Module Codemap

## 1. Responsibility

The `auth` module provides **authentication token management** infrastructure for the AIC Platform using JSON Web Token (JWT) technology. Its primary responsibilities include:

- **Token Generation**: Creation of cryptographically signed JWT access tokens with configurable expiration
- **Token Verification**: Decoding and validation of JWT tokens to extract identity claims
- **Security Boundary**: Centralized JWT signing/verification logic that enforces consistent authentication protocols across all API endpoints and websocket connections

This module implements a **stateless authentication** mechanism where the server validates tokens without maintaining session state, delegating trust verification to the cryptographic signature.

---

## 2. Design Patterns

### Factory Pattern
```python
def create_access_token(data: dict) -> str:
    """Factory method that constructs JWT tokens from claim data."""
```
The `create_access_token()` function acts as a factory, assembling token components (payload + metadata) and returning an encoded JWT string. The encoding algorithm is abstracted behind the `jwt.encode()` call.

### Gateway / Facade Pattern
The module encapsulates complexity of JWT operations (encoding, decoding, error handling, algorithm selection) behind two simple public interfaces:
- `create_access_token()` — single entry point for token creation
- `decode_access_token()` — single entry point for token validation

### Observer Pattern (Error Handling)
The `decode_access_token()` function implements implicit observer behavior through exception handling:
```python
try:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
except JWTError:
    return None
```
The decoder observes `JWTError` exceptions (raised by python-jose library) and gracefully degrades to returning `None` rather than propagating failures up the call stack. This allows callers to handle authentication failure uniformly.

### Singleton Pattern (Configuration)
Module-level access to `settings` (from `backend.config.Settings`) follows singleton semantics—a single shared configuration instance accessed by both functions.

### Command Pattern (Token Operation)
The JWT encode/decode operations represent command objects where:
- **Receiver**: `python-jose.jwt` library methods
- **Invoker**: `create_access_token()` and `decode_access_token()` wrappers
- **Command Parameters**: `data`, `token`, algorithm, secret key

---

## 3. Data & Control Flow

### Token Creation Flow (`create_access_token`)

```
Input: dict containing at minimum `sub` (subject/user identifier)
   │
   ▼
┌─────────────────────────────────────┐
│ 1. Copy input payload               │
│    - Creates shallow copy to        │
│      prevent mutation of original   │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ 2. Compute expiration timestamp     │
│    - datetime.now(timezone.utc)     │
│    + timedelta(minutes=SETTINGS)    │
│    - ACCESS_TOKEN_EXPIRE_MINUTES    │
│    = 1440 minutes (24 hours) by def │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ 3. Add `exp` claim to payload       │
│    to_encode["exp"] = expire        │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ 4. Encode JWT                       │
│    - Algorithm: HS256 (HMAC SHA-256)│
│    - Secret: SETTINGS.SECRET_KEY    │
│    - Output: Base64URL-encoded JWT  │
└─────────────────────────────────────┘
           │
           ▼
Output: str (JWT token string)
```

**Data Exit Points:**
- Returns JWT string to caller
- JWT structure: `[header].[payload].[signature]` (Base64URL encoded)

### Token Verification Flow (`decode_access_token`)

```
Input: str (JWT token)
   │
   ▼
┌─────────────────────────────────────┐
│ 1. Attempt JWT decode               │
│    - Verify signature with          │
│      SECRET_KEY                     │
│    - Validate expiration (exp claim)│
│    - Decode payload to dict         │
└─────────────────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
 Success        Failure (JWTError)
    │             │
    ▼             ▼
┌─────────┐   ┌──────────────┐
│ Return  │   │ Catch JWTError│
│ claims  │   │ Return None   │
│ dict    │   └──────────────┘
└─────────┘
```

**Data Entry Points:**
- Receives JWT string from upstream services (API routes, websockets)
- Validates: signature integrity, expiration status, algorithm match

**Data Exit Points:**
- On success: Returns `dict` of decoded claims (includes `sub`, `exp`, any custom claims)
- On failure: Returns `None` (graceful degradation)

### Configuration Dependency Flow

```
auth.security
     │
     ├→ backend.config.Settings
     │    ├── SECRET_KEY (environment variable: AIC_JWT_SECRET)
     │    ├── ALGORITHM ("HS256")
     │    └── ACCESS_TOKEN_EXPIRE_MINUTES (1440)
     │
     └→ jose.JWTError (external library exception)
         └→ python-jose package
```

**Secret Key Lifecycle:**
1. Environment variable `AIC_JWT_SECRET` read during `Settings.ensure_dirs()` initialization
2. Minimum 32 characters enforced at startup
3. Stored in singleton `settings` object
4. Used as symmetric key for HMAC-SHA256 signing

---

## 4. Integration Points

### Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `python-jose` | External Library | JWT encoding/decoding operations |
| `backend.config.Settings` | Internal Module | Configuration retrieval (secret key, algorithm, token expiry) |
| `datetime`, `timedelta`, `timezone` | Standard Library | Expiration timestamp computation |

### Consumer Modules (Call Sites)

| Module | Import Location | Usage |
|--------|-----------------|-------|
| `backend.backend.api.dependencies` | Line 9 | `from auth.security import decode_access_token` |
| **Dependencies Usage**: `Line 27` | Extracts user claims from Bearer token for dependency injection |
| `backend.backend.api.routes.auth` | Line 19 | `from auth.security import create_access_token, decode_access_token` |
| **Auth Routes**: `Line 134` | Generates JWT after successful credential verification |
| **Auth Routes**: `Line 148` | Validates token payload for protected route access |
| `backend.backend.routes.websocket` | Line 17 | `from auth.security import decode_access_token` |
| **WebSocket**: `Line 187` | Authenticates WebSocket connection via JWT in query params or header |

### External Interface Contracts

#### `create_access_token(data: dict) -> str`
- **Expected Input**: Dictionary containing at minimum `sub` field (user identifier)
- **Return Value**: RFC 7519 compliant JWT string
- **Contract Violation Behavior**: Raises `JWTError` if payload invalid or secret key misconfigured

#### `decode_access_token(token: str) -> dict \| None`
- **Expected Input**: Valid JWT string (Bearer token format)
- **Return Value**: 
  - On success: Decoded claim dictionary (e.g., `{"sub": "admin", "exp": 1723296000}`)
  - On failure: `None` (silent failure pattern—caller must check falsy return)
- **Failure Conditions**: Expired token, invalid signature, wrong algorithm, malformed JWT

### Architecture Context

```
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ REST Routes  │  │ Dependencies │  │ WebSocket Handler│  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                   │             │
│         └─────────────────┼───────────────────┘             │
│                           ▼                                 │
│                  ┌────────────────┐                         │
│                  │  auth.security │                         │
│                  └────────┬───────┘                         │
│                           │                                 │
│              ┌────────────┴────────────┐                    │
│              ▼                         ▼                    │
│   ┌──────────────────────┐  ┌──────────────────────┐      │
│   │ backend.config       │  │ python-jose          │      │
│   │ Settings (singleton) │  │ (HMAC-SHA256 crypto) │      │
│   └──────────────────────┘  └──────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Security Considerations

- **Symmetric Cryptography**: Uses HMAC-SHA256 (HS256), meaning the same secret key signs AND verifies tokens
- **Key Management**: Secret key MUST be provided via environment variable at runtime (no file-based fallback per GAP-1 fix)
- **Token Lifetime**: Default 24-hour expiry (`ACCESS_TOKEN_EXPIRE_MINUTES = 1440`)
- **Subject Claim**: Token `sub` field contains username—not full user object or roles (application-layer authorization required)

---

## File Structure

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 0 | Empty package marker |
| `security.py` | 27 | Core JWT functionality (2 public functions) |

---

## Maintenance Notes

- **No bcrypt integration**: Comment on line 18 explicitly notes this module handles JWT, not password hashing (bcrypt would be used separately in authentication credentials validation)
- **Windows/Linux compatibility**: Comment on lines 4-6 indicates python-jose was chosen over PyJWT for bundled runtime consistency
- **Thread Safety**: Module functions are pure (no mutable state)—thread-safe by design
- **Testing Strategy**: Functions should be unit-tested with mock settings and known JWT vectors
