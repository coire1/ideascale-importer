import sys
import csv
from faker import Faker
import json
import random

# number of max reviews that will be generated for each proposal
number_of_reviews = int(sys.argv[1])
# get proposals
with open("proposals.json") as proposals_file:
    proposals = json.load(proposals_file)

fake = Faker()
# one assessor for each review
assessors_id = sorted(
    set(fake.unique.random_int(min=5000, max=7000) for i in range(number_of_reviews))
)
with open("random-reviews.csv", mode="w") as file:
    file_writer = csv.writer(
        file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    file_writer.writerow(
        [
            "id",
            "Assessor",
            "Impact / Alignment Note",
            "Impact / Alignment Rating",
            "Feasibility Note",
            "Feasibility Rating",
            "Auditability Note",
            "Auditability Rating",
            "level",
            "allocated",
            "proposal_id",
            "proposal_url",
            "proposal_title",
            "proposal_challenge_id",
            "Result",
        ]
    )
    index = 0
    for proposal in proposals:
        reviews_for_proposal = random.randrange(0, number_of_reviews)
        for n in range(reviews_for_proposal):
            file_writer.writerow(
                [
                    index + 1,
                    "test_assessor_" + str(assessors_id[n]),
                    fake.paragraph(nb_sentences=7),
                    fake.random_int(min=1, max=5),
                    fake.paragraph(nb_sentences=7),
                    fake.random_int(min=1, max=5),
                    fake.paragraph(nb_sentences=7),
                    fake.random_int(min=1, max=5),
                    fake.random_int(min=0, max=1),
                    fake.boolean(chance_of_getting_true=50),
                    proposal["proposal_id"],
                    proposal["proposal_url"],
                    proposal["proposal_title"],
                    proposal["challenge_id"],
                ]
            )
            index += 1
