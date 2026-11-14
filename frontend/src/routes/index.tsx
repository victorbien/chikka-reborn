import type { RouteObject } from "react-router-dom";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { RootLayout } from "@/components/layout/RootLayout";
import { paths } from "@/lib/paths";
import {
  ForgotPasswordPage,
  RegisterPage,
  ResetPasswordPage,
  SignInPage,
  VerifyEmailPage,
} from "@/routes/AuthPages";
import {
  PublicAppLayout,
  RedirectIfSignedIn,
  RequireAuth,
  RequireOnboarded,
  SignedInAppLayout,
} from "@/routes/guards";
import {
  AdminAiPage,
  AdminAuditPage,
  AdminLayout,
  AdminMessagesPage,
  AdminOverviewPage,
  AdminUsersPage,
} from "@/routes/AdminPages";
import { AdminSmsPage } from "@/routes/AdminSmsPage";
import { ContactsPage } from "@/routes/ContactsPage";
import { CreditsPage } from "@/routes/CreditsPage";
import { HomePage } from "@/routes/HomePage";
import { MessagesPage, NewConversationPage } from "@/routes/MessagesPage";
import { NotFoundPage } from "@/routes/NotFoundPage";
import { NotificationSettingsPage } from "@/routes/NotificationSettingsPage";
import { NotificationsPage } from "@/routes/NotificationsPage";
import { ProfileSettingsPage, ProfileSetupPage } from "@/routes/ProfilePages";
import { RouteErrorPage } from "@/routes/RouteErrorPage";
import { SmsPage } from "@/routes/SmsPage";
import { StyleGuide } from "@/routes/StyleGuide";

export const appRoutes: RouteObject[] = [
  {
    element: <RootLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          {
            element: <RedirectIfSignedIn />,
            children: [
              { path: paths.signIn, element: <SignInPage /> },
              { path: paths.register, element: <RegisterPage /> },
              { path: paths.forgotPassword, element: <ForgotPasswordPage /> },
            ],
          },
          // Links from emails work whether or not someone is signed in on this browser.
          { path: paths.verifyEmail, element: <VerifyEmailPage /> },
          { path: paths.resetPassword, element: <ResetPasswordPage /> },
        ],
      },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AuthLayout />,
            children: [{ path: paths.onboarding, element: <ProfileSetupPage /> }],
          },
          {
            element: <RequireOnboarded />,
            children: [
              {
                element: <SignedInAppLayout />,
                children: [
                  { index: true, element: <HomePage /> },
                  { path: paths.contacts, element: <ContactsPage /> },
                  { path: paths.newMessage, element: <NewConversationPage /> },
                  { path: paths.messages, element: <MessagesPage /> },
                  { path: `${paths.messages}/:conversationId`, element: <MessagesPage /> },
                  { path: paths.sms, element: <SmsPage mode="list" /> },
                  { path: paths.smsNew, element: <SmsPage mode="new" /> },
                  {
                    path: `${paths.sms}/:conversationId`,
                    element: <SmsPage mode="conversation" />,
                  },
                  {
                    element: <AdminLayout />,
                    children: [
                      { path: paths.admin, element: <AdminOverviewPage /> },
                      { path: paths.adminUsers, element: <AdminUsersPage /> },
                      { path: paths.adminMessages, element: <AdminMessagesPage /> },
                      { path: paths.adminAi, element: <AdminAiPage /> },
                      { path: paths.adminAudit, element: <AdminAuditPage /> },
                    ],
                  },
                  { path: paths.adminSms, element: <AdminSmsPage /> },
                  { path: paths.settings, element: <ProfileSettingsPage /> },
                  { path: paths.notifications, element: <NotificationsPage /> },
                  { path: paths.notificationSettings, element: <NotificationSettingsPage /> },
                  { path: paths.credits, element: <CreditsPage /> },
                ],
              },
            ],
          },
        ],
      },
      {
        element: <PublicAppLayout />,
        children: [
          { path: paths.styleGuide, element: <StyleGuide /> },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
];
