# Agent instructions

Read README.md and docs/PORTABILITY.md. This repository documents and exercises
existing selection engines; it does not own their scientific implementations.

- Use upstream.lock.json and a separate, clean predictor checkout. Never swap
  its pinned revision for master silently.
- Run the small synthetic example in a new local directory. `run` resumes;
  `status` computes a snapshot without launching tasks. Let scripts finish and
  report closure artifacts rather than repeatedly polling logs.
- Keep CPU numeric threads at one for the demo. It uses no GPU or production
  services. Real populations require measured memory/cost before scaling.
- Read REPORT.json and both campaign closure files, then check the local cube.
  Filters are candidate generators; the final feature selection requires
  predictive validation in the target domain.
- Preserve input hashes, seed, unsupported/undefined results and causal
  assumptions. NOT_IDENTIFIED cannot be converted to causal absence.
- New domains: map availability, units, targets and split/retraining contracts
  first. Consult the capability table before promising config-only support.
- Keep analytical databases, input data, credentials and host addresses outside
  Git. Commit scripts, configs, manifests, tests and small verification records.
- Make improvements in the owning repository, then update the pin only after
  its real integration test passes. No copied scientific engine implementations.
