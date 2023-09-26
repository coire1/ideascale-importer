# Set the Earthly version to 0.7
VERSION 0.7

# Use current debian stable with python
FROM python:3.11-slim

# Environment variables for python
ENV PYTHONUNBUFFERED=true

# Build base container and install python requirements
build-reqs:
    WORKDIR /ideascale-importer

    # Install system dependencies
    RUN apt-get update && \
        apt-get install -y --no-install-recommends curl build-essential #libxml2-dev libxslt-dev zlib1g-dev python3-lxml

    ## apt cleanup
    RUN apt-get clean && \
        rm -rf /var/lib/apt/lists/*

    # Install package dependencies from requirements
    COPY requirements.txt ./
    RUN pip install -r requirements.txt

# Build container with main script and extras.
build:
    FROM +build-reqs
    # Copy the package files to the container
    COPY --dir scripts examples templates main.py README.md ./

    SAVE ARTIFACT /ideascale-importer

# Run the script.
#
# This target requires that the `api_token` to be provided as a secret.
#
# The simplest way to accomplish this, is to put it in a `./secrets` file, so that Earthly can retrieve it.
# It also needs to be provided by CI to work there.
run:
    FROM +build

    # These args can be passed as earthly CLI arguments.
    ARG api_token
    ARG fund="10"
    ARG fund_group_id="63"
    ARG output_dir="./deployment"
    ARG stages="--stages 4590 --stages 4596 --stages 4602 --stages 4608 --stages 4614 --stages 4620 --stages 4626 --stages 4632 --stages 4638 --stages 4644 --stages 4650 --stages 4656 --stages 4662"

    # Reset the $output_dir
    RUN rm -rf $output_dir && mkdir $output_dir

    # Run the script
    RUN --no-cache --secret api_token python3 main.py --fund $fund --fund-group-id $fund_group_id $stages --output-dir $output_dir --api-token $api_token
    SAVE ARTIFACT $output_dir
