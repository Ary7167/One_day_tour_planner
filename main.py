import streamlit as st
import ollama
import neo4j
import requests
import datetime
import uuid
from typing import Dict, List, Any

class TourPlannerApp:
    def __init__(self):
        # Initialize session state
        if 'user_id' not in st.session_state:
            st.session_state.user_id = str(uuid.uuid4())
        
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        
        if 'current_trip' not in st.session_state:
            st.session_state.current_trip = {}
        
        # Neo4j Connection (replace with your credentials)
        try:
            self.neo4j_driver = neo4j.GraphDatabase.driver(
                "bolt://localhost:7687", 
                auth=("neo4j", "your_neo4j_password")
            )
        except Exception as e:
            st.error(f"Neo4j Connection Error: {e}")
            self.neo4j_driver = None

    def get_weather(self, city: str) -> Dict[str, Any]:
        """Fetch weather information for the given city"""
        try:
            api_key = st.secrets.get("OPENWEATHER_API_KEY", "your_openweather_api_key")
            response = requests.get(
                f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
            )
            data = response.json()
            return {
                "temperature": data['main']['temp'],
                "description": data['weather'][0]['description'],
                "feels_like": data['main']['feels_like'],
                "humidity": data['main']['humidity']
            }
        except Exception as e:
            st.error(f"Weather fetch error: {e}")
            return {"temperature": "N/A", "description": "Unable to fetch"}

    def generate_itinerary(self, city: str, interests: List[str], budget: float, date: datetime.date) -> Dict[str, Any]:
        """Generate a personalized itinerary using Ollama"""
        try:
            # Prepare a comprehensive prompt for itinerary generation
            prompt = (
                f"Create a detailed one-day tour itinerary for {city} on {date}. "
                f"Traveler interests: {', '.join(interests)}. "
                f"Total budget: ${budget}. "
                "Provide: "
                "1. List of attractions with timings "
                "2. Estimated travel time between locations "
                "3. Budget breakdown "
                "4. Recommended lunch spot "
                "5. Tips for the day"
            )

            response = ollama.chat(
                model='llama2',
                messages=[{'role': 'user', 'content': prompt}]
            )

            return {
                "raw_itinerary": response['message']['content'],
                "city": city,
                "date": date,
                "budget": budget,
                "interests": interests
            }
        except Exception as e:
            st.error(f"Itinerary generation error: {e}")
            return {"raw_itinerary": "Unable to generate itinerary"}

    def save_trip_memory(self, trip_details: Dict[str, Any]):
        """Save trip details to Neo4j graph database"""
        if not self.neo4j_driver:
            st.warning("Neo4j not connected. Cannot save trip memory.")
            return

        with self.neo4j_driver.session() as session:
            try:
                session.run(
                    """
                    MERGE (u:User {id: $user_id})
                    MERGE (t:Trip {
                        city: $city, 
                        date: $date, 
                        unique_id: $unique_id
                    })
                    MERGE (u)-[:TOOK_TRIP]->(t)
                    SET t.budget = $budget,
                        t.interests = $interests,
                        t.itinerary = $itinerary
                    """,
                    user_id=st.session_state.user_id,
                    city=trip_details['city'],
                    date=str(trip_details['date']),
                    unique_id=str(uuid.uuid4()),
                    budget=trip_details['budget'],
                    interests=trip_details['interests'],
                    itinerary=trip_details.get('raw_itinerary', '')
                )
                st.success("Trip memory saved successfully!")
            except Exception as e:
                st.error(f"Error saving trip memory: {e}")

    def run(self):
        """Main Streamlit application"""
        st.title("🌍 Personalized Tour Planner")

        # Sidebar for trip planning
        with st.sidebar:
            st.header("Plan Your Trip")
            city = st.text_input("Destination City", placeholder="Rome, Paris...")
            travel_date = st.date_input("Travel Date", datetime.date.today())
            interests = st.multiselect(
                "Your Interests", 
                ["Historical Sites", "Food", "Nature", "Shopping", "Art", "Museums"]
            )
            budget = st.number_input("Total Budget ($)", min_value=50, max_value=1000, value=200)

            # Plan Trip Button
            if st.button("Generate Trip Plan"):
                if city and interests:
                    # Generate Itinerary
                    itinerary = self.generate_itinerary(city, interests, budget, travel_date)
                    st.session_state.current_trip = itinerary

                    # Get Weather
                    weather = self.get_weather(city)

                    # Display Results
                    st.subheader(f"🌞 Weather in {city}")
                    st.write(f"Temperature: {weather['temperature']}°C")
                    st.write(f"Conditions: {weather['description']}")

                    st.subheader("📍 Your Personalized Itinerary")
                    st.write(itinerary['raw_itinerary'])

                    # Save Trip to Memory
                    self.save_trip_memory(itinerary)
                else:
                    st.warning("Please enter a city and select interests")

        # Conversation Interface
        st.header("Trip Assistant")
        
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # User input
        if prompt := st.chat_input("Ask about your trip or get recommendations"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Context-aware response generation
            context = {
                "current_trip": st.session_state.get('current_trip', {}),
                "chat_history": st.session_state.messages
            }
            
            try:
                # Generate response using Ollama with context
                response = ollama.chat(
                    model='llama2',
                    messages=[
                        {'role': 'system', 'content': f"You are a helpful travel assistant. Context: {context}"},
                        {'role': 'user', 'content': prompt}
                    ]
                )
                
                # Display and store AI response
                with st.chat_message("assistant"):
                    st.markdown(response['message']['content'])
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response['message']['content']
                })
            
            except Exception as e:
                st.error(f"Error generating response: {e}")

def main():
    app = TourPlannerApp()
    app.run()

if __name__ == "__main__":
    main()
