# Repair Policy

When an artifact is invalid or incomplete:

1. Identify the broken artifact and the evidence.
2. Fix the smallest affected file or generation step.
3. Re-run the validator that caught the issue.
4. Record the repair in the run notes.

Never repair a production database by mutation. Production access remains SELECT only.
