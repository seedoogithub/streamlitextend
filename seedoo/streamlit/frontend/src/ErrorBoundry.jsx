import React, { Component } from 'react';

class ErrorBoundry extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorMessage: '', errorStack: '' };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, errorMessage: error.toString() };
  }

  componentDidCatch(error, errorInfo) {
    // You can also log the error to an error reporting service
    console.log(error, errorInfo);
    this.setState({ errorStack: errorInfo.componentStack }); // Save the stack trace in the state
  }

  render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      return (
        <div>
          <h1>{`Something went wrong: ${this.state.errorMessage}`}</h1>
          <pre>{this.state.errorStack}</pre> {/* Render the stack trace */}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundry;
