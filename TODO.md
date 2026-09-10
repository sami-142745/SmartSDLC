## SmartSDLC Run checklist

### Docker / runtime
- [ ] Ensure `.env` exists (copy from `.env.example`) and contains required vars
- [ ] Run `docker compose up --build`
- [ ] Verify backend responds: http://localhost:8000/docs
- [ ] Verify frontend responds: http://localhost:5173
- [ ] If startup fails, capture error output and patch the offending code/config

