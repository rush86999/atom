import React from "react";
import { useRouter } from "next/router";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle, Home, RefreshCw } from "lucide-react";

export default function AuthError() {
  const router = useRouter();
  const { error } = router.query;

  const getErrorMessage = (errorType: string) => {
    switch (errorType) {
      case "Configuration":
        return "There is a problem with the server configuration. Please contact support.";
      case "AccessDenied":
        return "Access denied. You do not have permission to sign in.";
      case "Verification":
        return "The verification link has expired or has already been used.";
      case "Default":
      default:
        return "An unexpected error occurred during authentication. Please try again.";
    }
  };

  const errorMessage = getErrorMessage(error as string);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 to-orange-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center mb-4">
            <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-white mb-2">
            Authentication Error
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            There was a problem signing you in
          </p>
        </div>

        {/* Error Alert */}
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Authentication Failed</AlertTitle>
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>

        {/* Action Buttons */}
        <div className="space-y-3">
          <Button
            className="w-full h-12 text-base gap-2"
            onClick={() => router.push("/auth/signin")}
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </Button>

          <Button
            variant="outline"
            className="w-full h-12 text-base gap-2"
            onClick={() => router.push("/")}
          >
            <Home className="w-4 h-4" />
            Return Home
          </Button>
        </div>

        <div className="text-center">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            If this problem persists, please contact support.
          </p>
        </div>
      </div>
    </div>
  );
}
