import streamlit as st
import requests
import ollama  # Ensure you have Ollama installed and running
import uuid
import datetime
import neo4j
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
        
        try:
            self.neo4j_driver = neo4j.GraphDatabase.driver(
                "bolt://localhost:7687", 
                auth=("neo4j", "1e_mRSKgAF-LOm_1Z_jmrjGJcRE8lXwCx0I2prKwGyY")
            )
        except Exception as e:
            st.error(f"Neo4j Connection Error: {e}")
            self.neo4j_driver = None

    def query_ollama_model(self, prompt: str) -> str:
        """Function to query Ollama for generating responses."""
        try:
            # Using Ollama to generate responses from the model
            response = ollama.chat(
                model='llama3.2',  # Replace with the correct model name
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response['message']['content']  # Return the model's response
        except Exception as e:
            st.error(f"Error querying Ollama: {e}")
            return "Sorry, I couldn't process that."

    def get_weather(self, city: str) -> Dict[str, Any]:
        """Fetch weather information for the given city."""
        try:
            #api_key = st.secrets.get("OPENWEATHER_API_KEY", "your_openweather_api_key")
            api_key = 'b70f1a98fdea996089fbd445af2a835a'
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

    def get_news(self) -> Dict[str, Any]:
        """Fetch the latest news using an API."""
        try:
            #api_key = st.secrets.get("NEWS_API_KEY", "your_news_api_key")
            api_key = '92435d2f9e734d0997164bec672c4450'
            response = requests.get(
                f"https://newsapi.org/v2/top-headlines?country=us&apiKey={api_key}"
            )
            data = response.json()
            articles = []
            for article in data['articles'][:5]:
                articles.append({
                    "title": article['title'],
                    "description": article['description'],
                    "url": article['url']
                })
            return articles
        except Exception as e:
            st.error(f"News fetch error: {e}")
            return []

    def generate_itinerary(self, city: str, interests: List[str], budget: float, date: datetime.date) -> Dict[str, Any]:
        """Generate a personalized itinerary using Ollama."""
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

            itinerary = self.query_ollama_model(prompt)  # Query Ollama for the itinerary
            return {
                "raw_itinerary": itinerary,
                "city": city,
                "date": date,
                "budget": budget,
                "interests": interests
            }
        except Exception as e:
            st.error(f"Itinerary generation error: {e}")
            return {"raw_itinerary": "Unable to generate itinerary"}

    def optimize_route(self, origin: str, destination: str) -> Dict[str, Any]:
        """Optimize travel route using OpenStreet API."""
        try:
            response = requests.get(
                f"https://api.openstreetmap.org/routing/v1/driving?start={origin}&end={destination}"
            )
            data = response.json()
            # Example: Extracting distance and time from response
            distance = data['routes'][0]['summary']['distance']
            time = data['routes'][0]['summary']['duration']
            return {
                "distance": distance,
                "time": time,
                "route": data['routes'][0]['legs'][0]['steps']
            }
        except Exception as e:
            st.error(f"Route optimization error: {e}")
            return {"distance": "N/A", "time": "N/A", "route": "Unable to optimize"}
    def save_trip_memory(self, trip_details: Dict[str, Any]):
        """Save trip details to the Neo4j graph database."""
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
        """Main Streamlit application."""
        st.title("🌍 Personalized Tour Planner")
        
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
            response = self.query_ollama_model(f"You are a helpful travel assistant. Context: {context}. {prompt}")
            
            # Display and store AI response
            with st.chat_message("assistant"):
                st.markdown(response)
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response
            })
        
        except Exception as e:
            st.error(f"Error generating response: {e}")

def main():
    app = TourPlannerApp()
    app.run()

if __name__ == "__main__":
    main()
