"""
Comprehensive API endpoint tests for AI Travel Planner.
Covers: auth, chat, trips (CRUD, duplicate, share, regenerate, sub-resources).
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from tests.conftest import _TestSession
from app.models.trip import Trip, TripStatus, TripDestination
from app.models.user import User
from app.models.itinerary import ItineraryDay, Activity, PackingList, BudgetBreakdown, TransportLeg, TimeSlot
from app.models.place import Accommodation, Restaurant
from app.models.extra import WeatherSnapshot

client = TestClient(app, raise_server_exceptions=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _register(email="test@example.com", password="password123", name="Test User"):
    return client.post("/api/auth/register", json={
        "email": email, "password": password, "full_name": name
    })


def _login(email="test@example.com", password="password123"):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def _auth_headers(email="test@example.com", password="password123"):
    _register(email, password, email.split("@")[0].replace(".", " ").title())
    res = _login(email, password)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_trip(headers, email="test@example.com"):
    """Create a trip with a destination directly in DB for testing sub-resources."""
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == email).first()
        trip = Trip(
            user_id=user.id,
            title="Test Trip",
            status=TripStatus.CREATED,
            budget=20000,
            days=3,
            travelers_adults=2,
        )
        db.add(trip)
        db.flush()
        dest = TripDestination(trip_id=trip.id, city="Goa", state="Goa", country="India", allocated_days=3)
        db.add(dest)
        db.commit()
        return trip.id
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthRegister:
    def test_register_success(self):
        res = _register()
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["full_name"] == "Test User"

    def test_register_duplicate_email(self):
        _register()
        res = _register()
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()

    def test_register_missing_fields(self):
        res = client.post("/api/auth/register", json={"email": "a@b.com"})
        assert res.status_code == 422

    def test_register_invalid_email(self):
        res = client.post("/api/auth/register", json={
            "email": "not-an-email", "password": "password123", "full_name": "Test"
        })
        assert res.status_code == 422


class TestAuthLogin:
    def test_login_success(self):
        _register()
        res = _login()
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_login_wrong_password(self):
        _register()
        res = _login(password="wrongpassword")
        assert res.status_code == 401

    def test_login_unknown_email(self):
        res = _login(email="nobody@example.com")
        assert res.status_code == 401

    def test_login_returns_user_info(self):
        _register()
        res = _login()
        assert res.json()["user"]["email"] == "test@example.com"


class TestAuthMe:
    def test_get_me_authenticated(self):
        headers = _auth_headers()
        res = client.get("/api/auth/me", headers=headers)
        assert res.status_code == 200
        assert res.json()["email"] == "test@example.com"

    def test_get_me_unauthenticated(self):
        res = client.get("/api/auth/me")
        assert res.status_code == 401

    def test_get_me_invalid_token(self):
        res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert res.status_code == 401


class TestAuthForgotPassword:
    def test_forgot_password_existing_email(self):
        _register()
        res = client.post("/api/auth/forgot-password", json={"email": "test@example.com"})
        assert res.status_code == 200
        assert "reset link" in res.json()["message"].lower()

    def test_forgot_password_unknown_email_same_response(self):
        # Must not reveal whether account exists
        res = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        assert res.status_code == 200
        assert "reset link" in res.json()["message"].lower()


class TestAuthResetPassword:
    def test_reset_password_invalid_token(self):
        res = client.post("/api/auth/reset-password", json={
            "token": "invalidtoken", "password": "newpassword123"
        })
        assert res.status_code == 400

    def test_reset_password_too_short(self):
        res = client.post("/api/auth/reset-password", json={
            "token": "sometoken", "password": "short"
        })
        assert res.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# CHAT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

class TestChatSend:
    def test_send_message_creates_trip(self):
        headers = _auth_headers()
        mock_reply = ("Hi! Where would you like to go?", "collecting")
        with patch("app.services.chat_service.process_message", return_value=mock_reply):
            res = client.post("/api/chat/", json={"message": "I want to visit Goa"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "trip_id" in data
        assert data["trip_id"] is not None
        assert "agent_reply" in data

    def test_send_message_unauthenticated(self):
        res = client.post("/api/chat/", json={"message": "Hello"})
        assert res.status_code == 401

    def test_send_message_empty_rejected(self):
        headers = _auth_headers()
        res = client.post("/api/chat/", json={"message": ""}, headers=headers)
        assert res.status_code == 422

    def test_send_message_to_existing_trip(self):
        headers = _auth_headers()
        mock_reply = ("Tell me your budget.", "collecting")
        with patch("app.services.chat_service.process_message", return_value=mock_reply):
            res1 = client.post("/api/chat/", json={"message": "I want to visit Goa"}, headers=headers)
            trip_id = res1.json()["trip_id"]
            res2 = client.post("/api/chat/", json={"message": "5 days", "trip_id": trip_id}, headers=headers)
        assert res2.status_code == 200
        assert res2.json()["trip_id"] == trip_id

    def test_send_message_to_other_users_trip(self):
        headers1 = _auth_headers("user1@example.com")
        headers2 = _auth_headers("user2@example.com")
        mock_reply = ("Hi!", "collecting")
        with patch("app.services.chat_service.process_message", return_value=mock_reply):
            res = client.post("/api/chat/", json={"message": "Goa"}, headers=headers1)
            trip_id = res.json()["trip_id"]
        res2 = client.post("/api/chat/", json={"message": "Hello", "trip_id": trip_id}, headers=headers2)
        assert res2.status_code == 404


class TestChatHistory:
    def test_get_history_empty(self):
        headers = _auth_headers()
        mock_reply = ("Hi!", "collecting")
        with patch("app.services.chat_service.process_message", return_value=mock_reply):
            res = client.post("/api/chat/", json={"message": "Goa"}, headers=headers)
            trip_id = res.json()["trip_id"]
        res2 = client.get(f"/api/chat/{trip_id}/history/", headers=headers)
        assert res2.status_code == 200
        data = res2.json()
        assert "messages" in data
        assert data["trip_id"] == trip_id

    def test_get_history_unauthenticated(self):
        res = client.get("/api/chat/999/history/")
        assert res.status_code == 401

    def test_get_history_not_found(self):
        headers = _auth_headers()
        res = client.get("/api/chat/99999/history/", headers=headers)
        assert res.status_code == 404

    def test_get_history_other_users_trip(self):
        headers1 = _auth_headers("h1@example.com")
        headers2 = _auth_headers("h2@example.com")
        mock_reply = ("Hi!", "collecting")
        with patch("app.services.chat_service.process_message", return_value=mock_reply):
            res = client.post("/api/chat/", json={"message": "Goa"}, headers=headers1)
            trip_id = res.json()["trip_id"]
        res2 = client.get(f"/api/chat/{trip_id}/history/", headers=headers2)
        assert res2.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# TRIPS ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

class TestTripsList:
    def test_list_trips_empty(self):
        headers = _auth_headers()
        res = client.get("/api/trips/", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []
        assert data["counts"]["all"] == 0

    def test_list_trips_unauthenticated(self):
        res = client.get("/api/trips/")
        assert res.status_code == 401

    def test_list_trips_pagination(self):
        headers = _auth_headers()
        res = client.get("/api/trips/?page=1&page_size=5", headers=headers)
        assert res.status_code == 200
        assert "total_pages" in res.json()

    def test_list_trips_invalid_status_filter(self):
        headers = _auth_headers()
        res = client.get("/api/trips/?status=invalid", headers=headers)
        assert res.status_code == 400

    def test_list_trips_filter_created(self):
        headers = _auth_headers()
        res = client.get("/api/trips/?status=created", headers=headers)
        assert res.status_code == 200

    def test_list_trips_filter_drafts(self):
        headers = _auth_headers()
        res = client.get("/api/trips/?status=drafts", headers=headers)
        assert res.status_code == 200


class TestTripsGet:
    def test_get_trip_success(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.get(f"/api/trips/{trip_id}/", headers=headers)
        assert res.status_code == 200
        assert res.json()["id"] == trip_id

    def test_get_trip_not_found(self):
        headers = _auth_headers()
        res = client.get("/api/trips/99999/", headers=headers)
        assert res.status_code == 404

    def test_get_trip_other_user(self):
        headers1 = _auth_headers("owner@example.com")
        headers2 = _auth_headers("other@example.com")
        trip_id = _create_trip(headers1, email="owner@example.com")
        res = client.get(f"/api/trips/{trip_id}/", headers=headers2)
        assert res.status_code == 404

    def test_get_trip_unauthenticated(self):
        res = client.get("/api/trips/1/")
        assert res.status_code == 401


class TestTripsStatus:
    def test_get_status_success(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.get(f"/api/trips/{trip_id}/status/", headers=headers)
        assert res.status_code == 200
        assert "status" in res.json()

    def test_get_status_not_found(self):
        headers = _auth_headers()
        res = client.get("/api/trips/99999/status/", headers=headers)
        assert res.status_code == 404


class TestTripsPatch:
    def test_patch_title(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.patch(f"/api/trips/{trip_id}/", json={"title": "New Title"}, headers=headers)
        assert res.status_code == 200
        assert res.json()["title"] == "New Title"

    def test_patch_not_found(self):
        headers = _auth_headers()
        res = client.patch("/api/trips/99999/", json={"title": "X"}, headers=headers)
        assert res.status_code == 404

    def test_patch_other_users_trip(self):
        headers1 = _auth_headers("p1@example.com")
        headers2 = _auth_headers("p2@example.com")
        trip_id = _create_trip(headers1, email="p1@example.com")
        res = client.patch(f"/api/trips/{trip_id}/", json={"title": "Hack"}, headers=headers2)
        assert res.status_code == 404


class TestTripsDelete:
    def test_delete_trip_success(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.delete(f"/api/trips/{trip_id}/", headers=headers)
        assert res.status_code == 204
        res2 = client.get(f"/api/trips/{trip_id}/", headers=headers)
        assert res2.status_code == 404

    def test_delete_trip_not_found(self):
        headers = _auth_headers()
        res = client.delete("/api/trips/99999/", headers=headers)
        assert res.status_code == 404

    def test_delete_other_users_trip(self):
        headers1 = _auth_headers("d1@example.com")
        headers2 = _auth_headers("d2@example.com")
        trip_id = _create_trip(headers1, email="d1@example.com")
        res = client.delete(f"/api/trips/{trip_id}/", headers=headers2)
        assert res.status_code == 404

    def test_delete_unauthenticated(self):
        res = client.delete("/api/trips/1/")
        assert res.status_code == 401


class TestTripsDuplicate:
    def test_duplicate_trip_success(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.post(f"/api/trips/{trip_id}/duplicate/", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] != trip_id
        assert "(copy)" in data["title"]
        assert data["status"] == "draft"

    def test_duplicate_copies_destinations(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.post(f"/api/trips/{trip_id}/duplicate/", headers=headers)
        new_id = res.json()["id"]
        res2 = client.get(f"/api/trips/{new_id}/", headers=headers)
        assert len(res2.json()["destinations"]) > 0
        assert res2.json()["destinations"][0]["city"] == "Goa"

    def test_duplicate_copies_budget_and_days(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.post(f"/api/trips/{trip_id}/duplicate/", headers=headers)
        data = res.json()
        assert data["budget"] == 20000
        assert data["days"] == 3

    def test_duplicate_not_found(self):
        headers = _auth_headers()
        res = client.post("/api/trips/99999/duplicate/", headers=headers)
        assert res.status_code == 404

    def test_duplicate_other_users_trip(self):
        headers1 = _auth_headers("dup1@example.com")
        headers2 = _auth_headers("dup2@example.com")
        trip_id = _create_trip(headers1, email="dup1@example.com")
        res = client.post(f"/api/trips/{trip_id}/duplicate/", headers=headers2)
        assert res.status_code == 404


class TestTripsShare:
    def test_create_share_link(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.post(f"/api/trips/{trip_id}/share/", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "token" in data
        assert "url" in data

    def test_create_share_idempotent(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res1 = client.post(f"/api/trips/{trip_id}/share/", headers=headers)
        res2 = client.post(f"/api/trips/{trip_id}/share/", headers=headers)
        assert res1.json()["token"] == res2.json()["token"]

    def test_revoke_share(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        client.post(f"/api/trips/{trip_id}/share/", headers=headers)
        res = client.delete(f"/api/trips/{trip_id}/share/", headers=headers)
        assert res.status_code == 204

    def test_share_not_found(self):
        headers = _auth_headers()
        res = client.post("/api/trips/99999/share/", headers=headers)
        assert res.status_code == 404


class TestTripsSubResources:
    """Tests for itinerary, hotels, restaurants, budget, weather, packing-list, map."""

    def _setup(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        db = _TestSession()
        try:
            # Add itinerary day + activity
            day = ItineraryDay(trip_id=trip_id, day_number=1, city="Goa", theme="Beaches")
            db.add(day)
            db.flush()
            act = Activity(
                day_id=day.id, time_slot=TimeSlot.MORNING, slot_order=0,
                place_name="Baga Beach", cost_estimate=0, duration_minutes=120,
                travel_minutes_to_next=15,
            )
            db.add(act)
            # Hotel
            db.add(Accommodation(trip_id=trip_id, city="Goa", place_name="Beach Resort",
                                  cost_per_night=2000, nights=3))
            # Restaurant
            db.add(Restaurant(trip_id=trip_id, city="Goa", place_name="Fisherman's Wharf",
                               meal_type="dinner", cost_estimate=500))
            # Budget
            db.add(BudgetBreakdown(trip_id=trip_id, stay=6000, food=3000, transport=2000,
                                    activities=1000, buffer=500, total_estimate=12500, status="comfortable"))
            # Transport leg
            db.add(TransportLeg(trip_id=trip_id, from_city="Mumbai", to_city="Goa",
                                 mode="flight", duration_minutes=60, cost_min=3000, cost_max=6000))
            # Weather
            db.add(WeatherSnapshot(trip_id=trip_id, city="Goa", month="December",
                                    temp_min=22, temp_max=32, condition="Sunny"))
            # Packing list
            db.add(PackingList(trip_id=trip_id, items={"clothing": ["t-shirts", "shorts"]}))
            db.commit()
        finally:
            db.close()
        return headers, trip_id

    def test_get_itinerary(self):
        headers, trip_id = self._setup()
        res = client.get(f"/api/trips/{trip_id}/itinerary/", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data["days"]) == 1
        assert data["days"][0]["city"] == "Goa"
        assert len(data["days"][0]["activities"]) == 1

    def test_get_hotels(self):
        headers, trip_id = self._setup()
        res = client.get(f"/api/trips/{trip_id}/hotels/", headers=headers)
        assert res.status_code == 200
        assert len(res.json()["hotels"]) == 1
        assert res.json()["hotels"][0]["place_name"] == "Beach Resort"

    def test_get_restaurants(self):
        headers, trip_id = self._setup()
        res = client.get(f"/api/trips/{trip_id}/restaurants/", headers=headers)
        assert res.status_code == 200
        assert len(res.json()["restaurants"]) == 1

    def test_get_budget(self):
        headers, trip_id = self._setup()
        res = client.get(f"/api/trips/{trip_id}/budget/", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["budget_breakdown"]["total_estimate"] == 12500
        assert data["budget_breakdown"]["status"] == "comfortable"

    def test_get_weather(self):
        headers, trip_id = self._setup()
        res = client.get(f"/api/trips/{trip_id}/weather/", headers=headers)
        assert res.status_code == 200
        assert len(res.json()["weather"]) == 1
        assert res.json()["weather"][0]["city"] == "Goa"

    def test_get_packing_list(self):
        headers, trip_id = self._setup()
        res = client.get(f"/api/trips/{trip_id}/packing-list/", headers=headers)
        assert res.status_code == 200
        assert "clothing" in res.json()["packing_list"]

    def test_get_map(self):
        headers, trip_id = self._setup()
        res = client.get(f"/api/trips/{trip_id}/map/", headers=headers)
        assert res.status_code == 200
        assert res.json()["type"] == "FeatureCollection"

    def test_get_itinerary_not_found(self):
        headers = _auth_headers()
        res = client.get("/api/trips/99999/itinerary/", headers=headers)
        assert res.status_code == 404

    def test_get_budget_no_breakdown(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.get(f"/api/trips/{trip_id}/budget/", headers=headers)
        assert res.status_code == 200
        assert res.json()["budget_breakdown"] is None

    def test_get_packing_list_empty(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        res = client.get(f"/api/trips/{trip_id}/packing-list/", headers=headers)
        assert res.status_code == 200
        assert res.json()["packing_list"] == {}


class TestTripsRegenerate:
    def test_regenerate_updates_params(self):
        headers = _auth_headers()
        trip_id = _create_trip(headers)
        with patch("app.routers.chat._generate_plan_in_web_process"):
            res = client.post(f"/api/trips/{trip_id}/regenerate/", json={
                "budget": 30000, "days": 5, "travelers_adults": 3
            }, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "creating"

    def test_regenerate_not_found(self):
        headers = _auth_headers()
        res = client.post("/api/trips/99999/regenerate/", json={}, headers=headers)
        assert res.status_code == 404

    def test_regenerate_other_users_trip(self):
        headers1 = _auth_headers("rg1@example.com")
        headers2 = _auth_headers("rg2@example.com")
        trip_id = _create_trip(headers1, email="rg1@example.com")
        res = client.post(f"/api/trips/{trip_id}/regenerate/", json={}, headers=headers2)
        assert res.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
