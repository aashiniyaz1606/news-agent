import asyncio
import math
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
    
    # Pagination
    items_per_page = 20
    total_pages = math.ceil(len(articles) / items_per_page)
    
    if total_pages > 1:
        current_page = st.number_input(f"Page (1 to {total_pages})", min_value=1, max_value=total_pages, value=1)
    else:
        current_page = 1
        
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_articles = articles[start_idx:end_idx]
    
    # Display in a nice grid/list
    for article in paginated_articles:
        with st.container():
            col1, col2 = st.columns([1, 3])
            
            # Extract main image from images_links list, filtering out empty strings
            images = [img for img in article["images_links"] if img and isinstance(img, str) and img.startswith("http")]
            main_image = images[0] if len(images) > 0 else "default_renewable.png"
            
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
