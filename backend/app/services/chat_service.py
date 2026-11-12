"""
Chat Service — slot-filling orchestrator.
Manages conversation state, collects trip inputs progressively,
confirms with user, then triggers async generation.
"""
import logging
import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.trip import BudgetScope, Trip, TripStatus, TripDestination
from app.models.itinerary import Activity, ItineraryDay, PackingList, BudgetBreakdown, TransportLeg, TimeSlot
from app.models.place import Accommodation, Restaurant
from app.config import settings
from app.services import llm_service

logger = logging.getLogger(__name__)

GENERIC_DESTINATION_RE = r"^(?:hi|hello|hey|greetings|hello\s+)?\s*(?:i\s+want\s+to\s+plan(?:\s+p\s*=\s*)?|plan\s+a\s+trip|help\s+me\s+plan|i\s+want\s+(?:a|to\s+plan\s+a)\s+trip|travel\s+planner).*$"
NON_ANSWER_RE = r"^(?:hi|hello|hey|greetings|good\s+(?:morning|afternoon|evening)|ok|okay|thanks|thank\s+you|yes|yep|sure|hmm)[!. ,]*$"

# Ordered intake slots. Preferences receive a safe default when explicitly skipped.
SLOT_ORDER = [
    "destination", "travelers_adults", "travelers_children", "child_ages", "start_date",
    "budget", "days", "starting_city", "travel_style",
    "interests", "pace", "diet", "transport_mode", "special_requests",
]
REQUIRED_SLOTS = ["destination", "budget", "days"]
SLOT_QUESTIONS = {
    "travelers_adults": "How many adults will be travelling?",
    "travelers_children": "Will any children be joining?",
    "child_ages": "How old are the children?",
    "start_date": "When are you planning to travel?",
    "destination": "Where would you like to go? You can name a country, state, or city.",
    "budget": "Could you let me know your budget for the trip?",
    "days": "How many days are you planning to stay?",
    "starting_city": "Which city will you be travelling from? (You can skip this.)",
    "travel_style": "Do you prefer budget, mid-range, or luxury travel?",
    "interests": "Do you have specific interests — heritage, adventure, food, nature, or a balanced mix?",
    "pace": "Would you prefer a relaxed, moderate, or packed itinerary?",
    "diet": "Any dietary preferences I should know about?",
    "transport_mode": "How would you prefer to travel between cities — flight, train, or bus?",
    "special_requests": "Anything else you'd like me to keep in mind?",
}
DEFAULTS = {
    "travelers_adults": 1, "travelers_children": 0, "child_ages": [],
    "start_date": "next 30 days", "travel_style": "mid_range",
    "interests": ["balanced mix"], "pace": "moderate", "diet": ["any"],
    "transport_mode": "best time-cost balance", "starting_city": "", "special_requests": "",
}
DESTINATION_KEYWORDS = [
    "rajasthan", "goa", "kerala", "himachal", "jaipur", "delhi", "mumbai",
    "udaipur", "agra", "varanasi", "kashmir", "ooty", "coorg", "manali",
    "shimla", "darjeeling", "ladakh", "andaman",
]


def is_invalid_destination(value: object) -> bool:
    """Return True for generic planning text accidentally saved as a place."""
    if not isinstance(value, str):
        return False
    normalized = " ".join(value.strip().lower().split())
    if not normalized:
        return True
    if re.fullmatch(r"(?:p\s*=\s*)?my\s+trip", normalized):
        return True
    return bool(re.fullmatch(GENERIC_DESTINATION_RE, normalized))


def is_non_answer(value: object) -> bool:
    """Return True when a message does not answer the current intake slot."""
    if not isinstance(value, str):
        return True
    return bool(re.fullmatch(NON_ANSWER_RE, " ".join(value.strip().lower().split())))


def reset_invalid_draft(trip: Trip, session: ChatSession, db: Session) -> bool:
    """Reset only an incomplete draft whose destination is not a real place."""
    if trip.status in (TripStatus.CREATED, TripStatus.DONE, TripStatus.CREATING, TripStatus.GENERATING):
        return False
    destination = (session.slot_state or {}).get("destination")
    if not is_invalid_destination(destination):
        return False

    # The user explicitly chose to restart corrupted drafts. Delete only the
    # incomplete trip's chat/destination records; completed trips are protected.
    db.query(ChatMessage).filter(ChatMessage.trip_id == trip.id).delete(synchronize_session=False)
    db.query(TripDestination).filter(TripDestination.trip_id == trip.id).delete(synchronize_session=False)
    session.slot_state = {}
    session.next_slot = "destination"
    session.confirmed = False
    trip.status = TripStatus.DRAFT
    trip.title = "My Trip"
    db.flush()
    return True

SYSTEM_PROMPT = """You are a friendly AI travel planning assistant for "AI Travel Planner".
Your job is to help users plan trips through natural conversation — ask one focused question at a time.

RULES:
1. Ask only ONE question per response.
2. Extract information the user provides even without being asked (e.g. "just me and my wife" → 2 adults).
3. Always confirm the budget scope (total for group or per person).
4. Once you have destination, budget, and days, ask for a few more preferences briefly.
5. Keep responses warm, concise, and encouraging.
6. When you have enough info, summarize everything and ask for confirmation.
7. If the user says "yes" or "generate" after the summary, respond EXACTLY with: READY_TO_GENERATE
8. If the user asks to change something after the plan is generated, respond EXACTLY with: EDIT_REQUEST: <what to change>

Current slot state will be provided. Ask exactly the next unanswered question from the intake order. Never ask for a slot that is already present in the collected information, even when the latest message supplied several slots at once.
If the user gives multiple details, extract all of them and move to the next missing slot.
Use application defaults when the user says skip or no preference. Ask budget and days explicitly only when they are still missing.
"""


