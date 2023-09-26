from typing import List
import typer
import json
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from markdownify import markdownify as md
import re
import pandas as pd
import numpy as np
from rich import print
import strict_rfc3339

app = typer.Typer()

IDEASCALE_API_URL = "https://cardano.ideascale.com/a/rest"
MAX_PAGES_TO_QUERY = 100

def options_validation(ctx: typer.Context, value: bool):
    '''
    Validate that only one of the options `merge_multiple_authors` and
    `authors_as_list` is set to True.
    '''
    if ('merge_multiple_authors' in ctx.params):
        if (value and ctx.params['merge_multiple_authors'] == value):
            raise typer.BadParameter("""merge_multiple_authors and
                authors_as_list can't be active at the same time.""")
    return value

@app.command()
def import_fund(
    api_token: str = typer.Option("", help="Ideascale API token."),
    fund: int = typer.Option(8, help="Fund number."),
    fund_group_id: int = typer.Option(1, help="Ideascale Campaigns group id"),
    chain_vote_type: str = typer.Option("private", help="Chain vote type"),
    threshold: int = typer.Option(450, help="Voting threshold"),
    fund_goal: str = typer.Option("Lorem ipsum", help="Fund goal [UNUSED]. This field is ignored, and used to set the current time in RFC3339 format."),
    merge_multiple_authors: bool = typer.Option(
        False,
        help="When active includes and merge contributors name in author field"
    ),
    authors_as_list: bool = typer.Option(
        False,
        help="Export authors as a list of objects in place of an author field",
        callback=options_validation
    ),
    stages: List[int] = typer.Option(
        [],
        help="List of stages ids that will be pulled from Ideascale"
    ),
    stage_keys: List[str] = typer.Option(
        [],
        help="List of stage keys that will be pulled from Ideascale"
    ),
    assessments: str = typer.Option("", help="Valid assessments CSV file"),
    withdrawn: str = typer.Option("", help="Withdrawn proposals CSV file"),
    proposals_map: str = typer.Option(
        "templates/proposals_map.json",
        help="Mapping for proposals"
    ),
    extra_fields_map: str = typer.Option(
        "templates/proposals_extra_fields.json",
        help="Mappings for extra fields"
    ),
    funds_format: str = typer.Option(
        "templates/funds_format.json",
        help="Mapping for funds transformation."
    ),
    challenges_format: str = typer.Option(
        "templates/challenges_format.json",
        help="Mapping for challenges export."
    ),
    proposals_format: str = typer.Option(
        "templates/proposals_format.json",
        help="Mapping for proposals"
    ),
    reviews_format: str = typer.Option(
        "templates/reviews_format.json",
        help="Mapping for assessments transformation."
    ),
    output_dir: str = typer.Option("meta/fund10", help="Output dir for results"),
):
    authors_output = 'std'
    if authors_as_list:
        authors_output = 'list'
    if merge_multiple_authors:
        authors_output = 'merged_str'
    # Load and prepare
    mappings = json.load(open(f"{proposals_map}"))
    extra_fields_map = json.load(open(f"{extra_fields_map}"))
    funds_format = json.load(open(f"{funds_format}"))
    challenges_format = json.load(open(f"{challenges_format}"))
    proposals_format = json.load(open(f"{proposals_format}"))
    reviews_format = json.load(open(f"{reviews_format}"))
    if assessments:
        assessments = transform_assessments(
            pd.read_csv(assessments),
            reviews_format
        )
    else:
        assessments = False

    scores = get_scores(assessments)
    reviews = get_reviews(assessments, reviews_format)
    if withdrawn != '':
        withdrawn = pd.read_csv(withdrawn)
    else:
        withdrawn = False
    # OVERRIDE fund_goal to set the current time in RFC3339 format
    fund_goal = strict_rfc3339.now_to_rfc3339_utcoffset(integer=True)
    # Get local and remote data
    e_fund = get_fund(fund, threshold, fund_goal)
    challenges = get_challenges(fund, fund_group_id, api_token)
    if len(stage_keys) > 0:
        proposals = _get_proposals(
            stage_keys,
            fund,
            challenges,
            api_token,
            mappings,
            extra_fields_map,
            chain_vote_type,
            assessments,
            authors_output
        )
    elif len(stages) > 0:
        proposals = get_proposals(
            stages,
            fund,
            challenges,
            api_token,
            mappings,
            extra_fields_map,
            chain_vote_type,
            assessments,
            authors_output
        )

    excluded = transform_excluded(withdrawn)

    # Export relevant data
    print(f"[yellow]Saving data...[/yellow]")
    save_json(
        f"{output_dir}/funds.json",
        export_format(e_fund, funds_format)
    )
    save_json(
        f"{output_dir}/challenges.json",
        export_format(challenges, challenges_format)
    )
    save_json(
        f"{output_dir}/proposals.json",
        export_format(proposals, proposals_format)
    )
    save_json(
        f"{output_dir}/reviews.json",
        export_format(reviews, reviews_format)
    )
    scores.to_csv(f"{output_dir}/scores.csv", index=False)
    save_json(f"{output_dir}/excluded_proposals.json", excluded)
    print(f"[green bold]All data saved in {output_dir}.[/green bold]")

