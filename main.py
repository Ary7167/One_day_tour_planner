import streamlit as st
from neo4j import GraphDatabase
import openai
import requests

# Initialize global variables
OPENROUTESERVICE_API_KEY = "5b3ce3597851110001cf6248dc52e38cd7b94d699918c3320add5a78"  # Replace with your ORS API key
NEO4J_BOLT_URL = "neo4j+s://490a924f.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "1e_mRSKgAF-LOm_1Z_jmrjGJcRE8lXwCx0I2prKwGyY"
WEATHER_API_KEY = "b70f1a98fdea996089fbd445af2a835a"  # Replace with your OpenWeatherMap API key
NEWS_API_KEY = "92435d2f9e734d0997164bec672c4450"  # Replace with your NewsAPI key

class TourPlanner:
    def __init__(self):
        self.neo4j_driver = GraphDatabase.driver(
            NEO4J_BOLT_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    
    def close(self):
        self.neo4j_driver.close()

    def add_location(self, location_name, coordinates):
        """
        Add a location node to the Neo4j database.
        """
        query = """
        MERGE (loc:Location {name: $name, latitude: $lat, longitude: $lng})
        RETURN loc
        """
        with self.neo4j_driver.session() as session:
            session.run(query, name=location_name, lat=coordinates[0], lng=coordinates[1])
        st.success(f"Location '{location_name}' added to the database.")

    def optimize_route(self, locations):
        """
        Optimize route using OpenRouteService API.
        :param locations: List of tuples [(lat, lng), ...]
        """
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Authorization": OPENROUTESERVICE_API_KEY}
        payload = {
            "coordinates": locations,
            "format": "geojson",
            "options": {"optimize_waypoints": True},
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Extract the optimized coordinates
            optimized_route = [
                (step["geometry"]["coordinates"][1], step["geometry"]["coordinates"][0])
                for step in data["features"][0]["geometry"]["coordinates"]
            ]
            return optimized_route
        else:
            st.error(f"Error: {response.json()}")
            return None

    def display_map(self, locations, optimized_route=None):
        """
        Display the locations and optionally the optimized route on a map.
        """
        import folium
        from streamlit_folium import st_folium

        m = folium.Map(location=locations[0], zoom_start=12)

        # Add locations to the map
        for idx, loc in enumerate(locations):
            folium.Marker(loc, popup=f"Location {idx + 1}").add_to(m)

        # Draw optimized route
        if optimized_route:
            folium.PolyLine(
                optimized_route, color="blue", weight=2.5, opacity=1
            ).add_to(m)

        # Display map in Streamlit
        st_folium(m, width=700, height=500)

    def get_weather(self, city):
        """
        Get weather information using OpenWeatherMap API.
        :param city: Name of the city to get weather info
        """
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            weather_info = {
                "city": city,
                "temperature": data["main"]["temp"],
                "humidity": data["main"]["humidity"],
                "description": data["weather"][0]["description"],
            }
            return weather_info
        else:
            st.error(f"Error: {response.json()}")
            return None

    def get_news(self, query):
        """
        Get latest news articles using NewsAPI.
        :param query: Search query for news topics
        """
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            articles = data["articles"]
            return articles
        else:
            st.error(f"Error: {response.json()}")
            return None

# Streamlit UI
def main():
    st.title("Tour Planner with Route Optimization, Weather, and News")
    planner = TourPlanner()

    with st.sidebar:
        st.header("Add Locations")
        location_name = st.text_input("Location Name")
        latitude = st.number_input("Latitude", format="%.6f")
        longitude = st.number_input("Longitude", format="%.6f")
        if st.button("Add Location"):
            if location_name and latitude and longitude:
                planner.add_location(location_name, (latitude, longitude))
            else:
                st.error("Please enter all details.")

    st.header("Optimize Route")
    with st.form("route_form"):
        st.write("Enter the locations for optimization (Latitude, Longitude):")
        locations = []
        for i in range(3):  # Allow up to 3 locations
            col1, col2 = st.columns(2)
            lat = col1.number_input(f"Latitude {i+1}", format="%.6f")
            lng = col2.number_input(f"Longitude {i+1}", format="%.6f")
            if lat and lng:
                locations.append((lat, lng))

        submitted = st.form_submit_button("Optimize Route")
        if submitted:
            if len(locations) < 2:
                st.error("Please add at least two locations.")
            else:
                optimized_route = planner.optimize_route(locations)
                if optimized_route:
                    st.success("Route optimized successfully!")
                    planner.display_map(locations, optimized_route)

    st.header("Weather Information")
    city = st.text_input("Enter city for weather information", "")
    if city:
        weather_info = planner.get_weather(city)
        if weather_info:
            st.write(f"**Weather in {weather_info['city']}**")
            st.write(f"Temperature: {weather_info['temperature']}°C")
            st.write(f"Humidity: {weather_info['humidity']}%")
            st.write(f"Description: {weather_info['description']}")

    st.header("News Information")
    news_query = st.text_input("Enter topic for news", "")
    if news_query:
        news_articles = planner.get_news(news_query)
        if news_articles:
            for article in news_articles[:5]:  # Show top 5 articles
                st.subheader(article["title"])
                st.write(article["description"])
                st.write(f"[Read more]({article['url']})")

    planner.close()

if __name__ == "__main__":
    main()
