/**
 * LoadingSpinner Component - Shared loading indicator
 */

import { Spinner, SpinnerProps } from '@chakra-ui/react';

interface LoadingSpinnerProps extends SpinnerProps {
  label?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Loading...',
  ...props
}) => {
  return <Spinner label={label} {...props} />;
};