def get_fund(fund_id, threshold, goal):
    print(f"[yellow]Preparing fund...[/yellow]")
    return [
        {
            "id": fund_id,
            "goal": goal,
            "threshold": threshold,
            "rewards_info": ""
        }
    ]

def get_challenges(fund_id, fund_group_id, api_token):
    print(f"[yellow]Requesting challenges...[/yellow]")
    url = f"{IDEASCALE_API_URL}/v1/campaigns/groups/{fund_group_id}"
    response = ideascale_get(url, api_token)
    challenges = []
    full_challenges = []
    for fund in response:
        if "campaigns" in fund:
            for idx, res in enumerate(fund["campaigns"]):
                title = res["name"].replace(f"F{fund_id}:", "").strip()
                challenge_type = extract_challenge_type(title)
                rewards, currency = parse_rewards(res["tagline"])
                challenge = {
                    "id": idx + 1,
                    "title": title,
                    "challenge_type": challenge_type,
                    # canonical URL from the API query points to challenge brief
                    # instead of proposals list
                    "challenge_url": f"https://cardano.ideascale.com/c/campaigns/{res['id']}/",
                    "description": strip_tags(res["description"]),
                    "fund_id": fund_id,
                    "rewards_total": rewards,
    		        "proposers_rewards": rewards,
                    "internal_id": res['id']
                }
                challenges.append(challenge)
    print(
        f"[bold green]Total challenges pulled: {len(challenges)}[/bold green]"
    )
    return challenges

def _get_proposals(
    stage_ids,
    fund_id,
    challenges,
    api_token,
    mappings,
    extra_fields_map,
    chain_vote_type,
    assessments,
    authors_output
):
    print(f"[yellow]Requesting proposals...[/yellow]")
    page_size = 50
    ideas = []
    relevant_keys = extract_relevant_keys(mappings)
    relevant_extra_keys = extract_relevant_keys(extra_fields_map)
    internal_id = 0
    for challenge in challenges:
        for stage in stage_ids:
            for page in range(MAX_PAGES_TO_QUERY):
                url = f"{IDEASCALE_API_URL}/v1/campaigns/{challenge['internal_id']}/ideas/status/custom/{stage}/{page}/{page_size}"
                response = ideascale_get(url, api_token)
                for idx, idea in enumerate(response):
                    parsed_idea = parse_idea(
                        idea,
                        fund_id,
                        relevant_keys,
                        relevant_extra_keys,
                        extra_fields_map,
                        challenge,
                        chain_vote_type,
                        internal_id,
                        assessments,
                        authors_output,
                        mappings
                    )
                    ideas.append(parsed_idea)
                    internal_id = internal_id + 1
                if (len(response) < page_size):
                    # Break page loop if there are no results - thanks IdeaScale
                    # pagination implementation
                    break
    print(f"[bold green]Total ideas pulled: {len(ideas)}[/bold green]")
    return ideas

