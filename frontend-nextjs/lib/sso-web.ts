/**
 * Same-origin web OIDC entry point. The backend owns OAuth state, the IdP
 * redirect and the opaque handoff code (RFC 9700). The browser must not probe
 * this endpoint with GET first: that would create state and start OAuth twice.
 */
export function webSsoLoginPath(returnTo: string): string {
  return `/api/auth/sso/oidc/web/login?return_to=${encodeURIComponent(returnTo)}`;
}

export function startWebSso(returnTo: string): void {
  if (typeof window !== 'undefined') {
    window.location.assign(webSsoLoginPath(returnTo));
  }
}
