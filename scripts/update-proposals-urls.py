import json

with open("proposals.json") as proposals_file:
    proposals = json.load(proposals_file)

with open("slug-urls.json") as urls_file:
    urls = json.load(urls_file)

for proposal in proposals:
    found = False
    for row in urls["data"]["fund"]["projects"]:
        if row["_id"] == proposal["proposal_id"]:
            found = True
            proposal["proposal_url"] = (
                "https://projectcatalyst.io/funds/10/"
                + row["challenge"]["slug"]
                + "/"
                + row["projectSlug"]
            )

    if not found:
        print("Not found for proposal id: " + proposal["proposal_id"])

json_object = json.dumps(proposals, indent=4)
with open("proposals-slugs.json", "w") as outfile:
    outfile.write(json_object)