def get_proposals(
    stage_ids,
    fund_id,
    challenges,
    api_token,
    mappings,
    extra_fields_map,
    chain_vote_type,
    assessments,
    authors_output
):
    print(f"[yellow]Requesting proposals...[/yellow]")
    page_size = 50
    ideas = []
    relevant_keys = extract_relevant_keys(mappings)
    relevant_extra_keys = extract_relevant_keys(extra_fields_map)
    internal_id = 0
    for stage in stage_ids:
        for page in range(MAX_PAGES_TO_QUERY):
            url = f"{IDEASCALE_API_URL}/v1/stages/{stage}/ideas/{page}/{page_size}"
            response = ideascale_get(url, api_token)
            for idx, idea in enumerate(response):
                challenge = find_challenge(idea['campaignId'], challenges)
                parsed_idea = parse_idea(
                    idea,
                    fund_id,
                    relevant_keys,
                    relevant_extra_keys,
                    extra_fields_map,
                    challenge,
                    chain_vote_type,
                    internal_id,
                    assessments,
                    authors_output,
                    mappings
                )
                ideas.append(parsed_idea)
                internal_id = internal_id + 1
            if (len(response) < page_size):
                # Break page loop if there are no results - thanks IdeaScale
                # pagination implementation
                break
    print(f"[bold green]Total ideas pulled: {len(ideas)}[/bold green]")
    return ideas

def parse_idea(
    idea, fund_id, relevant_keys, relevant_extra_keys, extra_fields_map, challenge, chain_vote_type, internal_id, assessments, authors_output, mappings
):
    temp_idea = extract_custom_fields(idea, relevant_keys)
    extra_fields_idea = extract_custom_fields(idea, relevant_extra_keys)
    parsed_idea = {
        "category_name": f"Fund {fund_id}",
        "chain_vote_options": "blank,yes,no",
        "challenge_id": challenge["id"],
        "challenge_type": challenge["challenge_type"],
        "chain_vote_type": chain_vote_type,
        "internal_id": internal_id,
        "proposal_id": idea["id"],
        "proposal_impact_score": extract_score(idea["id"], assessments),
        "proposal_summary": strip_tags(idea["text"]),
        "proposal_title": strip_tags(idea["title"]),
        "proposal_url": idea["url"],
        "files_url": {
            "open_source": idea["customFieldsByKey"]["f10_open_source_choice"],
            "external_link1": idea["customFieldsByKey"]["f10_external_link"],
            "external_link2": idea["customFieldsByKey"]["f10_external_link_2"],
            "external_link3": idea["customFieldsByKey"]["f10_external_link_3"],
        },
    }
    if authors_output == 'std' or authors_output == 'merged_str':
        proposers_name = extract_proposers(idea, authors_output)
        # parsed_idea['proposer_email'] = idea["authorInfo"]["email"]
        parsed_idea['proposer_name'] = proposers_name
    else:
        proposers = extract_proposers(idea, authors_output)
        parsed_idea['proposers'] = proposers

    for k in mappings:
        extracted = extract_mapping(mappings[k], temp_idea)
        if extracted:
            parsed_idea[k] = extracted

    for k in extra_fields_map:
        extracted = extract_mapping(extra_fields_map[k], extra_fields_idea)
        if extracted:
            if 'extra_fields' not in parsed_idea:
                parsed_idea['extra_fields'] = {}
            parsed_idea['extra_fields'][k] = extracted
    return parsed_idea


def get_reviews(assessments, reviews_map):
    print(f"[yellow]Preparing reviews...[/yellow]")
    if assessments is False:
        return []
    relevant = assessments[reviews_map['cols'].keys()]
    reviews = relevant.rename(columns = reviews_map['cols'])
    reviews = reviews.to_dict('records')
    return reviews

def round_mean(x):
    return round(x.mean(), 2)

def get_scores(assessments):
    print(f"[yellow]Preparing proposals scores...[/yellow]")
    if assessments is False:
        return pd.DataFrame([])
    # Calculate scores from assessments. Group by proposal id and calculate avg
    all_proposals = assessments.groupby('proposal_id', as_index=False).agg({
        'Rating': round_mean
    })
    all_proposals = all_proposals.rename(columns={'Rating': 'rating_given'})
    return all_proposals

