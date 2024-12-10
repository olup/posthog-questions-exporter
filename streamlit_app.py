import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import os
import json

st.set_page_config(page_title="PostHog Message Exporter")


def fetch_posthog_events(bot_wat, poi_uuids, start_date, end_date, include_errors, include_no_errors):
    project_id = "19229"
    api_key = st.secrets["POSTHOG_API_KEY"]

    if not api_key:
        st.error("PostHog API key not found in environment variables")
        return None

    filters = []

    if bot_wat:
        filters.append(f"properties.bot_wat = '{bot_wat}'")
    elif poi_uuids:
        uuid_list = [
            f"'{uuid.strip()}'" for uuid in poi_uuids.split() if uuid.strip()]
        filters.append(f"properties.poi_uuid in ({','.join(uuid_list)})")

    error_filters = []
    if include_errors:
        error_filters.append("properties.error is not null")
    if include_no_errors:
        error_filters.append("properties.error is null")

    if error_filters:
        filters.append(f"({' or '.join(error_filters)})")

    where_clause = f"event = 'message_received' and {' and '.join(filters)}"

    query = f"""
            SELECT
            timestamp,
            properties.question as question,
            properties.response as response,
            properties.error as error
            FROM events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT 100000
            """

    print(query)

    payload = {
        "query": {
            "kind": "HogQLQuery",
            "query": query
        }
    }

    response = requests.post(
        f"https://eu.posthog.com/api/projects/{project_id}/query/",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload)
    )

    if response.ok:
        return response.json()['results']
    else:
        st.error(f"Error fetching data: {response.text}")
        return None


st.title("PostHog Message Exporter")

# Filter Type Selection
filter_type = st.radio("Filter Type", ["Bot WAT", "POI UUIDs"])

# Filter Value Input
if filter_type == "Bot WAT":
    bot_wat = st.text_input("Bot WAT")
    poi_uuids = ""
else:
    bot_wat = ""
    poi_uuids = st.text_area("POI UUIDs (one per line)")

# Date Range
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "Start Date", datetime.now() - timedelta(days=7))
with col2:
    end_date = st.date_input("End Date", datetime.now())

# Error Filters
col3, col4 = st.columns(2)
with col3:
    include_errors = st.checkbox("Include Messages with Errors", True)
with col4:
    include_no_errors = st.checkbox("Include Messages without Errors", True)

if st.button("Export Messages"):
    if filter_type == "Bot WAT" and not bot_wat:
        st.error("Please enter a Bot WAT")
    elif filter_type == "POI UUIDs" and not poi_uuids:
        st.error("Please enter at least one POI UUID")
    elif not (include_errors or include_no_errors):
        st.error("Please select at least one error filter option")
    else:
        with st.spinner("Fetching data..."):
            results = fetch_posthog_events(
                bot_wat=bot_wat,
                poi_uuids=poi_uuids,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                include_errors=include_errors,
                include_no_errors=include_no_errors
            )

            if results:
                df = pd.DataFrame(results)

                # Display total events count
                st.info(f"Total events found: {len(df)}")

                # Download button for CSV
                csv = df.to_csv(index=False).encode('utf-8')
                filter_id = bot_wat if filter_type == "Bot WAT" else "poi_list"
                error_filter = "_".join(filter(None, [
                    "with_error" if include_errors else "",
                    "without_error" if include_no_errors else ""
                ]))
                filename = f"posthog_messages_{filter_id}_{error_filter}_{start_date}_{end_date}.csv"

                st.download_button(
                    "Download CSV",
                    csv,
                    filename,
                    "text/csv",
                    key='download-csv'
                )