def get_or_create_session(trip: Trip, db: Session) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.trip_id == trip.id).first()
    if not session:
        session = ChatSession(trip_id=trip.id, slot_state={}, next_slot="destination")
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def build_context_prompt(session: ChatSession) -> str:
    slots = session.slot_state or {}
    slot_summary = "\n".join(f"  - {k}: {v}" for k, v in slots.items()) if slots else "  (none yet)"
    missing = [s for s in SLOT_ORDER if s not in slots and not (s == "child_ages" and not slots.get("travelers_children"))]
    return f"""
Current collected information:
{slot_summary}

Missing required slots: {', '.join(missing) if missing else 'ALL COLLECTED'}
Turn count: {session.turn_count}
"""


def build_confirmation_message(slots: dict) -> str:
    destination = slots.get("destination", "your destination")
    adults = int(slots.get("travelers_adults", 1) or 1)
    children = int(slots.get("travelers_children", 0) or 0)
    party = f"{adults} adult" if adults == 1 else f"{adults} adults"
    if children:
        party += f" and {children} child" if children == 1 else f" and {children} children"
    budget = slots.get("budget")
    budget_text = f"₹{int(float(budget)):,}" if budget is not None else "your budget"
    days = slots.get("days", "the requested duration")
    travel_date = slots.get("start_date", "the next 30 days")
    return (
        f"Lovely — I have your trip details for {destination}: {party}, {days} days, "
        f"travelling around {travel_date}, with a budget of {budget_text}. "
        "I’ll use the preferences you shared and sensible defaults for anything you skipped. "
        "Would you like me to generate the full plan?"
    )


def extract_slots_from_reply(user_message: str, current_slots: dict, agent_reply: str) -> dict:
    """
    Quick heuristic extraction + LLM-assisted slot update.
    """
    # Simple heuristic extractions
    text = user_message.lower()
    updated = dict(current_slots)

    # Budget pattern: currency-prefixed amounts and phrases such as
    # "budget of 40000". Keep the suffix attached to the match.
    import re
    budget_match = re.search(
        r'(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|l)?'
        r'|\b(?:budget|spend|limit)\s*(?:is|of|around|about|:)?\s*'
        r'(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|l)?',
        text,
    )
    if budget_match and "budget" not in updated:
        raw = budget_match.group(1) or budget_match.group(3)
        suffix = budget_match.group(2) or budget_match.group(4) or ""
        value = float(raw.replace(",", ""))
        multiplier = 1000 if suffix == "k" else 100000 if suffix in ("l", "lakh") else 1
        val = int(value * multiplier)
        if val > 100:  # filter out noise
            updated["budget"] = val

    if re.search(r"\bper[\s-]?person\b|\beach(?:\s+person)?\b", text):
        updated["budget_scope"] = "per_person"
    elif re.search(r"\b(total|whole group|for the group|for both of us)\b", text):
        updated["budget_scope"] = "total"

    # Days pattern
    days_match = re.search(r'(\d+)\s*[-]?\s*(?:days?|nights?)', text)
    if days_match and "days" not in updated:
        updated["days"] = int(days_match.group(1))

    # Travelers
    if "just me" in text or "only me" in text or "solo" in text:
        updated["travelers_adults"] = 1
    elif "me and my wife" in text or "me and my husband" in text or "couple" in text:
        updated["travelers_adults"] = 2

    # Style — check mid-range variants first so "budget" in cost phrases doesn't match
    for style in ["mid-range", "midrange", "luxury", "budget"]:
        if style in text:
            updated["travel_style"] = "mid_range" if "mid" in style else style
            break

    if re.search(r"\bnon[- ]?(?:vegetarian|veg)\b", text):
        updated["diet"] = "non_vegetarian"
    elif re.search(r"\bvegan\b", text):
        updated["diet"] = "vegan"
    elif re.search(r"\bvegetarian\b|\bveg\b", text):
        updated["diet"] = "vegetarian"
    elif text.strip().rstrip(".!") == "any" or re.search(
        r"\b(no dietary restrictions|no food restrictions|eat anything)\b", text
    ):
        updated["diet"] = "any"

    # Children, ages, adults, dates and preference values.
    child_match = re.search(r"\b(\d+)\s*(?:children|child|kids?)\b", text)
    if child_match:
        updated["travelers_children"] = int(child_match.group(1))
    elif re.search(r"\b(no|none)\b.*\b(children|kids?)\b|\bwithout children\b", text):
        updated["travelers_children"] = 0
    age_matches = re.findall(r"\b\d{1,2}\s*(?:years?|yrs?)\b", text)
    if age_matches:
        updated["child_ages"] = [int(re.search(r"\d+", age).group()) for age in age_matches]

    adult_match = re.search(r"\b(\d+)\s*(?:adults?|people|persons?)\b", text)
    if adult_match:
        updated["travelers_adults"] = int(adult_match.group(1))
    elif re.search(r"\b(couple|both of us|me and my (?:wife|husband|partner))\b", text):
        updated["travelers_adults"] = 2
    elif re.search(r"\b(just me|only me|solo|alone)\b", text):
        updated["travelers_adults"] = 1

    date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{4})?)\b", text)
    if date_match:
        updated["start_date"] = date_match.group(1)
    else:
        relative_date = re.search(r"\b(next month|next 30 days|soon|this month)\b", text)
        if relative_date:
            updated["start_date"] = relative_date.group(1)

    for pace in ("relaxed", "moderate", "packed"):
        if pace in text:
            updated["pace"] = pace
    for mode in ("flight", "train", "bus"):
        if mode in text:
            updated["transport_mode"] = mode

    # Users often include their origin in the first message, for example
    # "flights from Ahmedabad to Goa". Treat it as an answered slot instead
    # of asking for the starting city again later.
    starting_city_match = re.search(
        r"\b(?:from|starting from|departing from|leaving from)\s+"
        r"([a-z][a-z .'-]{1,40}?)(?=\s+(?:to|in|on|during|for|with|and|the|including|travell?ing)\b|[,.!?]|$)",
        text,
    )
    if starting_city_match and "starting_city" not in updated:
        city = starting_city_match.group(1).strip(" .,!?-")
        if city:
            updated["starting_city"] = city.title()

    if re.search(r"\b(heritage|adventure|food|nature)\b", text):
        updated["interests"] = [x for x in ("heritage", "adventure", "food", "nature") if x in text]

    if "destination" not in updated:
        for keyword in DESTINATION_KEYWORDS:
            if keyword in text:
                updated["destination"] = keyword.title()
                break

    # On a new conversation, preserve a short destination phrase from the
    # first message (e.g. "Rajasthan for a week").
    if "destination" not in updated and not current_slots and not re.fullmatch(
        r"(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|greetings)[!. ]*", text
    ):
        cleaned = re.sub(r"\b(i want to go to|i want to visit|visit|travel to|go to|plan a trip to)\b", "", user_message, flags=re.I)
        cleaned = re.sub(r"\s+for\s+\d+\s+(?:days?|nights?).*$", "", cleaned, flags=re.I).strip(" .,!?")
        if cleaned and len(cleaned.split()) <= 8 and not is_invalid_destination(cleaned) and not re.search(r"\b(plan|trip|travel|budget|days?)\b", cleaned, re.I):
            updated["destination"] = cleaned.title()

    return updated


