import unittest

from app.services.chat_service import (
    _day_number_from_text,
    _requested_activity_name,
    extract_slots_from_reply,
    is_invalid_destination,
)


class ChatDestinationTests(unittest.TestCase):
    def test_generic_opening_is_not_a_destination(self):
        slots = extract_slots_from_reply("Hello I want to plan p=my trip", {}, "")
        self.assertNotIn("destination", slots)

    def test_valid_destination_phrases_are_extracted(self):
        self.assertEqual(
            extract_slots_from_reply("I want to visit Rajasthan", {}, "")["destination"],
            "Rajasthan",
        )
        goa_slots = extract_slots_from_reply("Plan a 5-day trip to Goa", {}, "")
        self.assertEqual(goa_slots["destination"], "Goa")
        self.assertEqual(goa_slots["days"], 5)
        self.assertEqual(
            extract_slots_from_reply("Rajasthan", {}, "")["destination"],
            "Rajasthan",
        )

    def test_generic_saved_values_are_invalid(self):
        self.assertTrue(is_invalid_destination("Hello I Want To Plan P=My Trip"))
        self.assertTrue(is_invalid_destination("My Trip"))
        self.assertFalse(is_invalid_destination("Rajasthan"))
        self.assertFalse(is_invalid_destination("Paris"))

    def test_complete_first_message_extracts_all_provided_details(self):
        message = (
            "Generate a personalized 6-day travel itinerary for Goa, India, for 2 adults "
            "with no children, travelling from Ahmedabad in November 2026. The total budget "
            "is ₹40,000 for both travelers. The preferred travel style is mid-range, with "
            "interests in heritage, adventure, food, and nature. Keep the itinerary relaxed "
            "and include vegetarian food options, suitable accommodation, flights from "
            "Ahmedabad to Goa, local transportation, sightseeing activities, and a day-by-day plan."
        )
        slots = extract_slots_from_reply(message, {}, "")
        self.assertEqual(slots["destination"], "Goa")
        self.assertEqual(slots["budget"], 40000)
        self.assertEqual(slots["days"], 6)
        self.assertEqual(slots["travelers_adults"], 2)
        self.assertEqual(slots["travelers_children"], 0)
        self.assertEqual(slots["starting_city"], "Ahmedabad")
        self.assertEqual(slots["start_date"], "november 2026")
        self.assertEqual(slots["travel_style"], "mid_range")
        self.assertEqual(slots["pace"], "relaxed")
        self.assertEqual(slots["diet"], "vegetarian")


class ChatEditParsingTests(unittest.TestCase):
    def test_activity_edit_drops_instruction_text(self):
        message = "change itinerary to visit Sabarmati Ashram in day three you can make change whatever you want"
        self.assertEqual(_requested_activity_name(message), "Sabarmati Ashram")
        self.assertEqual(_day_number_from_text(message), 3)

    def test_activity_add_stops_at_day_reference(self):
        message = "add sunset point to day 1"
        self.assertEqual(_requested_activity_name(message), "sunset point")
        self.assertEqual(_day_number_from_text(message), 1)

    def test_visit_instruction_is_a_plan_edit(self):
        message = "visit Sabarmati Riverfront in day 3 so make change in that"
        self.assertEqual(_requested_activity_name(message), "Sabarmati Riverfront")
        self.assertEqual(_day_number_from_text(message), 3)


if __name__ == "__main__":
    unittest.main()
