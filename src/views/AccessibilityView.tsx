import React, { useState, FC } from 'react';
import { useToast } from '../components/NotificationSystem';

interface AccessibilityOption {
    id: string;
    name: string;
    description: string;
    enabled: boolean;
    category: string;
}

// Accessibility Feature Card Component
const AccessibilityFeatureCard: FC<{
    option: AccessibilityOption;
    onChange: (id: string, enabled: boolean) => void;
}> = ({ option, onChange }) => {
    return (
        <div className="accessibility-feature">
            <div className="feature-content">
                <h4>{option.name}</h4>
                <p>{option.description}</p>
            </div>
            <label className="toggle-switch">
                <input
                    type="checkbox"
                    checked={option.enabled}
                    onChange={(e) => onChange(option.id, e.target.checked)}
                />
                <span className="slider"></span>
            </label>
        </div>
    );
};

export const AccessibilityView = () => {
    const { success, info } = useToast();
    const [accessibilityOptions, setAccessibilityOptions] = useState<AccessibilityOption[]>([
        // Visual
        {
            id: 'high-contrast',
            name: 'High Contrast Mode',
            description: 'Increase contrast throughout the interface',
            enabled: false,
            category: 'Visual'
        },
        {
            id: 'large-text',
            name: 'Large Text',
            description: 'Increase font size globally',
            enabled: false,
            category: 'Visual'
        },
        {
            id: 'reduce-motion',
            name: 'Reduce Motion',
            description: 'Minimize animations and transitions',
            enabled: false,
            category: 'Visual'
        },
        {
            id: 'color-blind',
            name: 'Color Blind Mode',
            description: 'Optimize colors for color blindness',
            enabled: false,
            category: 'Visual'
        },
        // Audio
        {
            id: 'captions',
            name: 'Show Captions',
            description: 'Display captions for audio and video content',
            enabled: true,
            category: 'Audio'
        },
        {
            id: 'audio-descriptions',
            name: 'Audio Descriptions',
            description: 'Play audio descriptions for visual content',
            enabled: false,
            category: 'Audio'
        },
        // Navigation
        {
            id: 'keyboard-nav',
            name: 'Keyboard Navigation',
            description: 'Navigate using keyboard only',
            enabled: true,
            category: 'Navigation'
        },
        {
            id: 'focus-indicator',
            name: 'Enhanced Focus Indicator',
            description: 'Show clear focus outlines for keyboard navigation',
            enabled: true,
            category: 'Navigation'
        },
        {
            id: 'skip-links',
            name: 'Skip Links',
            description: 'Jump directly to main content areas',
            enabled: true,
            category: 'Navigation'
        },
        // Speech
        {
            id: 'text-to-speech',
            name: 'Text to Speech',
            description: 'Read page content aloud',
            enabled: false,
            category: 'Speech'
        },
        {
            id: 'voice-control',
            name: 'Voice Control',
            description: 'Control interface using voice commands',
            enabled: false,
            category: 'Speech'
        }
    ]);

    const [fontSize, setFontSize] = useState<'small' | 'medium' | 'large'>('medium');
    const [activeCategory, setActiveCategory] = useState<string>('All');

    const categories = ['All', ...Array.from(new Set(accessibilityOptions.map(o => o.category)))];

    const handleAccessibilityChange = (id: string, enabled: boolean) => {
        setAccessibilityOptions(prev =>
            prev.map(option => option.id === id ? { ...option, enabled } : option)
        );
        const option = accessibilityOptions.find(o => o.id === id);
        if (option) {
            success('Setting Updated', `${option.name} ${enabled ? 'enabled' : 'disabled'}`);
        }
    };

    const filteredOptions = activeCategory === 'All'
        ? accessibilityOptions
        : accessibilityOptions.filter(o => o.category === activeCategory);

    return (
        <div className="accessibility-view">
            <header className="view-header">
                <h1>Accessibility</h1>
                <p>Customize your experience for better accessibility.</p>
            </header>

            <div className="accessibility-content">
                <aside className="accessibility-sidebar">
                    <div className="font-size-control">
                        <h3>Font Size</h3>
                        <div className="size-buttons">
                            <button
                                className={`size-btn ${fontSize === 'small' ? 'active' : ''}`}
                                onClick={() => {
                                    setFontSize('small');
                                    success('Font Size', 'Small text applied');
                                }}
                            >
                                A
                            </button>
                            <button
                                className={`size-btn ${fontSize === 'medium' ? 'active' : ''}`}
                                onClick={() => {
                                    setFontSize('medium');
                                    success('Font Size', 'Medium text applied');
                                }}
                            >
                                <strong>A</strong>
                            </button>
                            <button
                                className={`size-btn ${fontSize === 'large' ? 'active' : ''}`}
                                onClick={() => {
                                    setFontSize('large');
                                    success('Font Size', 'Large text applied');
                                }}
                            >
                                <strong style={{ fontSize: '1.2em' }}>A</strong>
                            </button>
                        </div>
                    </div>

                    <div className="category-filter">
                        <h3>Categories</h3>
                        <div className="category-buttons">
                            {categories.map(cat => (
                                <button
                                    key={cat}
                                    className={`category-btn ${activeCategory === cat ? 'active' : ''}`}
                                    onClick={() => setActiveCategory(cat)}
                                >
                                    {cat}
                                </button>
                            ))}
                        </div>
                    </div>
                </aside>

                <main className="accessibility-main">
                    <section className="features-section">
                        <h2>{activeCategory === 'All' ? 'All Features' : activeCategory}</h2>
                        <div className="features-grid">
                            {filteredOptions.map(option => (
                                <AccessibilityFeatureCard
                                    key={option.id}
                                    option={option}
                                    onChange={handleAccessibilityChange}
                                />
                            ))}
                        </div>
                    </section>

                    <section className="help-section">
                        <h3>📖 Help & Resources</h3>
                        <div className="help-resources">
                            <div className="resource-item">
                                <h4>🎯 Screen Reader Support</h4>
                                <p>This application supports popular screen readers like NVDA, JAWS, and VoiceOver.</p>
                                <a href="#">Learn more</a>
                            </div>
                            <div className="resource-item">
                                <h4>⌨️ Keyboard Shortcuts</h4>
                                <p>Navigate and control the application entirely using your keyboard.</p>
                                <a href="#">View keyboard shortcuts</a>
                            </div>
                            <div className="resource-item">
                                <h4>♿ Accessibility Statement</h4>
                                <p>Read our full commitment to web accessibility standards.</p>
                                <a href="#">View statement</a>
                            </div>
                            <div className="resource-item">
                                <h4>🐛 Report an Issue</h4>
                                <p>Found an accessibility issue? Help us improve by reporting it.</p>
                                <a href="#">Report issue</a>
                            </div>
                        </div>
                    </section>

                    <section className="wcag-compliance">
                        <h3>✅ WCAG Compliance</h3>
                        <div className="compliance-info">
                            <p>This application meets <strong>WCAG 2.1 Level AA</strong> accessibility standards.</p>
                            <div className="compliance-details">
                                <div className="detail-item">
                                    <span className="check">✓</span>
                                    <span>Perceivable - Information and user interface components are presentable</span>
                                </div>
                                <div className="detail-item">
                                    <span className="check">✓</span>
                                    <span>Operable - All functionality is available from a keyboard</span>
                                </div>
                                <div className="detail-item">
                                    <span className="check">✓</span>
                                    <span>Understandable - Text is readable and pages operate predictably</span>
                                </div>
                                <div className="detail-item">
                                    <span className="check">✓</span>
                                    <span>Robust - Compatible with assistive technologies</span>
                                </div>
                            </div>
                        </div>
                    </section>
                </main>
            </div>
        </div>
    );
};