def process_message(
    user_message: str,
    db: Session,
    trip: Trip,
    session: ChatSession,
    background_tasks=None,
) -> tuple[str, str]:
    """
    Core orchestration logic.
    Returns: (agent_reply_text, new_status)
    """
    import re
    session.turn_count = (session.turn_count or 0) + 1

    # A generated trip uses the same conversation for refinement. Keep this
    # path separate from intake so an edit never accidentally starts a second
    # trip or moves a finished trip back into the confirmation flow.
    if trip.status in (TripStatus.CREATED, TripStatus.DONE) or (
        trip.itinerary_days and _looks_like_plan_edit(user_message)
    ):
        return apply_trip_edit(user_message, trip, session, db)

    # Get full message history for context
    history = db.query(ChatMessage).filter(
        ChatMessage.trip_id == trip.id
    ).order_by(ChatMessage.created_at).all()

    conversation = [{"role": m.role.value, "content": m.content} for m in history]

    # Greetings should open the conversation; they are not a destination.
    is_greeting = bool(re.fullmatch(
        r"(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|greetings)[!. ]*",
        user_message.strip().lower(),
    ))
    if is_greeting:
        slots = session.slot_state or {}
        # A greeting in the middle of intake is not an answer. Reuse the slot
        # that was asked most recently instead of advancing to the next empty
        # slot (for example, "hii" must repeat the destination question).
        next_slot = session.next_slot or next(
            (s for s in SLOT_ORDER if s not in slots and not (s == "child_ages" and not slots.get("travelers_children"))),
            "destination",
        )
        session.next_slot = next_slot
        db.commit()
        if next_slot == "destination":
            if session.turn_count > 1:
                return f"I didn’t catch that. {SLOT_QUESTIONS[next_slot]}", trip.status.value
            return "Hi! Nice to meet you — let’s plan something memorable. Where would you like to go?", trip.status.value
        return f"I didn’t catch that. {SLOT_QUESTIONS[next_slot]}", trip.status.value

    # Build enriched prompt
    context = build_context_prompt(session)
    enriched_system = SYSTEM_PROMPT + "\n" + context

    # Extract any slots from this user message
    previous_slots = dict(session.slot_state or {})
    updated_slots = extract_slots_from_reply(user_message, previous_slots, "")
    if is_invalid_destination(updated_slots.get("destination")):
        updated_slots.pop("destination", None)

    # Resolve short answers against the question that was shown last turn.
    previous_slot = session.next_slot
    if "destination" not in updated_slots:
        # Destination is authoritative. Never let a stale next_slot advance to
        # adults, budget, or another field before a real place is collected.
        previous_slot = "destination"
        session.next_slot = "destination"
    if previous_slot and previous_slot not in updated_slots:
        answer = user_message.strip()
        if previous_slot == "travelers_adults" and answer.lower() in ("no", "skip"):
            updated_slots[previous_slot] = 1
        elif previous_slot == "travelers_children" and answer.lower() in ("no", "none", "skip"):
            updated_slots[previous_slot] = 0
        elif previous_slot == "travelers_children" and answer.lower() in ("yes", "yep"):
            updated_slots[previous_slot] = 1
        elif previous_slot == "starting_city" and answer.lower() in ("no", "none", "skip"):
            updated_slots[previous_slot] = ""
        elif previous_slot in ("travelers_adults", "travelers_children", "days") and re.fullmatch(r"\d+", answer):
            updated_slots[previous_slot] = int(answer)
        elif previous_slot == "budget" and re.fullmatch(r"(?:₹|rs\.?|inr)?\s*[\d,]+(?:k)?", answer, re.I):
            raw = re.sub(r"[^\d]", "", answer)
            updated_slots[previous_slot] = int(raw) * (1000 if answer.lower().rstrip().endswith("k") else 1)
        elif previous_slot == "starting_city" and answer:
            updated_slots[previous_slot] = answer.title()
        elif previous_slot == "destination" and answer:
            candidate = re.sub(
                r"^(?:hello|hi|hey|greetings)\s*[,!-]?\s*",
                "",
                answer,
                flags=re.I,
            )
            candidate = re.sub(
                r"^(?:i\s+want\s+to\s+(?:go|travel)\s+to|i\s+want\s+to\s+visit|visit|travel\s+to|go\s+to|plan\s+(?:a\s+)?trip\s+to)\s+",
                "",
                candidate,
                flags=re.I,
            )
            candidate = re.sub(r"\s+for\s+\d+\s+(?:days?|nights?).*$", "", candidate, flags=re.I).strip(" .,!?")
            if candidate and not is_invalid_destination(candidate) and not is_non_answer(candidate):
                updated_slots[previous_slot] = candidate.title()

    # Check for destination mentions
    destination_keywords = ["rajasthan", "goa", "kerala", "himachal", "jaipur", "delhi",
                           "mumbai", "udaipur", "agra", "varanasi", "kashmir", "ooty",
                           "coorg", "manali", "shimla", "darjeeling", "ladakh", "andaman"]
    for kw in destination_keywords:
        if kw in user_message.lower() and "destination" not in updated_slots:
            updated_slots["destination"] = kw.title()
            break

    # Apply defaults when the traveller explicitly declines a preference.
    if re.search(r"\b(skip|no preference|no dietary restrictions|nothing|none|don't know)\b", user_message.lower()):
        next_slot = next((s for s in SLOT_ORDER if s not in updated_slots and not (s == "child_ages" and not updated_slots.get("travelers_children"))), None)
        if next_slot in DEFAULTS:
            updated_slots[next_slot] = DEFAULTS[next_slot]
    if int(updated_slots.get("travelers_children", 0) or 0) == 0 and "travelers_children" in updated_slots:
        updated_slots["child_ages"] = []

    session.slot_state = updated_slots
    db.commit()

    # The confirmation button sends an explicit confirmation. Handle it
    # deterministically so generation does not depend on another LLM reply.
    is_confirmation = (
        trip.status == TripStatus.CONFIRMING
        and re.search(r"\b(yes|confirm|generate|go ahead|start)\b", user_message.lower())
    )
    is_retry_confirmation = (
        trip.status == TripStatus.FAILED
        and re.search(r"\b(retry|try again|generate|regenerate|start)\b", user_message.lower())
    )

    if is_confirmation or is_retry_confirmation:
        reply = "READY_TO_GENERATE"
    else:
        # Keep intake predictable: one focused question, in the product order.
        # Gemini remains responsible for the actual plan generation below.
        next_slot = next((s for s in SLOT_ORDER if s not in updated_slots and not (s == "child_ages" and not updated_slots.get("travelers_children"))), None)
        if next_slot:
            if next_slot == "destination" and is_invalid_destination(user_message):
                reply = SLOT_QUESTIONS[next_slot]
            elif updated_slots != previous_slots:
                reply = f"Thanks — got it. {SLOT_QUESTIONS[next_slot]}"
            else:
                reply = f"I didn’t quite catch that. {SLOT_QUESTIONS[next_slot]}"
            session.next_slot = next_slot
        else:
            reply = build_confirmation_message(updated_slots)

    # Check special signals
    new_status = trip.status.value

    if "READY_TO_GENERATE" in reply:
        reply = "Perfect! I have everything I need. Let me start building your trip plan... This usually takes 20-40 seconds. I'll update you as I go! 🗺️"
        new_status = "creating"
        trip.status = TripStatus.CREATING
        # Update trip model with collected slots
        _apply_slots_to_trip(trip, updated_slots, db)
        db.commit()
        # Trigger async generation
        # In development, do not enqueue to Redis at all. A broker can accept
        # a message even when no worker is consuming it, leaving the trip in
        # CREATING forever. FastAPI's background task is reliable for the
        # single-process local setup and keeps the HTTP response immediate.
        if settings.DEBUG and background_tasks is not None:
            from app.routers.chat import _generate_plan_in_web_process
            background_tasks.add_task(_generate_plan_in_web_process, trip.id)
            logger.info("Trip %s queued in local background fallback", trip.id)
        else:
            try:
                from app.workers.tasks import generate_trip_plan
                result = generate_trip_plan.delay(trip.id)
                trip.celery_task_id = result.id
                db.commit()
            except Exception as e:
                logger.warning("Celery unavailable; using local background fallback: %s", e)
                if background_tasks is not None:
                    from app.routers.chat import _generate_plan_in_web_process
                    background_tasks.add_task(_generate_plan_in_web_process, trip.id)
                else:
                    # Preserve the direct-service behavior used by tests/scripts.
                    from app.services.generation_service import generate_plan_sync
                    generate_plan_sync(trip.id, db)

    elif "EDIT_REQUEST:" in reply:
        new_status = "draft"
        trip.status = TripStatus.DRAFT
        db.commit()
        reply = reply.replace("EDIT_REQUEST:", "").strip()

    elif trip.status in (TripStatus.DRAFT, TripStatus.COLLECTING):
        # Check if we should move to confirming
        complete = all(s in updated_slots for s in SLOT_ORDER if s != "child_ages" or updated_slots.get("travelers_children", 0) > 0)
        required_filled = all(s in updated_slots for s in REQUIRED_SLOTS)
        if required_filled and complete:
            trip.status = TripStatus.CONFIRMING
            new_status = "confirming"
            db.commit()

    return reply, new_status


