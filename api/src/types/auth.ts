import { Type, Static } from '@sinclair/typebox';

// User role schema
export const UserRoleSchema = Type.Union([
  Type.Literal('admin'),
  Type.Literal('user'),
  Type.Literal('readonly'),
]);

export type UserRole = Static<typeof UserRoleSchema>;

// JWT payload schema
export const JWTPayloadSchema = Type.Object({
  sub: Type.String(), // User ID
  type: Type.Union([Type.Literal('access'), Type.Literal('refresh')]),
  iat: Type.Number(),
  exp: Type.Number(),
  iss: Type.String(),
});

export type JWTPayload = Static<typeof JWTPayloadSchema>;

// API key permissions schema
export const APIKeyPermissionsSchema = Type.Array(Type.String());

export type APIKeyPermissions = Static<typeof APIKeyPermissionsSchema>;

// User authentication info
export interface UserAuthInfo {
  id: string;
  role: UserRole;
  apiKey?: boolean;
  permissions?: APIKeyPermissions;
}

// Authentication headers
export const AuthHeadersSchema = Type.Object({
  authorization: Type.Optional(Type.String()),
  'x-api-key': Type.Optional(Type.String()),
});

export type AuthHeaders = Static<typeof AuthHeadersSchema>;

// API key creation request
export const CreateAPIKeyRequestSchema = Type.Object({
  name: Type.String({ minLength: 1, maxLength: 100 }),
  permissions: Type.Optional(APIKeyPermissionsSchema),
  expires_at: Type.Optional(Type.String({ format: 'date-time' })),
});

export type CreateAPIKeyRequest = Static<typeof CreateAPIKeyRequestSchema>;

// API key response
export const APIKeyResponseSchema = Type.Object({
  id: Type.String(),
  name: Type.String(),
  key: Type.String(),
  permissions: APIKeyPermissionsSchema,
  created_at: Type.String({ format: 'date-time' }),
  expires_at: Type.Optional(Type.String({ format: 'date-time' })),
  last_used_at: Type.Optional(Type.String({ format: 'date-time' })),
});

export type APIKeyResponse = Static<typeof APIKeyResponseSchema>;

// JWT tokens response
export const TokensResponseSchema = Type.Object({
  access_token: Type.String(),
  refresh_token: Type.String(),
  token_type: Type.Literal('Bearer'),
  expires_in: Type.Number(),
});

export type TokensResponse = Static<typeof TokensResponseSchema>;

// Login request
export const LoginRequestSchema = Type.Object({
  email: Type.String({ format: 'email' }),
  password: Type.String({ minLength: 8 }),
});

export type LoginRequest = Static<typeof LoginRequestSchema>;

// Rate limit info
export interface RateLimitInfo {
  limit: number;
  remaining: number;
  resetTime: number;
  windowMs: number;
}