def ideascale_get(url, token):
    # Setup a retry strategy for failing requests
    retry_strategy = Retry(
        total=5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    headers = { 'api_token': token }
    print("Requesting url: {}".format(url))
    r = http.get(url, headers=headers)
    try:
        response = r.json()
        if (r.status_code == 200):
            return response
        else:
            print(f"Error {r.status_code}")
    except Exception as e:
        print("Something wrong with Ideascale")
        print(e)

def save_json(path, data):
    with open(path, 'w') as outfile:
        json.dump(data, outfile, indent=2)
        outfile.close()

def extract_proposers(idea, authors_output):
    contributors = []
    if authors_output == 'std' or authors_output == 'merged_str':
        proposers = [idea['authorInfo']['name']]
        if authors_output == 'merged_str':
            contributors = [c['name'] for c in idea['contributors']]
        all_authors = proposers + contributors
        return ', '.join(all_authors)
    else:
        proposers = [{
            'name': idea['authorInfo']['name'],
            #'email': idea['authorInfo']['email'],
            'main': True
        }]
        '''
        contributors = [
            {'name': c['name'], 'email': c['email']}
            for c in idea['contributors']
        ]
        '''
        contributors = [
            {'name': c['name']}
            for c in idea['contributors']
        ]
        return proposers + contributors



def extract_custom_fields(idea, relevant_keys):
    # Create a temporary idea dict only with relevant keys extracted from
    # the customFieldsByKey in IdeaScale response
    temp_idea = {}
    if 'customFieldsByKey' in idea:
        for k in relevant_keys:
            if (k in idea['customFieldsByKey']):
                temp_idea[k] = strip_tags(idea['customFieldsByKey'][k])
    return temp_idea

def extract_relevant_keys(mappings):
    relevant_keys = []
    for k in mappings:
        if isinstance(mappings[k], list):
            relevant_keys = relevant_keys + mappings[k]
        else:
            relevant_keys.append(mappings[k])
    return relevant_keys

def extract_mapping(key, idea):
    if isinstance(key, list):
        for k in key:
            if k in idea and (len(idea[k]) > 0):
                return idea[k]
    else:
        if key in idea:
            return idea[key]
    return False

def extract_score(id, assessments):
    # Query assessments by proposal_id and calculate avg of scores.
    if assessments is False:
        return "0"
    mask = assessments.query(f"proposal_id == {id}")
    score = mask['Rating'].mean()
    return str(int(np.round(score, 2) * 100))

def parse_rewards(subtitle):
    # Regex to extract budget and currency from 3 different templates:
    # $500,000 in ada
    # $200,000 in CLAP tokens
    # 12,800,000 ada
    result = re.search(r"\$?(.*?)\s+(?:in\s)?(.*)", subtitle)
    rewards = re.sub('\D', '', result.group(1))
    currency = result.group(2)
    return rewards, currency

def extract_challenge_type(title):
    # Actual implementation base on titles. It could be adapted to use
    # different funnel_id
    if 'catalyst natives' in title.lower():
        return 'native'
    elif 'challenge setting' in title.lower():
        return 'community-choice'
    else:
        return 'simple'

def strip_tags(text):
    tags_to_strip = ['a', 'b', 'img', 'strong', 'u', 'i', 'embed', 'iframe']
    clean_text = md(text, strip=tags_to_strip).strip()
    return clean_text

def find_challenge(id, challenges):
    for c in challenges:
        if id == c['internal_id']:
            return c
    print(f"Error, challenge {id} not found")
    return {}

def cast_field(value, dtype):
    if (dtype == 'int'):
        return int(value)
    elif (dtype == 'float'):
        return float(value)
    elif (dtype == 'bool'):
        return value.lower() == "true"
    elif (dtype == 'list'):
        return value
    elif (dtype == 'dict'):
        return value
    else:
        return str(value)

def export_format(elements, ex_format):
    # Map list of elements filtering only valid fields
    return [
        dict(
            (k, cast_field(el[k], ex_format['export_cols'][k]))
            for k in ex_format['export_cols'].keys()
            if k in el
        )

        for el in elements
    ]

def transform_assessments(assessments, reviews_map):
    # Calculate avg for the score of each single assessment.
    assessments['Rating'] = assessments[reviews_map['rating_cols']].mean(axis=1)
    return assessments

def transform_excluded(widthdrawn):
    print(f"[yellow]Preparing withdrawn proposals...[/yellow]")
    if widthdrawn is False:
        return []
    proposals = widthdrawn_proposals.to_dict('records')
    ids = [proposal['proposal_id'] for proposal in proposals]
    return ids

if __name__ == "__main__":
    app()