def _looks_like_plan_edit(user_message: str) -> bool:
    """Recognize explicit edits even if an older trip has a stale status."""
    text = user_message.lower()
    return bool(
        re.search(r"\b(itinerary|activity|activities|stop|day\s*\d+|hotel|stay|accommodation|restaurant|dining|budget|transport|packing|essential|essentials)\b", text)
        and re.search(r"\b(add|change|edit|update|remove|delete|replace|swap|make|want|in|to|with)\b", text)
    )


def _number_from_text(text: str) -> float | None:
    match = re.search(r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k| lakh|l)?", text.lower())
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").strip()
    if suffix == "k":
        value *= 1000
    elif suffix in ("l", "lakh"):
        value *= 100000
    return value


def _find_activity(trip: Trip, text: str) -> Activity | None:
    lowered = text.lower()
    activities = [activity for day in trip.itinerary_days for activity in day.activities]
    return next((a for a in activities if a.place_name and a.place_name.lower() in lowered), None)


def _find_place(places: list, text: str, name_attr: str = "place_name"):
    lowered = text.lower()
    return next((place for place in places if getattr(place, name_attr, "") and getattr(place, name_attr).lower() in lowered), None)


def _refresh_budget_status(budget: BudgetBreakdown, trip: Trip) -> None:
    budget.total_estimate = sum(float(getattr(budget, key) or 0) for key in ("stay", "food", "transport", "activities", "buffer"))
    limit = float(trip.budget or 0)
    budget.status = "comfortable" if not limit or budget.total_estimate <= limit * 0.9 else "tight" if budget.total_estimate <= limit * 1.05 else "unrealistic"


