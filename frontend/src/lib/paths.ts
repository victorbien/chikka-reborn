/** Route paths shared by features and the route table. */
export const paths = {
  home: "/",
  styleGuide: "/style-guide",
  signIn: "/auth/sign-in",
  register: "/auth/register",
  forgotPassword: "/auth/forgot-password",
  resetPassword: "/auth/reset-password",
  verifyEmail: "/auth/verify-email",
  onboarding: "/onboarding",
  contacts: "/contacts",
  messages: "/messages",
  newMessage: "/messages/new",
  settings: "/settings/profile",
} as const;
