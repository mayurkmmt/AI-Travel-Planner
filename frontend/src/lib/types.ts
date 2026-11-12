export interface TripDestination {
  id: number;
  city?: string;
  state?: string;
  country: string;
  allocated_days: number;
}

export interface Trip {
  id: number;
  title: string;
  status: string;
  budget?: number;
  days?: number;
  travelers_adults: number;
  travelers_children: number;
  travel_style?: string;
  pace?: string;
  interests: string[];
  transport_modes?: string[];
  special_requests?: string;
  thumbnail_url?: string;
  destinations: TripDestination[];
}

export interface Activity {
  id: number;
  time_slot: "morning" | "afternoon" | "evening";
  start_time?: string;
  place_name: string;
  place_type?: string;
  description?: string;
  cost_estimate: number;
  duration_minutes: number;
  travel_minutes_to_next: number;
  tips?: string;
}

export interface ItineraryDay {
  id: number;
  day_number: number;
  city?: string;
  theme?: string;
  summary?: string;
  activities: Activity[];
}

export interface Hotel {
  id: number;
  city: string;
  place_name: string;
  place_type?: string;
  cost_per_night?: number;
  nights: number;
  total_cost?: number;
  notes?: string;
}

export interface Restaurant {
  id: number;
  city: string;
  day_number?: number;
  meal_type?: string;
  place_name: string;
  cuisine?: string;
  cost_estimate: number;
  notes?: string;
}

export interface BudgetBreakdown {
  stay: number;
  food: number;
  transport: number;
  activities: number;
  buffer: number;
  total_estimate: number;
  status: "comfortable" | "tight" | "unrealistic";
}

export interface WeatherSnapshot {
  city: string;
  month?: string;
  temp_min?: number;
  temp_max?: number;
  condition?: string;
  advice?: string;
}

export interface PackingList {
  [category: string]: string[];
}
