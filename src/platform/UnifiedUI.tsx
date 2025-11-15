import React from 'react';
import { UnifiedPlatform, platform, featureFlags } from './UnifiedPlatform';

// Unified UI component props
export interface UnifiedUIProps {
  children?: React.ReactNode;
  className?: string;
  platform?: 'desktop' | 'web' | 'auto';
}

// Button component with platform-appropriate styling
export interface ButtonProps extends UnifiedUIProps {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void;
  type?: 'button' | 'submit' | 'reset';
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  onClick,
  type = 'button',
  className = '',
  platform: forcePlatform,
}) => {
  const currentPlatform = forcePlatform || platform.getPlatform();
  const isDesktop = currentPlatform === 'desktop';

  const baseClasses = `unified-button ${isDesktop ? 'desktop' : 'web'} ${variant} ${size} ${className}`;

  return (
    <button
      type={type}
      className={baseClasses}
      disabled={disabled || loading}
      onClick={onClick}
      data-platform={currentPlatform}
      data-variant={variant}
      data-size={size}
    >
      {loading && <span className="loading-spinner" />}
      {children}
    </button>
  );
};

// Card component with platform-appropriate styling
export interface CardProps extends UnifiedUIProps {
  variant?: 'default' | 'elevated' | 'outlined';
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  padding = 'md',
  className = '',
  platform: forcePlatform,
}) => {
  const currentPlatform = forcePlatform || platform.getPlatform();
  const isDesktop = currentPlatform === 'desktop';

  const baseClasses = `unified-card ${isDesktop ? 'desktop' : 'web'} ${variant} padding-${padding} ${className}`;

  return (
    <div className={baseClasses} data-platform={currentPlatform}>
      {children}
    </div>
  );
};

// Input component with platform-appropriate styling
export interface InputProps extends UnifiedUIProps {
  type?: 'text' | 'email' | 'password' | 'number' | 'search';
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
  error?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const Input: React.FC<InputProps> = ({
  type = 'text',
  placeholder,
  value,
  onChange,
  disabled = false,
  error = false,
  size = 'md',
  className = '',
  platform: forcePlatform,
}) => {
  const currentPlatform = forcePlatform || platform.getPlatform();
  const isDesktop = currentPlatform === 'desktop';

  const baseClasses = `unified-input ${isDesktop ? 'desktop' : 'web'} ${size} ${error ? 'error' : ''} ${className}`;

  return (
    <input
      type={type}
      className={baseClasses}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
      disabled={disabled}
      data-platform={currentPlatform}
      data-size={size}
    />
  );
};

// Modal component with platform-appropriate behavior
export interface ModalProps extends UnifiedUIProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
  className = '',
  platform: forcePlatform,
}) => {
  const currentPlatform = forcePlatform || platform.getPlatform();
  const isDesktop = currentPlatform === 'desktop';

  if (!isOpen) return null;

  const baseClasses = `unified-modal ${isDesktop ? 'desktop' : 'web'} ${size} ${className}`;

  return (
    <div className="unified-modal-overlay" onClick={onClose}>
      <div className={baseClasses} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          {title && <h3 className="modal-title">{title}</h3>}
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-content">
          {children}
        </div>
      </div>
    </div>
  );
};

// Navigation component with platform-appropriate layout
export interface NavigationProps extends UnifiedUIProps {
  items: Array<{
    id: string;
    label: string;
    icon?: string;
    active?: boolean;
    onClick?: () => void;
  }>;
  orientation?: 'horizontal' | 'vertical';
}

export const Navigation: React.FC<NavigationProps> = ({
  items,
  orientation = 'horizontal',
  className = '',
  platform: forcePlatform,
}) => {
  const currentPlatform = forcePlatform || platform.getPlatform();
  const isDesktop = currentPlatform === 'desktop';

  // Use sidebar on desktop, bottom navigation on mobile web
  const effectiveOrientation = isDesktop ? 'vertical' : orientation;

  const baseClasses = `unified-navigation ${isDesktop ? 'desktop' : 'web'} ${effectiveOrientation} ${className}`;

  return (
    <nav className={baseClasses} data-platform={currentPlatform}>
      {items.map((item) => (
        <button
          key={item.id}
          className={`nav-item ${item.active ? 'active' : ''}`}
          onClick={item.onClick}
        >
          {item.icon && <span className="nav-icon">{item.icon}</span>}
          <span className="nav-label">{item.label}</span>
        </button>
      ))}
    </nav>
  );
};

// Feature-gated component wrapper
export interface FeatureGatedProps extends UnifiedUIProps {
  feature: keyof ReturnType<typeof featureFlags>;
  fallback?: React.ReactNode;
}

export const FeatureGated: React.FC<FeatureGatedProps> = ({
  feature,
  children,
  fallback = null,
}) => {
  const isAvailable = featureFlags[feature]();

  if (!isAvailable) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};

// Platform-aware layout component
export interface LayoutProps extends UnifiedUIProps {
  sidebar?: React.ReactNode;
  header?: React.ReactNode;
  footer?: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({
  sidebar,
  header,
  footer,
  children,
  className = '',
  platform: forcePlatform,
}) => {
  const currentPlatform = forcePlatform || platform.getPlatform();
  const isDesktop = currentPlatform === 'desktop';

  const baseClasses = `unified-layout ${isDesktop ? 'desktop' : 'web'} ${className}`;

  return (
    <div className={baseClasses} data-platform={currentPlatform}>
      {header && <header className="layout-header">{header}</header>}
      <div className="layout-body">
        {sidebar && isDesktop && (
          <aside className="layout-sidebar">{sidebar}</aside>
        )}
        <main className="layout-main">{children}</main>
      </div>
      {footer && <footer className="layout-footer">{footer}</footer>}
      {sidebar && !isDesktop && (
        <nav className="layout-bottom-nav">{sidebar}</nav>
      )}
    </div>
  );
};

// Integration status component
export interface IntegrationStatusProps extends UnifiedUIProps {
  integration: string;
  status: 'connected' | 'disconnected' | 'error' | 'loading';
  lastSync?: string;
}

export const IntegrationStatus: React.FC<IntegrationStatusProps> = ({
  integration,
  status,
  lastSync,
  className = '',
  platform: forcePlatform,
}) => {
  const currentPlatform = forcePlatform || platform.getPlatform();

  const statusIcons = {
    connected: '✅',
    disconnected: '🔌',
    error: '❌',
    loading: '⏳',
  };

  const baseClasses = `unified-integration-status ${currentPlatform} ${status} ${className}`;

  return (
    <div className={baseClasses} data-platform={currentPlatform}>
      <span className="status-icon">{statusIcons[status]}</span>
      <span className="integration-name">{integration}</span>
      {lastSync && <span className="last-sync">Last sync: {lastSync}</span>}
    </div>
  );
};

// Export all components
export const UnifiedUI = {
  Button,
  Card,
  Input,
  Modal,
  Navigation,
  FeatureGated,
  Layout,
  IntegrationStatus,
};

export default UnifiedUI;
