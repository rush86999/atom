/**
 * Comprehensive Browser Testing Script for ATOM Application
 * This script will test various aspects of the ATOM web application
 *
 * To run: node test-atom-app.js
 * Prerequisites: npm install puppeteer
 */

const puppeteer = require('puppeteer');
const fs = require('fs');

class AtomAppTester {
    constructor() {
        this.baseUrl = 'http://localhost:3000';
        this.issues = [];
        this.screenshots = [];
        this.browser = null;
        this.page = null;
    }

    async init() {
        console.log('🚀 Starting ATOM Application Testing...\n');

        this.browser = await puppeteer.launch({
            headless: false, // Set to true for headless mode
            defaultViewport: { width: 1920, height: 1080 },
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        });

        this.page = await this.browser.newPage();

        // Enable console logging
        this.page.on('console', msg => {
            console.log('Browser Console:', msg.text());
            if (msg.type() === 'error') {
                this.addIssue('JavaScript Error', 'Console', 'major', msg.text(), 'N/A');
            }
        });

        // Enable request monitoring
        this.page.on('response', response => {
            if (response.status() >= 400) {
                this.addIssue(
                    `HTTP Error ${response.status()}`,
                    response.url(),
                    'major',
                    `Failed request: ${response.status()} ${response.statusText()}`,
                    'N/A'
                );
            }
        });
    }

    async takeScreenshot(name, description = '') {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `screenshots/${name}_${timestamp}.png`;

        // Ensure screenshots directory exists
        if (!fs.existsSync('screenshots')) {
            fs.mkdirSync('screenshots');
        }

        await this.page.screenshot({ path: filename, fullPage: true });
        this.screenshots.push({ filename, description, timestamp });
        console.log(`📸 Screenshot saved: ${filename}`);
        return filename;
    }

    addIssue(title, location, severity, description, steps) {
        this.issues.push({
            title,
            location,
            severity,
            description,
            steps,
            timestamp: new Date().toISOString()
        });
        console.log(`\n❌ Issue Found: ${title}`);
        console.log(`   Location: ${location}`);
        console.log(`   Severity: ${severity}`);
        console.log(`   Description: ${description}`);
    }

    async testPageLoad() {
        console.log('\n📍 Testing Page Load...');

        try {
            const response = await this.page.goto(this.baseUrl, { waitUntil: 'networkidle2' });

            if (response.status() !== 200) {
                this.addIssue(
                    'Page Load Error',
                    this.baseUrl,
                    'critical',
                    `Page returned status ${response.status()}`,
                    'Navigate to homepage'
                );
            }

            // Check for page title
            const title = await this.page.title();
            if (!title || title.trim() === '') {
                this.addIssue(
                    'Missing Page Title',
                    'Homepage',
                    'minor',
                    'Page title is empty or missing',
                    'Check homepage title element'
                );
            }

            await this.takeScreenshot('homepage_load', 'Initial page load');

        } catch (error) {
            this.addIssue(
                'Page Load Failure',
                this.baseUrl,
                'critical',
                `Failed to load page: ${error.message}`,
                'Navigate to homepage'
            );
        }
    }

