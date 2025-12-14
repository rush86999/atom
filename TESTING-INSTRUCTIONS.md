# ATOM Application Testing Instructions

## Quick Start Guide

### 1. Fix Critical Issues First

Before you can properly test the application, you need to fix the critical dependency issues:

**Windows Users:**
```bash
cd C:\Users\Rish\projects\atom
fix-atom-app.bat
```

**Linux/Mac Users:**
```bash
cd /path/to/atom
chmod +x fix-atom-app.sh
./fix-atom-app.sh
```

### 2. Start the Application

After running the fix script:

1. **Start Frontend:**
   ```bash
   cd frontend-nextjs
   npm run dev
   ```

2. **Ensure Backend is Running:**
   - Backend should be running on port 5059
   - Check: http://localhost:5059/health

### 3. Run Automated Tests

Once the application is running without errors:

```bash
cd C:\Users\Rish\projects\atom
node test-atom-app.js
```

### 4. Manual Testing Checklist

Use the comprehensive manual testing guide:

- Open: `manual-testing-checklist.md`
- Go through each section systematically
- Document any issues found

---

## Testing Tools Setup

### Browser DevTools
1. Open Chrome DevTools (F12)
2. Check Console tab for JavaScript errors
3. Check Network tab for failed requests
4. Check Elements tab for DOM issues

### Lighthouse (Optional)
```bash
npm install -g lighthouse
lighthouse http://localhost:3000 --view
```

### Accessibility Testing
1. Install Chrome Extensions:
   - WAVE Evaluation Tool
   - axe DevTools
   - Color Contrast Analyzer

---

## Common Issues & Solutions

### 1. Module Resolution Errors
**Problem:** `Module not found: Can't resolve '@/...'`
**Solution:** Check tsconfig.json paths configuration

### 2. Port Conflicts
**Problem:** Port 3000 or 5059 already in use
**Solution:**
```bash
# Kill processes on ports
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

### 3. CORS Issues
**Problem:** Frontend can't connect to backend
**Solution:** Check backend CORS configuration

### 4. Environment Variables
**Problem:** API endpoints not working
**Solution:** Check .env.local configuration

---

## Testing Scenarios

### Authentication Testing
1. Try to access protected pages without logging in
2. Test login with invalid credentials
3. Test social login buttons
4. Test password reset flow
5. Test logout functionality

### Feature Testing
1. **Dashboard:**
   - Check if widgets load
   - Test data refresh
   - Test interactions

2. **Tasks:**
   - Create new task
   - Edit existing task
   - Delete task
   - Test filters and search

3. **Automations:**
   - Create new automation
   - Test automation triggers
   - Check automation history

4. **Integrations:**
   - Test connecting to services
   - Test OAuth flows
   - Test webhook configurations

### Responsive Testing
1. **Mobile (375x667):**
   - Test all major features
   - Check navigation
   - Test touch interactions

2. **Tablet (768x1024):**
   - Test layout adjustments
   - Test touch vs mouse interactions

3. **Desktop (1920x1080):**
   - Test full functionality
   - Test keyboard shortcuts

### Error Handling Testing
1. **Network Errors:**
   - Disconnect network
   - Slow network simulation
   - Server unavailable

2. **Invalid Data:**
   - Submit empty forms
   - Submit invalid data
   - Test server error responses

3. **Edge Cases:**
   - Very long text inputs
   - Special characters
   - Unicode support

---

## Performance Testing

### 1. Page Load Time
- Use browser DevTools Network tab
- Measure Time to Interactive
- Check Largest Contentful Paint

### 2. Bundle Size
```bash
npm run build
npm run analyze
```

### 3. Memory Usage
- Monitor Chrome DevTools Memory tab
- Check for memory leaks on page navigation

---

## Security Testing

### 1. Basic Security Checks
- Test for XSS in input fields
- Check for CSRF tokens
- Verify HTTPS redirects
- Test input validation

### 2. Authentication Security
- Test session management
- Check password policies
- Test rate limiting

---

## Reporting Issues

For each issue found, create a report with:

```markdown
## Issue Title
**Severity:** Critical/Major/Minor
**Location:** Page/Component
**Browser:** Chrome/Firefox/Safari
**Device:** Desktop/Mobile/Tablet

### Description
Detailed description of the issue

### Steps to Reproduce
1. Go to...
2. Click on...
3. Observe...

### Expected Behavior
What should happen

### Actual Behavior
What actually happens

### Screenshots/Videos
Attach visual evidence

### Console Errors
Copy any console errors

### Additional Notes
Any other relevant information
```

---

## Continuous Testing

### Set Up Pre-commit Hooks
```bash
npm install --save-dev husky lint-staged
npx husky install
```

### Automated CI/CD Testing
- GitHub Actions for automated testing
- Lighthouse CI for performance
- Accessibility testing with axe

---

## Next Steps After Initial Testing

1. **Priority 1:** Fix all critical and major issues found
2. **Priority 2:** Implement missing features
3. **Priority 3:** Improve performance and accessibility
4. **Priority 4:** Add comprehensive test coverage
5. **Priority 5:** Optimize for production deployment

---

## Contact & Support

If you encounter issues during testing:

1. Check this documentation
2. Review the console for errors
3. Check the backend logs
4. Consult the development team

Remember: Good testing is about finding bugs early and providing clear, actionable feedback!