# Property Tax Appeal Forge

When the user asks about appealing a property tax assessment, checking if their assessment is too high, or analyzing a King County WA property address — run the pipeline scripts in order:

```bash
bash scripts/setup.sh                              # one-time extract download
bash scripts/run_appeal.sh "<address>"              # full pipeline
```

Or step by step:
```bash
python3 scripts/resolve_parcel.py "<address>" run/<PIN>
python3 scripts/fetch_account_value.py <PIN> run/<PIN>
python3 scripts/fetch_comps.py run/<PIN>
python3 scripts/adjust_and_value.py run/<PIN>
python3 scripts/case_test.py run/<PIN>
python3 scripts/build_packet.py run/<PIN>           # only if case_test says GO
```

Present the decision.json summary to the user. If GO, show the evidence_packet.md and petition.json fields. Always surface the disclaimers from references/disclaimers.md.
