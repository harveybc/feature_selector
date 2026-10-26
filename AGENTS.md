# Agent instructions

Read README.md, docs/PLUGIN_API.md and docs/INTEGRATION_MAP.md. This repository
owns the plugin coordinator and generic subset search. Existing scientific
engines remain in their repositories; do not duplicate their implementations.

- New package smoke: install -e '.[test]', run examples/plugin_demo.json on CPU,
  inspect all receipts and repeat it to verify resume; then run pytest.
- Use entry points for external plugins, and preserve typed JSON merge precedence.
  Plugin defaults < application defaults < file < explicit CLI. Unknown options fail.
- Real RL requires the actual model runner, structural pruning and native receipts.
  Never substitute the synthetic demo or a proxy classifier for its evaluator.
- All causal_selection stages are mandatory. Do not fabricate stage evidence,
  imply NOT_IDENTIFIED means no causal effect, or omit coding/extractor contrasts.
- Preserve no-state-feedback, fixed TRAIN scaling, no clipping, paired support,
  TRAIN-only fitting and no TEST access. No live campaigns or GPU launch by default.
- Read PROJECT_METHOD_STATE.json and keep tests, verification and scope current.

Legacy phase-2/3 example instructions:

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