def _sync_budget_with_plan(trip: Trip, db: Session) -> BudgetBreakdown:
    """Keep the budget as a projection of the editable plan.

    Generated plans contain estimates on the individual records. Rebuilding
    these categories after an edit prevents a renamed/replaced stay, meal,
    activity, or transport leg from leaving the summary out of sync.
    """
    budget = db.query(BudgetBreakdown).filter(BudgetBreakdown.trip_id == trip.id).first()
    if not budget:
        budget = BudgetBreakdown(trip_id=trip.id, buffer=0)
        db.add(budget)

    accommodations = db.query(Accommodation).filter(Accommodation.trip_id == trip.id).all()
    restaurants = db.query(Restaurant).filter(Restaurant.trip_id == trip.id).all()
    legs = db.query(TransportLeg).filter(TransportLeg.trip_id == trip.id).all()
    activities = [activity for day in trip.itinerary_days for activity in day.activities]

    budget.stay = sum(float((hotel.total_cost if hotel.total_cost is not None else (hotel.cost_per_night or 0) * (hotel.nights or 1)) or 0) for hotel in accommodations)
    budget.food = sum(float(restaurant.cost_estimate or 0) for restaurant in restaurants)
    budget.activities = sum(float(activity.cost_estimate or 0) for activity in activities)
    # The upper bound is the safer amount to use when a leg has a range.
    budget.transport = sum(float((leg.cost_max if leg.cost_max is not None else leg.cost_min) or 0) for leg in legs)
    _refresh_budget_status(budget, trip)
    return budget


def _amount_after_keyword(text: str, keywords: str) -> float | None:
    match = re.search(rf"(?:{keywords}).{{0,40}}?(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|l)?", text.lower())
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").strip()
    return value * (1000 if suffix == "k" else 100000 if suffix in ("l", "lakh") else 1)


def _day_number_from_text(text: str) -> int | None:
    match = re.search(r"\bday\s*(\d+|one|two|three|four|five|six|seven|first|second|third|fourth|fifth|sixth|seventh)\b", text.lower())
    if not match:
        return None
    value = match.group(1)
    return int(value) if value.isdigit() else {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
        "first": 1, "second": 2, "third": 3, "fourth": 4,
        "fifth": 5, "sixth": 6, "seventh": 7,
    }[value]


def _requested_activity_name(text: str) -> str:
    """Extract only the place name from a natural-language itinerary edit."""
    cleaned = text.strip(" .,!?")
    match = re.search(
        r"(?:replace\s+.+?\s+with|change\s+.+?\s+to|(?:add|include|visit|go\s+to)\s+)"
        r"(.+?)(?=\s+(?:in|on|for|to)\s+day\b|\s+day\s+(?:\d+|one|two|three|four|five|six|seven|first|second|third|fourth|fifth|sixth|seventh)\b|[.!?]|$)",
        cleaned,
        re.I,
    )
    if not match:
        return ""
    name = match.group(1).strip(" .,!?")
    # Do not persist conversational instructions as an attraction name.
    name = re.sub(r"^(?:visit|go\s+to|add|include)\s+", "", name, flags=re.I)
    name = re.sub(r"\s+(?:you can|you may|please|make changes?|change whatever).*$", "", name, flags=re.I)
    return name.strip(" .,!?")


def _scale_plan_costs(trip: Trip, db: Session, old_total: float, new_budget: float) -> None:
    """Move all editable estimates with the budget so the plan remains coherent."""
    if old_total <= 0 or new_budget <= 0:
        return
    factor = new_budget / old_total
    for activity in [item for day in trip.itinerary_days for item in day.activities]:
        activity.cost_estimate = round(float(activity.cost_estimate or 0) * factor, 2)
    for hotel in db.query(Accommodation).filter(Accommodation.trip_id == trip.id).all():
        if hotel.cost_per_night is not None:
            hotel.cost_per_night = round(hotel.cost_per_night * factor, 2)
        if hotel.total_cost is not None:
            hotel.total_cost = round(hotel.total_cost * factor, 2)
    for restaurant in db.query(Restaurant).filter(Restaurant.trip_id == trip.id).all():
        if restaurant.cost_estimate is not None:
            restaurant.cost_estimate = round(restaurant.cost_estimate * factor, 2)
    for leg in db.query(TransportLeg).filter(TransportLeg.trip_id == trip.id).all():
        if leg.cost_min is not None:
            leg.cost_min = round(leg.cost_min * factor, 2)
        if leg.cost_max is not None:
            leg.cost_max = round(leg.cost_max * factor, 2)