    async testAuthenticationFlow() {
        console.log('\n🔐 Testing Authentication Flow...');

        // Check if redirected to signin
        const currentUrl = this.page.url();
        if (currentUrl.includes('/auth/signin')) {
            console.log('✅ Correctly redirected to authentication');

            await this.takeScreenshot('auth_page', 'Authentication page');

            // Test form elements
            const emailInput = await this.page.$('input[type="email"]');
            const passwordInput = await this.page.$('input[type="password"]');
            const submitButton = await this.page.$('button[type="submit"]');

            if (!emailInput) {
                this.addIssue(
                    'Missing Email Input',
                    'Authentication Page',
                    'critical',
                    'Email input field not found',
                    'Check signin form'
                );
            }

            if (!passwordInput) {
                this.addIssue(
                    'Missing Password Input',
                    'Authentication Page',
                    'critical',
                    'Password input field not found',
                    'Check signin form'
                );
            }

            if (!submitButton) {
                this.addIssue(
                    'Missing Submit Button',
                    'Authentication Page',
                    'critical',
                    'Submit button not found',
                    'Check signin form'
                );
            }

            // Test social login buttons
            const googleButton = await this.page.$('button:has-text("Google")');
            const githubButton = await this.page.$('button:has-text("GitHub")');

            if (!googleButton) {
                this.addIssue(
                    'Missing Google Login',
                    'Authentication Page',
                    'major',
                    'Google OAuth button not found',
                    'Check social login options'
                );
            }

            if (!githubButton) {
                this.addIssue(
                    'Missing GitHub Login',
                    'Authentication Page',
                    'major',
                    'GitHub OAuth button not found',
                    'Check social login options'
                );
            }

            // Test form validation
            if (emailInput && submitButton) {
                await emailInput.click();
                await emailInput.type('invalid-email');
                await submitButton.click();
                await this.page.waitForTimeout(1000);

                const hasValidationError = await this.page.$('.text-red-800, .border-red-200');
                if (hasValidationError) {
                    console.log('✅ Form validation working correctly');
                } else {
                    this.addIssue(
                        'No Form Validation',
                        'Authentication Page',
                        'major',
                        'Email validation not working',
                        'Submit invalid email and check for error message'
                    );
                }
            }
        }
    }

    async testResponsiveDesign() {
        console.log('\n📱 Testing Responsive Design...');

        const viewports = [
            { name: 'Mobile', width: 375, height: 667 },
            { name: 'Tablet', width: 768, height: 1024 },
            { name: 'Desktop', width: 1920, height: 1080 }
        ];

        for (const viewport of viewports) {
            await this.page.setViewport(viewport);
            await this.page.waitForTimeout(500);

            await this.takeScreenshot(`responsive_${viewport.name.toLowerCase()}`, `Responsive test - ${viewport.name}`);

            // Check for horizontal scroll
            const hasHorizontalScroll = await this.page.evaluate(() => {
                return document.body.scrollWidth > document.body.clientWidth;
            });

            if (hasHorizontalScroll) {
                this.addIssue(
                    'Horizontal Scroll',
                    `Responsive - ${viewport.name}`,
                    'major',
                    'Page has horizontal scroll on this viewport',
                    `Test on ${viewport.name} viewport`
                );
            }

            // Check if elements are properly sized
            const elementsTooSmall = await this.page.evaluate(() => {
                const buttons = document.querySelectorAll('button, a');
                return Array.from(buttons).filter(btn => {
                    const rect = btn.getBoundingClientRect();
                    return rect.height < 44 || rect.width < 44; // Minimum touch target size
                }).length;
            });

            if (elementsTooSmall > 0 && viewport.name === 'Mobile') {
                this.addIssue(
                    'Touch Targets Too Small',
                    `Responsive - ${viewport.name}`,
                    'major',
                    `${elementsTooSmall} buttons/links are smaller than 44x44px`,
                    'Check button sizes on mobile'
                );
            }
        }

        // Reset to desktop
        await this.page.setViewport({ width: 1920, height: 1080 });
    }

