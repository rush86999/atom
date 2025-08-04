export type RefreshTokenResponseBodyType = {
  access_token: string;
  expires_in: number; // add seconds to now
  scope: string;
  token_type: string;
};
