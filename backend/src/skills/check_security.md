# Check Security Skill

You are tasked with performing a security review of code.

## Instructions

1. Scan for common security vulnerabilities
2. Check for OWASP Top 10 issues
3. Identify potential attack vectors
4. Assess data handling practices
5. Review authentication/authorization logic

## Security Checklist

### OWASP Top 10
- [ ] Injection (SQL, Command, LDAP)
- [ ] Broken Authentication
- [ ] Sensitive Data Exposure
- [ ] XML External Entities (XXE)
- [ ] Broken Access Control
- [ ] Security Misconfiguration
- [ ] Cross-Site Scripting (XSS)
- [ ] Insecure Deserialization
- [ ] Using Components with Known Vulnerabilities
- [ ] Insufficient Logging & Monitoring

### Additional Checks
- [ ] Input validation
- [ ] Output encoding
- [ ] Secret management
- [ ] Error handling (no sensitive info leakage)
- [ ] Rate limiting considerations

## Input Parameters

- `code`: The code to review
- `context`: Type of application (web, API, CLI)
- `focus`: Specific security concerns

## Output Format

1. **Risk Summary**: Overall security posture
2. **Vulnerabilities Found**: List with severity (Critical, High, Medium, Low)
3. **Recommendations**: How to fix each issue
4. **Best Practices**: Additional security improvements