    async testAccessibility() {
        console.log('\n♿ Testing Accessibility...');

        // Check for alt text on images
        const imagesWithoutAlt = await this.page.$$eval('img:not([alt])', imgs => imgs.length);
        if (imagesWithoutAlt > 0) {
            this.addIssue(
                'Missing Alt Text',
                'Images',
                'major',
                `${imagesWithoutAlt} images missing alt attributes`,
                'Add alt text to all images'
            );
        }

        // Check for proper heading structure
        const headings = await this.page.$$eval('h1, h2, h3, h4, h5, h6', headings => {
            return headings.map(h => ({ tag: h.tagName, text: h.textContent.trim() }));
        });

        if (headings.length === 0) {
            this.addIssue(
                'No Headings',
                'Page Structure',
                'major',
                'No heading elements found on page',
                'Add proper heading structure'
            );
        }

        // Check for ARIA labels on interactive elements
        const buttonsWithoutAria = await this.page.$$eval('button:not([aria-label]):not([aria-labelledby])', buttons => {
            return buttons.filter(btn => !btn.textContent.trim()).length;
        });

        if (buttonsWithoutAria > 0) {
            this.addIssue(
                'Missing ARIA Labels',
                'Buttons',
                'minor',
                `${buttonsWithoutAria} buttons without text or aria-label`,
                'Add aria-label to icon buttons'
            );
        }

        // Check color contrast (basic check)
        const lowContrastElements = await this.page.evaluate(() => {
            const elements = document.querySelectorAll('*');
            const lowContrast = [];

            elements.forEach(el => {
                const styles = window.getComputedStyle(el);
                const color = styles.color;
                const backgroundColor = styles.backgroundColor;

                // Simple check for light text on light background or vice versa
                if (color && backgroundColor &&
                    color !== 'rgba(0, 0, 0, 0)' &&
                    backgroundColor !== 'rgba(0, 0, 0, 0)') {
                    // This is a simplified check - real contrast calculation is more complex
                    lowContrast.push({ element: el.tagName, color, backgroundColor });
                }
            });

            return lowContrast.length;
        });
    }

    async testNavigation() {
        console.log('\n🧭 Testing Navigation...');

        // Try to access authenticated pages without login
        const protectedPages = [
            '/dashboard',
            '/automations',
            '/agents',
            '/tasks',
            '/integrations'
        ];

        for (const page of protectedPages) {
            try {
                await this.page.goto(`${this.baseUrl}${page}`, { waitUntil: 'networkidle2' });
                await this.page.waitForTimeout(1000);

                const currentUrl = this.page.url();

                if (!currentUrl.includes('/auth/signin')) {
                    this.addIssue(
                        'Authentication Bypass',
                        page,
                        'critical',
                        'Protected page accessible without authentication',
                        `Access ${page} without login`
                    );
                }
            } catch (error) {
                this.addIssue(
                    'Page Load Error',
                    page,
                    'major',
                    `Failed to load ${page}: ${error.message}`,
                    `Navigate to ${page}`
                );
            }
        }
    }

    async testPerformance() {
        console.log('\n⚡ Testing Performance...');

        const metrics = await this.page.metrics();

        if (metrics.LayoutDuration > 100) {
            this.addIssue(
                'Slow Layout',
                'Performance',
                'minor',
                `Layout duration: ${metrics.LayoutDuration}ms (>100ms)`,
                'Optimize CSS and layout calculations'
            );
        }

        if (metrics.ScriptDuration > 200) {
            this.addIssue(
                'Slow JavaScript',
                'Performance',
                'minor',
                `Script duration: ${metrics.ScriptDuration}ms (>200ms)`,
                'Optimize JavaScript execution'
            );
        }

        // Check for large resources
        const resources = await this.page.evaluate(() => {
            return performance.getEntriesByType('resource').map(r => ({
                name: r.name,
                size: r.transferSize || 0
            }));
        });

        const largeResources = resources.filter(r => r.size > 1024 * 1024); // > 1MB
        if (largeResources.length > 0) {
            this.addIssue(
                'Large Resources',
                'Performance',
                'minor',
                `${largeResources.length} resources larger than 1MB`,
                'Optimize images and other large resources'
            );
        }
    }

