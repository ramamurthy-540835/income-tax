export const roles=["CLIENT","TAX_PREPARER","AUDITOR","ADMIN"] as const;
export type Role=(typeof roles)[number];
export interface AuthenticatedUser{uid:string;role:Role;emailVerified:boolean}
export function requireRole(user:AuthenticatedUser,allowed:readonly Role[]):AuthenticatedUser{if(!allowed.includes(user.role))throw new AuthorizationError();return user}
export class AuthorizationError extends Error{readonly status=403;constructor(){super("You do not have access to this resource")}}
