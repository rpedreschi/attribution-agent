"""Event payload builders, one per source-system topic.

Each builder returns a (topic_key, payload) tuple. `topic_key` indexes
settings.kafka.topics; `payload` is JSON shaped like the real API response so
the DeltaStream CREATE STREAM / CREATE CHANGELOG definitions read it directly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

Event = tuple[str, dict[str, Any]]


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# --- Salesforce CDC (changelogs) --------------------------------------------

def sf_account(account_id: str, name: str, industry: str, employees: int,
               arr_band: str, region: str, is_customer: bool, updated: datetime) -> Event:
    return ("salesforce_accounts", {
        "account_id": account_id, "name": name, "industry": industry,
        "employee_count": employees, "arr_band": arr_band, "region": region,
        "is_customer": 1 if is_customer else 0, "updated_at": _ts(updated),
    })


def sf_contact(contact_id: str, email: str, account_id: str,
               first: str, last: str, updated: datetime) -> Event:
    return ("salesforce_contacts", {
        "contact_id": contact_id, "email": email, "account_id": account_id,
        "first_name": first, "last_name": last, "updated_at": _ts(updated),
    })


def sf_opportunity(opp_id: str, account_id: str, stage_from: str, stage_to: str,
                   amount: float, deal_size: str, when: datetime) -> Event:
    return ("salesforce_opportunities", {
        "opportunity_id": opp_id, "account_id": account_id,
        "stage_from": stage_from, "stage_to": stage_to,
        "amount": round(amount, 2), "deal_size": deal_size, "event_time": _ts(when),
    })


# --- HubSpot MAP ------------------------------------------------------------

def hubspot_form(vid: str, web_user_id: str, email: str, form: str,
                 campaign: str, utm_source: str, when: datetime) -> Event:
    return ("hubspot", {
        "event_time": _ts(when), "vid": vid, "web_user_id": web_user_id,
        "email": email, "event_type": "form_submission",
        "lifecycle_from": "", "lifecycle_to": "", "form_name": form,
        "campaign": campaign, "utm_source": utm_source, "utm_medium": "form",
        "utm_campaign": campaign,
    })


def hubspot_lifecycle(vid: str, email: str, frm: str, to: str, when: datetime) -> Event:
    return ("hubspot", {
        "event_time": _ts(when), "vid": vid, "web_user_id": "", "email": email,
        "event_type": "lifecycle_change", "lifecycle_from": frm, "lifecycle_to": to,
        "form_name": "", "campaign": "", "utm_source": "", "utm_medium": "",
        "utm_campaign": "",
    })


def hubspot_email(vid: str, email: str, kind: str, campaign: str, when: datetime) -> Event:
    # kind is 'email_open' or 'email_click'
    return ("hubspot", {
        "event_time": _ts(when), "vid": vid, "web_user_id": "", "email": email,
        "event_type": kind, "lifecycle_from": "", "lifecycle_to": "",
        "form_name": "", "campaign": campaign, "utm_source": "hubspot",
        "utm_medium": "email", "utm_campaign": campaign,
    })


# --- GA4 --------------------------------------------------------------------

def ga4_event(user_id: str, session_id: str, name: str, page: str, device: str,
              utm_source: str, utm_medium: str, utm_campaign: str, when: datetime) -> Event:
    return ("ga4", {
        "event_time": _ts(when), "user_id": user_id, "session_id": session_id,
        "event_name": name, "page_location": page, "device_type": device,
        "utm_source": utm_source, "utm_medium": utm_medium,
        "utm_campaign": utm_campaign, "utm_term": "", "utm_content": "",
    })


# --- Ad platforms -----------------------------------------------------------

def linkedin_spend(day: str, campaign: str, spend: float, impr: int, clicks: int) -> Event:
    return ("linkedin_ads", {
        "spend_date": day, "channel": "Paid Social", "campaign": campaign,
        "spend_amount": round(spend, 2), "impressions": impr, "clicks": clicks,
    })


def google_spend(day: str, campaign: str, spend: float, impr: int, clicks: int) -> Event:
    return ("google_ads", {
        "spend_date": day, "channel": "Paid Search", "campaign": campaign,
        "spend_amount": round(spend, 2), "impressions": impr, "clicks": clicks,
    })


# --- Outreach ---------------------------------------------------------------

def outreach_activity(prospect_id: str, email: str, contact_id: str, activity: str,
                      sequence: str, sdr: str, when: datetime) -> Event:
    return ("outreach", {
        "event_time": _ts(when), "prospect_id": prospect_id, "email": email,
        "contact_id": contact_id, "activity": activity, "sequence": sequence,
        "sdr": sdr,
    })
