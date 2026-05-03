import asyncio
import streamlit as st
import logging
from src.database import NewsDatabase
from src.agent import NewsAgent
import clear_db

# Configure simple logging to be visible in Streamlit
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Set up page layout
st.set_page_config(page_title="Renewable Energy News", page_icon="⚡", layout="wide")

st.title("⚡ Renewable Energy News Dashboard")
st.markdown("A simple interface to test the backend agent and view the latest scraped articles.")

# Sidebar Controls
st.sidebar.header("Agent Controls")

if st.sidebar.button("🧹 Clean Database"):
    with st.spinner("Cleaning database..."):
        # Use our async DB cleanup script
        asyncio.run(clear_db.clear_database())
    st.sidebar.success("Database has been cleared!")
    st.rerun()

if st.sidebar.button("🚀 Run Pipeline"):
    with st.spinner("Running agent pipeline... this may take a few minutes."):
        # Run the agent synchronously within the streamlit thread
        agent = NewsAgent()
        articles = asyncio.run(agent.run())
    st.sidebar.success(f"Pipeline completed! Gathered {len(articles)} articles.")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("*Note: Running the pipeline will scrape new articles and insert them into the local SQLite database.*")

# Main Content Area
db = NewsDatabase()

# Fetch articles asynchronously
async def get_articles():
    return await db.get_all_articles()

articles = asyncio.run(get_articles())

if not articles:
    st.info("No articles found in the database. Use the sidebar to run the pipeline!")
else:
    st.subheader(f"Latest News ({len(articles)} articles)")
    
    # Display in a nice grid/list
    for article in articles:
        with st.container():
            col1, col2 = st.columns([1, 3])
            
            # Extract main image from images_links list
            images = article["images_links"]
            main_image = images[0] if images else "https://via.placeholder.com/300x200.png?text=No+Image"
            
            with col1:
                st.image(main_image, use_container_width=True)
                
            with col2:
                st.markdown(f"### [{article['title']}]({article['link']})")
                st.caption(f"📅 Published: {article['published_date']} | 🏷️ Tags: {', '.join(article['tags'])}")
                
                # Show a truncated preview of the full summary content to mimic a website card
                summary = article["content_summary"]
                preview_length = 300
                if len(summary) > preview_length:
                    summary = summary[:preview_length] + "..."
                st.write(summary)
                
        st.markdown("---")