    async testErrorHandling() {
        console.log('\n🚨 Testing Error Handling...');

        // Test 404 page
        await this.page.goto(`${this.baseUrl}/non-existent-page`, { waitUntil: 'networkidle2' });
        await this.page.waitForTimeout(1000);

        const has404Content = await this.page.evaluate(() => {
            return document.body.textContent.toLowerCase().includes('404') ||
                   document.body.textContent.toLowerCase().includes('not found');
        });

        if (!has404Content) {
            this.addIssue(
                'Poor 404 Handling',
                'Error Pages',
                'minor',
                'No proper 404 page or message',
                'Navigate to non-existent page'
            );
        }

        await this.takeScreenshot('404_page', '404 error page');
    }

    generateReport() {
        console.log('\n📊 Generating Test Report...\n');

        // Group issues by severity
        const issuesBySeverity = {
            critical: this.issues.filter(i => i.severity === 'critical'),
            major: this.issues.filter(i => i.severity === 'major'),
            minor: this.issues.filter(i => i.severity === 'minor')
        };

        const report = {
            timestamp: new Date().toISOString(),
            summary: {
                totalIssues: this.issues.length,
                critical: issuesBySeverity.critical.length,
                major: issuesBySeverity.major.length,
                minor: issuesBySeverity.minor.length,
                screenshots: this.screenshots.length
            },
            issues: this.issues,
            screenshots: this.screenshots,
            recommendations: this.getRecommendations(issuesBySeverity)
        };

        // Save report
        const reportPath = `test-report-${Date.now()}.json`;
        fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

        // Print summary
        console.log('='.repeat(60));
        console.log('📋 ATOM Application Test Report');
        console.log('='.repeat(60));
        console.log(`\n📊 Summary:`);
        console.log(`   Total Issues: ${report.summary.totalIssues}`);
        console.log(`   🔴 Critical: ${report.summary.critical}`);
        console.log(`   🟠 Major: ${report.summary.major}`);
        console.log(`   🟡 Minor: ${report.summary.minor}`);
        console.log(`   📸 Screenshots: ${report.summary.screenshots}`);

        if (report.summary.totalIssues > 0) {
            console.log(`\n🚨 Critical Issues (Fix Immediately):`);
            issuesBySeverity.critical.forEach(issue => {
                console.log(`   • ${issue.title} - ${issue.location}`);
            });

            console.log(`\n⚠️  Major Issues (Fix Soon):`);
            issuesBySeverity.major.forEach(issue => {
                console.log(`   • ${issue.title} - ${issue.location}`);
            });

            console.log(`\n💡 Minor Issues (Nice to Have):`);
            issuesBySeverity.minor.forEach(issue => {
                console.log(`   • ${issue.title} - ${issue.location}`);
            });
        }

        console.log(`\n📁 Report saved to: ${reportPath}`);
        console.log(`📁 Screenshots saved to: ./screenshots/`);

        return report;
    }

    getRecommendations(issuesBySeverity) {
        const recommendations = [];

        if (issuesBySeverity.critical.length > 0) {
            recommendations.push('🚨 CRITICAL: Fix authentication bypasses immediately');
            recommendations.push('🔒 SECURITY: Review and secure protected routes');
        }

        if (issuesBySeverity.major.length > 0) {
            recommendations.push('📱 UX: Improve mobile responsiveness');
            recommendations.push('♿ ACCESSIBILITY: Add proper ARIA labels and alt text');
        }

        if (issuesBySeverity.minor.length > 0) {
            recommendations.push('⚡ PERFORMANCE: Optimize resource loading');
            recommendations.push('🎨 UI: Polish visual elements and interactions');
        }

        return recommendations;
    }

    async runAllTests() {
        await this.init();

        try {
            await this.testPageLoad();
            await this.testAuthenticationFlow();
            await this.testNavigation();
            await this.testResponsiveDesign();
            await this.testAccessibility();
            await this.testPerformance();
            await this.testErrorHandling();

            const report = this.generateReport();

            return report;
        } finally {
            await this.browser.close();
        }
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    const tester = new AtomAppTester();
    tester.runAllTests().catch(console.error);
}

module.exports = AtomAppTester;