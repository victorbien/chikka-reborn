import { Component, type ReactNode } from "react";
import { ErrorState } from "@/components/shared/ErrorState";
import { reportError } from "@/lib/error-handling";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/** Last-resort guard so a render crash shows a readable message, not a blank page. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error): void {
    reportError(error, "render");
  }

  private readonly reset = (): void => {
    this.setState({ hasError: false });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <ErrorState
          message="The page failed to display. Your data is safe. Try again, or reload the page."
          onRetry={this.reset}
        />
      );
    }
    return this.props.children;
  }
}
