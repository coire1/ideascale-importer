# Ideascale importer

```
Usage: main.py [OPTIONS]                                                                                                                                          

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --api-token              TEXT       Ideascale API token.                                                                 │
│ --fund                   INTEGER    Fund number. [default: 8]                                                            │
│ --fund-group-id          INTEGER    Ideascale Campaigns group id [default: 1]                                            │
│ --chain-vote-type        TEXT       Chain vote type [default: private]                                                   │
│ --threshold              INTEGER    Voting threshold [default: 450]                                                      │
│ --fund-goal              TEXT       Fund goal [default: Lorem ipsum]                                                     │
│ --merge-multiple-authors            When active includes and merge contributors name in author field [default: False]    │
│ --authors-as-list                   Export authors as a list of objects replacing the single author [default: False]     │
│ --stages                 INTEGER    List of stages ids that will be pulled from Ideascale (alternative to --stages-keys) │
│ --stage-keys             TEXT       List of stage keys ids that will be pulled from Ideascale (alternative to --stages)  │
│ --assessments            TEXT       Valid assessments CSV file                                                           │
│ --withdrawn              TEXT       Withdrawn proposals CSV file                                                         │
│ --extra-fields-map       TEXT       Mappings for extra fields                                                            │
│ --proposals-map          TEXT       Mapping for proposals [default: templates/tags.json]                                 │
│ --funds-format           TEXT       Mapping for funds transformation. [default: templates/funds_format.json]             │
│ --challenges-format      TEXT       Mapping for challenges export. [default: templates/challenges_format.json]           │
│ --proposals-format       TEXT       Mapping for proposals [default: templates/proposals_format.json]                     |
│ --reviews-format         TEXT       Mapping for assessments transformation. [default: templates/reviews_format.json]     |
│ --output-dir             TEXT       Output dir for results [default: meta/fund9]                                         │
│ --help                              Show this message and exit.                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

For `--assessments` the example file can be found in `examples/assessments.csv`.
It is possible to omit this param (scores will be at 0 and reviews empty).

For `--withdrawn` the example file can be found in `examples/withdrawn.csv`.
It is possible to omit this param (excluded proposals will be empty).

The `--authors-as-list` option allows to include a list of object, each one describing a proposer or a co-proposer.
The alternative to this option is `--merge-multiple-authors` the outputs a single field with all the co-proposers joined with a `,`.

The `--proposals-format` map has a double function:
 - Only the keys of the `export_cols` field that are present in the proposals
 prepared by the script are exported and extra fields are filtered out.
 Having a field in `export_cols` doesn't guarantee that a field will be
 exported because it depends by its presence in the data (e.g. when
   `--merge_multiple_authors` the field `proposers` is not generate and not
   included in the export even if specified in this file).
- When a key is present it is exported after being cast with the data type
specified as values in the `export_cols` object.
- The `extra_fields` field needs to output data as an object and will include
all the fields indicated in the file of `--extra-fields-map` option.

The `--extra-fields-map` map has a double function:
- The keys of this JSON are the keys that will be used in the output.
- Each of this key is mapped to an ideascale custom field key. If the custom
field key is present for a proposal, it will be added to the final output using
the key indicated.

Ex:
```
  ...
  "budget_breakdown": "please_provide_a_detailed_budget_breakdown",
  ...
```

If the `please_provide_a_detailed_budget_breakdown` field is present in the
IdeaScale proposal, its value will be in the output with the `budget_breakdown`
field, inside the `extra_fields` of the proposal object.


The `--proposals-map` file is used to map the ideascale fields to local
proposal fields. It is possible to specify more than one ideascale field that
will be mapped to a local field.

## Example Usage

`python main.py --api-token 'IDEASCALE_TOKEN' --fund 9 --chain-vote-type 'private' --threshold 450 --fund-goal "Create, fund and deliver the future of Cardano." --stage-keys "stage-governancephase9dc535" --output-dir 'example/fund9' --fund-group-id 8104 --assessments 'example/assessments.csv' --withdrawn 'example/withdrawn.csv' --authors-as-list`

An example output can be find in `examples/proposals.json`.
The ideascale fields returns HTML strings, that are converted in Markdown (after
  stripping all the HTML tags in 'a', 'b', 'img', 'strong', 'u', 'i', 'embed',
  'iframe').
The final output includes fields in Markdown.