def _repair_malformed_activity_names(trip: Trip) -> None:
    """Repair records created by the old free-form replacement parser."""
    for day in list(trip.itinerary_days):
        for activity in list(day.activities):
            raw_name = (activity.place_name or "").strip()
            match = re.match(
                r"^(?:visit|go\s+to)\s+(.+?)\s+in\s+day\s+(?:\d+|one|two|three|four|five|six|seven|first|second|third|fourth|fifth|sixth|seventh)\b.*$",
                raw_name,
                re.I,
            )
            if not match:
                continue
            clean_name = match.group(1).strip(" .,!?")
            target_number = _day_number_from_text(raw_name)
            target_day = next((item for item in trip.itinerary_days if item.day_number == target_number), None)
            activity.place_name = clean_name
            activity.description = f"Visit {clean_name} as requested."
            if target_day and target_day.id != day.id:
                activity.day = target_day
                activity.slot_order = len(target_day.activities)


def apply_trip_edit(user_message: str, trip: Trip, session: ChatSession, db: Session) -> tuple[str, str]:
    """Apply a natural-language refinement to the generated trip.

    The edit grammar is intentionally forgiving: users can say “remove the
    museum from day 2”, “swap my hotel”, “make transport train”, “add sunscreen
    to essentials”, or “increase budget to 80k”.
    """
    text = user_message.strip()
    lowered = text.lower()
    changed: list[str] = []
    _repair_malformed_activity_names(trip)

    # “Make day 2 three stops and day 3 two stops” is a common itinerary
    # refinement. Keep the first activities and remove extras; if a day needs
    # more stops, clone the last one with a clear placeholder for the user to
    # refine further in chat.
    count_requests = re.findall(r"(?:day\s*)?(\d+)\s*(?:stops?|activities?|things?)\s*(?:in|to|=)\s*(\d+)|day\s*(\d+)\s*(?:in|with|to)\s*(\d+)", lowered)
    ordinal_days = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7}
    ordinal_requests = re.findall(r"(first|second|third|fourth|fifth|sixth|seventh)\s+day\s+(?:in|with|to)\s+(\d+)", lowered)
    parsed_count_requests = [
        (int(request[0] or request[2]), int(request[1] or request[3]))
        for request in count_requests
    ] + [(ordinal_days[day], int(count)) for day, count in ordinal_requests]
    for day_number, wanted in parsed_count_requests:
        day = next((item for item in trip.itinerary_days if item.day_number == day_number), None)
        if not day:
            continue
        activities = list(day.activities)
        if wanted < len(activities):
            for activity_to_remove in activities[wanted:]:
                db.delete(activity_to_remove)
        elif wanted > len(activities) and activities:
            template = activities[-1]
            for index in range(len(activities), wanted):
                db.add(Activity(
                    day_id=day.id,
                    time_slot=template.time_slot,
                    slot_order=index,
                    place_name=f"New stop for Day {day_number}",
                    place_type=template.place_type,
                    description="Added at your request — tell me what you would like to visit here.",
                ))
        changed.append(f"set day {day_number} to {wanted} stops")

    # Budget and transport edits.
    amount = _number_from_text(text)
    budget_request = amount is not None and re.search(r"\b(budget|spend|limit)\b", lowered)
    if budget_request:
        existing_budget = db.query(BudgetBreakdown).filter(BudgetBreakdown.trip_id == trip.id).first()
        previous_estimate = float(existing_budget.total_estimate or 0) if existing_budget else 0
        trip.budget = amount
        _scale_plan_costs(trip, db, previous_estimate, amount)
        changed.append(f"budget to ₹{amount:,.0f}")
    mode = next((m for m in ("flight", "train", "bus", "car", "taxi") if re.search(rf"\b{m}\b", lowered)), None)
    if mode and re.search(r"\b(transport|travel|commute|route|transfer)\b", lowered):
        trip.transport_modes = [mode]
        legs = trip.transport_legs
        for leg in legs:
            leg.mode = mode
        changed.append(f"transport to {mode}")
    transport_amount = _number_from_text(text) if re.search(r"\b(?:transport|travel|commute|route|transfer)\b", lowered) and re.search(r"\b(?:cost|price|fare|₹|rs\.?|inr)\b", lowered) else None
    if transport_amount is not None:
        for leg in trip.transport_legs:
            leg.cost_min = transport_amount
            leg.cost_max = transport_amount
        changed.append(f"transport cost to ₹{transport_amount:,.0f}")

    if budget_request:
        # A new overall budget changes the constraint, not the trip costs.
        _sync_budget_with_plan(trip, db)

    # Packing / travel essentials.
    if re.search(r"\b(pack|packing|essential|essentials|luggage)\b", lowered):
        packing = db.query(PackingList).filter(PackingList.trip_id == trip.id).first()
        if not packing:
            packing = PackingList(trip_id=trip.id, items={})
            db.add(packing)
        items = dict(packing.items or {})
        category_match = re.search(r"(?:under|in|to)\s+(clothing|toiletries|documents|medications|electronics|miscellaneous)", lowered)
        category = category_match.group(1) if category_match else "miscellaneous"
        remove = bool(re.search(r"\b(remove|delete|drop|without)\b", lowered))
        item_match = re.search(r"(?:add|include|remove|delete|drop|without)\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\s+(?:to|from|under|in)\s+(?:the\s+)?(?:packing|essentials|list|clothing|toiletries|documents|medications|electronics|miscellaneous))?[.!?]*$", text, re.I)
        item = item_match.group(1).strip(" .,!?") if item_match else ""
        if item:
            current = list(items.get(category, []))
            if remove:
                current = [value for value in current if value.lower() != item.lower()]
            elif not any(value.lower() == item.lower() for value in current):
                current.append(item)
            items[category] = current
            packing.items = items
            changed.append(("removed" if remove else "added") + f" {item} to essentials")

    # Itinerary edits: remove an activity, or add a named activity to a day.
    activity = _find_activity(trip, lowered)
    day_number = _day_number_from_text(lowered)
    requested_activity = _requested_activity_name(text)
    replacement = re.search(r"\b(?:to|with)\s+(.+?)(?:[.!?]|$)", text, re.I)
    activity_amount = _amount_after_keyword(text, r"(?:cost|price|budget)(?:\s+(?:of|to))?")
    if activity and activity_amount is not None and re.search(r"\b(cost|price)\b", lowered):
        activity.cost_estimate = activity_amount
        changed.append(f"cost of {activity.place_name} to ₹{activity_amount:,.0f}")
    is_add_request = bool(re.search(r"\b(add|include|insert)\b", lowered))
    if requested_activity and not is_add_request and (
        day_number is not None or re.search(r"\b(change|replace|swap|switch|visit|go\s+to)\b", lowered)
    ):
        target_day = next((item for item in trip.itinerary_days if item.day_number == day_number), None) if day_number else None
        target_activity = (target_day.activities[0] if target_day and target_day.activities else None) or activity
        if target_activity:
            old_name = target_activity.place_name
            target_activity.place_name = requested_activity
            target_activity.description = f"Visit {requested_activity} as requested."
            changed.append(f"changed {old_name} to {requested_activity} on day {target_day.day_number if target_day else target_activity.day.day_number}")
        elif target_day:
            db.add(Activity(
                day_id=target_day.id,
                time_slot=TimeSlot.AFTERNOON,
                slot_order=0,
                place_name=requested_activity,
                place_type="attraction",
                description=f"Visit {requested_activity} as requested.",
            ))
            changed.append(f"added {requested_activity} to day {target_day.day_number}")
    elif re.search(r"\b(remove|delete|skip|drop)\b", lowered) and activity:
        db.delete(activity)
        changed.append(f"removed {activity.place_name} from the itinerary")
    elif re.search(r"\b(add|include|insert)\b", lowered) and re.search(r"\b(itinerary|activity|stop|sight|visit)\b", lowered):
        day = next((d for d in trip.itinerary_days if d.day_number == (day_number or 1)), None)
        add_match = re.search(r"(?:add|include|insert)\s+(.+?)(?:\s+to\s+(?:day\s*\d+|the itinerary)|\s+on\s+day\s*\d+|[.!?]|$)", text, re.I)
        name = _requested_activity_name(text) or (add_match.group(1).strip(" .,!?") if add_match else "")
        if day and name:
            db.add(Activity(day_id=day.id, time_slot=TimeSlot.AFTERNOON, slot_order=len(day.activities), place_name=name, place_type="leisure", description="Added at your request."))
            changed.append(f"added {name} to day {day.day_number}")

    # Stays and dining edits. Existing names are preferred so “remove X” is
    # deterministic; new entries are created from the requested name.
    hotels = db.query(Accommodation).filter(Accommodation.trip_id == trip.id).all()
    restaurants = db.query(Restaurant).filter(Restaurant.trip_id == trip.id).all()
    hotel = _find_place(hotels, lowered)
    restaurant = _find_place(restaurants, lowered)
    hotel_amount = _number_from_text(text) if re.search(r"(?:cost|price|₹|rs\.?|inr|per\s+night|/night|nightly)", lowered) else None
    if hotel and hotel_amount is not None:
        hotel.cost_per_night = hotel_amount
        hotel.total_cost = hotel_amount * (hotel.nights or 1)
        changed.append(f"cost of {hotel.place_name} to ₹{hotel_amount:,.0f} per night")
    if hotel and re.search(r"\b(change|replace|switch)\b", lowered) and replacement:
        old_name = hotel.place_name
        hotel.place_name = replacement.group(1).strip(" .,!?")
        changed.append(f"changed stay from {old_name} to {hotel.place_name}")
    elif hotel and re.search(r"\b(remove|delete|drop|cancel)\b", lowered):
        db.delete(hotel)
        changed.append(f"removed {hotel.place_name} from stays")
    elif re.search(r"\b(hotel|stay|accommodation|resort|hostel)\b", lowered):
        add_match = re.search(r"(?:add|change|replace|book)\s+(?:a\s+)?(?:hotel|stay|accommodation|resort|hostel)?\s*(?:to|with)?\s*(.+?)[.!?]*$", text, re.I)
        name = add_match.group(1).strip(" .,!?") if add_match else ""
        if name and not hotel:
            nights_match = re.search(r"(\d+)\s*nights?", lowered)
            nights = int(nights_match.group(1)) if nights_match else 1
            cost = hotel_amount or 0
            db.add(Accommodation(trip_id=trip.id, city=trip.destinations[0].city if trip.destinations else "", place_name=name, place_type="hotel", nights=nights, cost_per_night=cost, total_cost=cost * nights, notes="Added at your request."))
            changed.append(f"added {name} to stays")
    restaurant_amount = _number_from_text(text) if re.search(r"(?:cost|price|₹|rs\.?|inr)", lowered) else None
    if restaurant and restaurant_amount is not None and re.search(r"\b(?:cost|price|₹|rs\.?|inr)\b", lowered):
        restaurant.cost_estimate = restaurant_amount
        changed.append(f"cost of {restaurant.place_name} to ₹{restaurant_amount:,.0f}")
    if restaurant and re.search(r"\b(change|replace|switch)\b", lowered) and replacement:
        old_name = restaurant.place_name
        restaurant.place_name = replacement.group(1).strip(" .,!?")
        changed.append(f"changed dining from {old_name} to {restaurant.place_name}")
    elif restaurant and re.search(r"\b(remove|delete|drop|cancel)\b", lowered):
        db.delete(restaurant)
        changed.append(f"removed {restaurant.place_name} from dining")
    elif re.search(r"\b(dining|restaurant|meal|food)\b", lowered):
        add_match = re.search(r"(?:add|change|replace|book)\s+(?:a\s+)?(?:restaurant|dining|meal)?\s*(?:to|with)?\s*(.+?)[.!?]*$", text, re.I)
        name = add_match.group(1).strip(" .,!?") if add_match else ""
        if name and not restaurant:
            db.add(Restaurant(trip_id=trip.id, city=trip.destinations[0].city if trip.destinations else "", place_name=name, meal_type="dinner", cost_estimate=restaurant_amount or 0, notes="Added at your request."))
            changed.append(f"added {name} to dining")

    # Reconcile all dependent costs after any mutation, including deletes and
    # newly added records. This also creates a breakdown for older trips.
    synced_budget = _sync_budget_with_plan(trip, db)
    if budget_request and trip.budget:
        committed_costs = sum(float(getattr(synced_budget, key) or 0) for key in ("stay", "food", "transport", "activities"))
        synced_budget.buffer = max(0, float(trip.budget) - committed_costs)
        _refresh_budget_status(synced_budget, trip)
    db.commit()
    if not changed:
        if re.search(r"\b(itinerary|activity|activities|stop|day)\b", lowered):
            return ("Sure — what should I change in the itinerary? For example: “make day 2 have 3 stops”, "
                    "“remove the museum from day 2”, or “replace the beach visit with a fort.”", trip.status.value)
        if re.search(r"\b(hotel|stay|accommodation|resort|hostel)\b", lowered):
            return ("Sure — which stay should I add, remove, or replace? Include the hotel name or city.", trip.status.value)
        if re.search(r"\b(dining|restaurant|meal|food)\b", lowered):
            return ("Sure — which dining suggestion should I add, remove, or replace? Include the restaurant or meal.", trip.status.value)
        if re.search(r"\b(budget|transport|travel|route)\b", lowered):
            return ("Sure — tell me the new budget or transport mode. For example: “set budget to ₹50,000” or “use trains.”", trip.status.value)
        if re.search(r"\b(pack|packing|essential|essentials|luggage)\b", lowered):
            return ("Sure — tell me what to add or remove from essentials. For example: “add sunscreen to essentials.”", trip.status.value)
        return ("I can edit the itinerary, stays, dining, budget, transport, or travel essentials. "
                "Try: ‘remove the museum from day 2’, ‘change transport to train’, or ‘add sunscreen to essentials.’", trip.status.value)
    budget_note = (
        f" Budget check: ₹{synced_budget.total_estimate:,.0f} estimated, "
        f"currently {synced_budget.status} against your ₹{trip.budget:,.0f} budget."
        if trip.budget else
        f" Updated estimate: ₹{synced_budget.total_estimate:,.0f}."
    )
    return "Done — I updated " + ", ".join(changed) + "." + budget_note, trip.status.value


def _apply_slots_to_trip(trip: Trip, slots: dict, db: Session):
    """Apply extracted slot values to the Trip model."""
    if "budget" in slots:
        trip.budget = float(slots["budget"])
    if "budget_scope" in slots:
        trip.budget_scope = BudgetScope(slots["budget_scope"])
    if "days" in slots:
        trip.days = int(slots["days"])
    if "travelers_adults" in slots:
        trip.travelers_adults = int(slots["travelers_adults"])
    if "travel_style" in slots:
        from app.models.trip import TravelStyle
        try:
            trip.travel_style = TravelStyle(slots["travel_style"].lower().replace("-", "_"))
        except ValueError:
            pass
    if "interests" in slots:
        trip.interests = slots["interests"] if isinstance(slots["interests"], list) else [slots["interests"]]
    if "diet" in slots:
        trip.diet = slots["diet"] if isinstance(slots["diet"], list) else [slots["diet"]]
    if "travelers_children" in slots:
        trip.travelers_children = int(slots["travelers_children"])
    if "child_ages" in slots:
        trip.child_ages = slots["child_ages"]
    if "start_date" in slots:
        trip.start_month = str(slots["start_date"])
    if "starting_city" in slots:
        trip.starting_city = str(slots["starting_city"])
    if "pace" in slots:
        from app.models.trip import Pace
        try:
            trip.pace = Pace(slots["pace"])
        except ValueError:
            pass
    if "transport_mode" in slots:
        trip.transport_modes = slots["transport_mode"] if isinstance(slots["transport_mode"], list) else [slots["transport_mode"]]
    if "special_requests" in slots:
        trip.special_requests = slots["special_requests"] or None

    # Create destination record
    dest = slots.get("destination")
    if dest:
        trip.title = f"Trip to {dest}"
        existing = db.query(TripDestination).filter(TripDestination.trip_id == trip.id).first()
        if not existing:
            td = TripDestination(trip_id=trip.id, country="India", city=dest, order=0, allocated_days=trip.days or 1)
            db.add(td)
